from typing import Dict, Union, Optional
from shared.types import OverrideNode, PermissionOverrideTree
import logging

from typing import Dict, Union, Optional
from shared.types import OverrideNode, PermissionOverrideTree
import logging


def is_end_node(node: Union[OverrideNode, PermissionOverrideTree]) -> bool:
    """Return True if a permissions tree node is a terminal `OverrideNode`.

    A terminal node carries the concrete `allow`/`deny` lists; an internal node
    is a nested mapping (another `PermissionOverrideTree`).
    """
    return not isinstance(node, dict)


class Permissions:
    """Hierarchical permission override tree with wildcard support.

    Stores overrides under dot‑separated paths (e.g., "Role.*", "User.123").
    Provides helpers to set nodes, resolve nodes (with optional strict mode),
    and ensure that intermediate paths exist.
    """
    def __init__(self, logger: logging.Logger, permissions: PermissionOverrideTree):
        """Initialize a permission tree wrapper.

        Args:
            logger: Logger for diagnostic messages.
            permissions: Root permission tree mapping.
        """
        self.logger = logger
        self.permissions = permissions

    def set(self, permission: str, result: OverrideNode):
        """Insert or replace a terminal override node at a given path.

        Creates intermediate namespaces as needed. If a path segment already
        points to a terminal node, the operation fails and is logged.

        Args:
            permission: Dot‑separated path (e.g., "Feature.Admin.Purge").
            result: Terminal override node with `allow` / `deny` lists.
        """
        namespaces = permission.split(".")
        current = self.permissions
        last = namespaces.pop()

        if not last:
            self.logger.warning("No namespaces provided.")
            return

        for namespace in namespaces:
            if namespace not in current:
                current[namespace] = {}
            elif is_end_node(current[namespace]):
                self.logger.error(f"Cannot create namespace '{namespace}' as it's already an end node.")
                return
            current = current[namespace]

        current[last] = result

    def get(self, permission: str, strict: bool = False) -> Optional[Union[OverrideNode, PermissionOverrideTree]]:
        """Resolve a path to either a terminal node or subtree.

        Supports a literal '*' at any level as a wildcard fallback.

        Args:
            permission: Dot‑separated path to resolve.
            strict: If True, do not return wildcard fallbacks; only exact matches.

        Returns:
            An `OverrideNode` (terminal), a `PermissionOverrideTree` (subtree),
            or `None` if no match is found (strict mode) / no wildcard fallback.
        """
        namespaces = permission.split(".")
        current = self.permissions
        last_global: Optional[OverrideNode] = None

        for namespace in namespaces:
            if namespace in current:
                node = current[namespace]
                if is_end_node(node):
                    return node
                current = node
            elif '*' in current:
                wildcard_node = current['*']
                if is_end_node(wildcard_node):
                    last_global = wildcard_node  # type: ignore
            else:
                return last_global if not strict else None

        return current if is_end_node(current) else last_global

    def get_end_node(self, permission: str, strict: bool = False) -> Optional[OverrideNode]:
        """Resolve to a terminal node only.

        Args:
            permission: Path to resolve.
            strict: If True, require exact path (ignore wildcard fallback).

        Returns:
            The terminal `OverrideNode` or `None`.
        """
        node = self.get(permission, strict)
        if node is not None and is_end_node(node):
            return node  # type: ignore
        return None

    def get_or_create_path(self, permission: str) -> PermissionOverrideTree:
        """Ensure a subtree exists for the provided path and return it.

        Creates intermediate namespaces as needed and always returns the dict
        that represents the final segment (which may then be populated).

        Args:
            permission: Dot‑separated path for the subtree.

        Returns:
            The mutable mapping for the last segment.
        """
        namespaces = permission.split(".")
        current = self.permissions

        for namespace in namespaces:
            if namespace not in current:
                current[namespace] = {}
            elif is_end_node(current[namespace]):
                self.logger.error(f"Cannot create or traverse namespace '{namespace}' as it's already an end node.")
                raise TypeError(f"Path segment '{namespace}' is a terminal node, not a namespace.")
            current = current[namespace]

        if is_end_node(current):
            self.logger.error("Final path segment is a terminal node, not a namespace.")
            raise TypeError("Final path segment is a terminal node, not a namespace.")
        return current  # type: ignore[return-value]
