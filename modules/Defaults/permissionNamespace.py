from typing import Optional
from discord import Member as GuildMember, TextChannel
from shared.types import ExtendedClient

async def RolesNamespace(client: ExtendedClient, node: str, member: GuildMember, channel: Optional[TextChannel]) -> bool:
    """Return True if the member has the role id referenced in the permission path.

    Expected path shape: "Role.<role_id>" or "Role.*" for wildcard nodes higher up the tree.

    Args:
        client: Bot client.
        node: Permission path, for example "Role.1234567890".
        member: Member to check.
        channel: Optional channel context, unused here.

    Returns:
        True if `member` has the role with the given id, False otherwise.
    """
    broken = node.split(".")
    role_id = broken.pop()
    if not role_id:
        return False
    return any(role.id == int(role_id) for role in member.roles)

async def ChannelsNamespace(client: ExtendedClient, node: str, member: GuildMember, channel: Optional[TextChannel]) -> bool:
    """Return True if the current channel matches the id referenced in the permission path.

    Expected path shape: "Channel.<channel_id>".

    Args:
        client: Bot client.
        node: Permission path, for example "Channel.1234567890".
        member: Member to check, unused here.
        channel: Channel context for the comparison.

    Returns:
        True if `channel.id` equals the id in the path, False otherwise.
    """
    broken = node.split(".")
    channel_id = broken.pop()
    if not channel_id or not channel:
        return False
    return channel.id == int(channel_id)

async def UsersNamespace(client: ExtendedClient, node: str, member: GuildMember, channel: Optional[TextChannel]) -> bool:
    """Return True if the member id matches the id referenced in the permission path.

    Expected path shape: "User.<user_id>".

    Args:
        client: Bot client.
        node: Permission path, for example "User.1234567890".
        member: Member to check.
        channel: Optional channel context, unused here.

    Returns:
        True if `member.id` equals the id in the path, False otherwise.
    """
    broken = node.split(".")
    user_id = broken.pop()
    if not user_id:
        return False
    return member.id == int(user_id)
