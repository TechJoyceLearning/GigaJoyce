# classes/managers/SettingsManager.py

from typing import Dict, Any, Optional
from settings.Setting import Setting
from classes.structs.Guild import Guild
from classes.structs.Member import Member
import logging
from shared.types import ExtendedClient


class SettingsManager:
    """Facade for loading and saving guild- and member-level settings.

    Delegates to `GuildManager` and `MemberManager` to materialize domain objects
    and persist updates.
    """

    def __init__(self, client: ExtendedClient, logger: Optional[logging.Logger] = None):
        self.client = client
        self.logger = logger or logging.getLogger("SettingsManager")
        self.guild_manager = client.guild_manager  # Assuming GuildManager is attached to client
        self.member_manager = client.member_manager    # Assuming memberManager is attached to client

    async def load_guild_settings(self, guild_id: int) -> Optional[Guild]:
        """Load and return a `Guild` object with settings materialized.

        Args:
            guild_id: Discord guild id.

        Returns:
            A `Guild` object or None if loading fails.
        """
        self.logger.debug(f"Loading settings for guild {guild_id}...")
        guild = await self.guild_manager.fetch_or_create(guild_id)
        if guild:
            self.logger.debug(f"Settings loaded for guild {guild_id}.")
            return guild
        else:
            self.logger.error(f"Failed to load settings for guild {guild_id}.")
            return None

    async def save_guild_setting(self, guild_id: int, setting_id: str, value: Any):
        """Persist a single guild setting.

        Args:
            guild_id: Discord guild id.
            setting_id: Setting identifier.
            value: New value to store.

        Raises:
            ValueError: If the guild cannot be loaded.
            KeyError: If the setting id is unknown for that guild.
        """
        guild = await self.guild_manager.fetch_or_create(guild_id)
        if not guild:
            raise ValueError(f"Guild with ID {guild_id} not found.")
        
        try:
            await guild.update_setting(setting_id, value)
            self.logger.debug(f"Saved setting '{setting_id}' for guild {guild_id} with value '{value}'.")
        except KeyError as e:
            self.logger.error(str(e))
            raise

    async def load_member_settings(self, member_id: int, guild_id: int) -> Optional[Member]:
        """Load and return a hydrated `Member` object with user settings.

        This delegates to `MemberManager.fetch_or_create`, which ensures the
        profile exists and resolves per‑user settings from module definitions.

        Args:
            member_id: Discord user id.
            guild_id: Discord guild id.

        Returns:
            Hydrated `Member` or `None` if loading fails.
        """
        self.logger.debug(f"Loading settings for member {member_id} in guild {guild_id}...")
        try:
            # This already returns a hydrated Member object with settings:
            member = await self.member_manager.fetch_or_create(str(member_id), str(guild_id))
            self.logger.debug(f"Settings loaded for member {member_id} in guild {guild_id}.")
            return member
        except Exception as e:
            self.logger.error(f"Failed to load settings for member {member_id} in guild {guild_id}: {e}")
            return None

    async def save_member_setting(self, member_id: int, guild_id: int, setting_id: str, value: Any):
        """Persist a single member (user-scoped) setting.

        Args:
            member_id: Discord user id.
            guild_id: Discord guild id.
            setting_id: Setting identifier.
            value: New value to store.

        Raises:
            ValueError: If the member cannot be loaded.
            Exception: If persistence fails.
        """
        member = await self.member_manager.fetch_or_create(member_id, guild_id)
        if not member:
            raise ValueError(f"member with ID {member_id} in guild {guild_id} not found.")
        
        try:
            await self.member_manager.update_member(member_id, guild_id, {f"settings.{setting_id}": value})
            self.logger.debug(f"Saved setting '{setting_id}' for member {member_id} in guild {guild_id} with value '{value}'.")
        except Exception as e:
            self.logger.error(f"Error saving setting '{setting_id}' for member {member_id} in guild {guild_id}: {e}")
            raise
        

