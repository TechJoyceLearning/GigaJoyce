# classes/structs/User.py

from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Any, Optional
from discord import Member as DiscordMember
from discord import User as DiscordUser
from collections import defaultdict
from classes.structs.ObjectFlags import ObjectFlags

if TYPE_CHECKING:
    from classes.structs.Guild import Guild
    from settings.Setting import Setting
    from shared.types import ExtendedClient

class Member:
    """Wrapper for a Discord member within a guild.

    Holds:
      - the Discord `Member` and `User` objects
      - the parent `Guild` wrapper
      - the member profile `data` from the database
      - resolved user-level `settings` (as declared by modules)
      - `flags` for feature toggles or state
    """

    def __init__(
        self,
        client: ExtendedClient,
        member: Member,
        guild: Guild,
        settings: Dict[str, Setting[Any]],
        data: Dict[str, Any],
    ):
        """Initialize the member wrapper.

        Args:
            client: Extended bot client.
            member: Discord member object.
            guild: Hydrated guild wrapper the member belongs to.
            settings: Resolved user settings (id → `Setting`).
            data: Backing DB document for this member.
        """
        self.id: int = member.id
        self.member: DiscordMember = member
        self.user: DiscordUser = member._user  # Access the Discord User object from Member
        self.client: ExtendedClient = client
        self.data: Dict[str, Any] = data
        self.guild: Guild = guild
        self.settings: Dict[str, Setting[Any]] = defaultdict(lambda: None, settings)
        self.flags: ObjectFlags = ObjectFlags(client, self)

    @property
    def display_name(self) -> str:
        """Return the preferred display name.

        Returns:
            The server nickname (`Member.display_name`) if present, otherwise the
            global username from the `User` object.
        """
        return self.member.display_name if self.member else self.user.name

    def get_setting(self, key: str) -> Optional[Any]:
        """Retrieve a user setting value by id.

        Args:
            key: Setting identifier.

        Returns:
            The `Setting` instance or `None` if missing.
        """
        return self.settings.get(key)

    def set_setting(self, key: str, value: Any) -> None:
        """Update or insert a user setting in-memory.

        Args:
            key: Setting identifier.
            value: New setting value (not persisted yet).
        """
        self.settings[key] = value

    def has_flag(self, flag: str) -> bool:
        """Return whether the member has a specific flag set.

        Args:
            flag: Flag key.

        Returns:
            True if the flag is set truthy, otherwise False.
        """
        return self.flags.has(flag)

    def set_flag(self, flag: str, value: Any) -> None:
        """Set or update a flag for this member (in-memory).

        Args:
            flag: Flag key.
            value: Value to assign.
        """
        self.flags.set(flag, value)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize main member data for diagnostics or persistence.

        Returns:
            A dict with user id, name, serialized settings and flags.
        """
        return {
            "id": self.id,
            "name": self.user.name,
            "settings": {key: setting.to_dict() for key, setting in self.settings.items()},
            "flags": self.flags.to_dict(),
        }

    def __repr__(self) -> str:
        """
        Return a string representation of the Member object.
        """
        return f"<Member id={self.id} name={self.user.name} settings={len(self.settings)}>"
