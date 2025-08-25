# classes/managers/PermissionsManager.py

from typing import Dict, Optional, Any, Union
from discord.ext.commands import Bot
from discord import TextChannel
from discord import Member as GuildMember
from shared.types import PermissionNode, RecursiveMap, OverrideNode
import logging


def is_end_node(node: Union[PermissionNode, RecursiveMap]) -> bool:
    """Return True if the node is a terminal permission node.

    A terminal node is a callable that resolves an access decision and is not a dict.
    """
    return not isinstance(node, dict)

class PermissionsManager:
    """Hierarchical permission registry and resolver.

    Stores permission nodes in a nested mapping keyed by dot‑separated paths, for example
    "Role.*", "User.1234", "Channel.5678", or custom trees like "Feature.Admin.Purge".

    Resolution rules:
      1. Exact path match returns the first terminal node found.
      2. If a segment is missing, the resolver remembers a sibling literal "*" at that level,
         which acts as a wildcard. The last wildcard seen becomes the fallback.
      3. If the traversal ends on a terminal node, it is returned. Otherwise the last wildcard wins.

    The manager also evaluates override documents with "allow" and "deny" lists by calling into
    registered nodes.

    Args:
        client: Discord bot client.
        logger: Logger instance.
    """
    def __init__(self, client: Bot, logger: logging.Logger):
        self.client = client
        self.logger = logger
        self.permissions: RecursiveMap = {}

    def register_node(self, permission: str, result: PermissionNode):
        """Register a terminal permission node.

        The permission string is a dot‑separated path. Intermediate namespaces are created as dicts.
        The final segment becomes the terminal node and must be a callable that returns an awaitable bool.

        Example:
            register_node("Role.*", role_checker)
            register_node("Feature.Admin.Purge", purge_checker)

        Args:
            permission: Permission path, for example "Role.*" or "Feature.Admin.Purge".
            result: Async callable of type PermissionNode.
        """
        namespaces = permission.split('.')
        current = self.permissions
        last = namespaces.pop() if namespaces else None

        if not last:
            self.logger.warning("No namespaces provided for permission registration.")
            return

        for namespace in namespaces:
            if namespace not in current:
                current[namespace] = {}
            elif not isinstance(current[namespace], dict):
                self.logger.error(f"Cannot create namespace '{namespace}' as it's already an end node.")
                return
            current = current[namespace]

        current[last] = result

    def get_node(self, permission: str) -> Optional[PermissionNode]:
        """Resolve a permission path into a terminal node.

        Traverses the internal tree segment by segment and returns the matching callable.
        Supports a literal "*" at any level as a wildcard fallback.

        Args:
            permission: Permission path to resolve.

        Returns:
            The resolved PermissionNode or None if nothing matches.
        """
        namespaces = permission.split('.')
        current = self.permissions
        last_global: Optional[PermissionNode] = None

        for namespace in namespaces:
            if namespace in current:
                node = current[namespace]
                if is_end_node(node):
                    return node
                current = node
            elif '*' in current:
                last_global = current['*']
            else:
                return last_global

        return current if is_end_node(current) else last_global

    async def check_permission_for(self, node: str, member: GuildMember, channel: TextChannel) -> bool:
        """Evaluate a permission node for a given member and channel.

        Args:
            node: Permission path to evaluate.
            member: Guild member being checked.
            channel: Text channel context for the check.

        Returns:
            True if the node grants permission, False otherwise.
        """
        permission_node = self.get_node(node)
        if not permission_node:
            self.logger.warning(f"Permission node '{node}' not found.")
            return False

        try:
            result = await permission_node(self.client, node, member, channel)
            return result
        except Exception as e:
            self.logger.error(f"Error executing permission node '{node}': {e}")
            return False

    async def compute_permissions(self, override: OverrideNode, member: GuildMember, channel: TextChannel) -> Optional[bool]:
        """Evaluate an override document with allow and deny lists.

        The override contains two lists of permission paths:
            - "allow": if any path evaluates to True, returns True
            - "deny": if any path evaluates to True, returns False

        Args:
            override: Override document with "allow" and "deny".
            member: Guild member being checked.
            channel: Text channel context.

        Returns:
            True, False, or None if no rule matched.
        """
        for allow_perm in override.get('allow', []):
            if await self.check_permission_for(allow_perm, member, channel):
                return True

        for deny_perm in override.get('deny', []):
            if await self.check_permission_for(deny_perm, member, channel):
                return False

        return None

    async def has_permission(self, node: str, member: GuildMember, channel: TextChannel, override: OverrideNode) -> bool:
        """High‑level permission check that combines Discord flags and overrides.

        Order:
            1) If the last segment of `node` matches a Discord permission flag and the member has it,
               return True.
            2) Evaluate the override document. If it resolves, return that result.
            3) Default to False.

        Note:
            This method is intended for cases where `node` maps to a Discord built‑in permission,
            for example "Permissions.manage_messages". For custom namespaces like "Role.*", prefer
            `compute_permissions` or `check_permission_for` with explicit nodes.

        Args:
            node: Permission path to check.
            member: Guild member being checked.
            channel: Text channel context.
            override: Override document with "allow" and "deny".

        Returns:
            True if permission is granted, otherwise False.
        """
        discord_permission = getattr(member.guild_permissions, node.split('.')[-1], False)
        if discord_permission:
            return True

        override_result = await self.compute_permissions(override, member, channel)
        if override_result is not None:
            return override_result

        return False
