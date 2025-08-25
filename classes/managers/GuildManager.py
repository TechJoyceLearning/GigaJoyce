from discord import Guild as DiscordGuild
from discord.ext.commands import Bot
from typing import Any, List, Dict
from classes.structs.Guild import Guild
from settings.Setting import Setting
from shared.types import ExtendedClient
import logging


class GuildManager:
    """Manage guild-level data, settings materialization, and caching.

    Responsibilities:
        - Ensure a guild document exists in MongoDB.
        - Merge module-declared default settings with DB values.
        - Maintain an in-memory settings cache per guild.
    """

    def __init__(self, client: ExtendedClient, logger: logging.Logger):
        self.client = client
        self.setting_cache: Dict[str, Dict[str, Setting]] = {}
        self.logger = logger

    async def fetch_or_create(self, guild_id: str, force: bool = False) -> Guild:
        """Fetch the Guild object with materialized settings, creating DB docs as needed.

        Loads the Discord guild from cache or API, ensures a guild profile exists
        in the `guilds` collection, and resolves the full settings map by combining
        module defaults and stored values.

        Args:
            guild_id: The Discord guild id (stringable).
            force: Reserved for future use (e.g., bypass certain caches).

        Returns:
            A :class:`Guild` wrapper with `guild`, `data`, and `settings` populated.

        Raises:
            ValueError: If the Discord guild cannot be found.
        """
        guild_id = str(guild_id)
        if not self.client.is_ready():
            await self.client.wait_until_ready()

        # Fetch or load the guild
        guild = self.client.get_guild(int(guild_id)) or await self.client.fetch_guild(int(guild_id))
        if not guild:
            raise ValueError(f"Guild with ID {guild_id} not found.")


        # Fetch or initialize guild data from database
        guild_data = await self.fetch_guild_data(guild_id)
        if not guild_data:
            guild_data = {"_id": guild_id, "settings": {}, "permissionsOverrides": {}}
            await self.create_guild_data(guild_data)

        # Fetch settings
        settings = self.client.setting_cache.get(guild_id) or await self._get_all_settings(guild_data, guild)
        self.client.setting_cache[guild_id] = settings

        return Guild(self.client, guild, guild_data, settings)
    
    async def fetch_all_members(self, guild_id: int) -> List[Dict[str, Any]]:
        """Fetching all members for a given guild.

        Args:
            guild_id: The Discord guild id.

        Returns:
            A list of member profile dicts or manager-defined structures.
        """
        gid = str(guild_id)
        return await self.client.db.find("members", {"guildId": gid})

    async def fetch_guild_data(self, guild_id: str) -> Dict[str, Any]:
        """Fetch the guild document from MongoDB.

        Args:
            guild_id: The Discord guild id.

        Returns:
            The guild document or None if not found.
        """
        return await self.client.db.find_one("guilds", {"_id": guild_id})

    async def create_guild_data(self, guild_data: Dict[str, Any]):
        """Insert a new guild document in MongoDB.

        Args:
            guild_data: Initial document to insert.

        Returns:
            The inserted id or driver-specific result.
        """
        return await self.client.db.insert_one("guilds", guild_data)

    async def get_language(self, guild_id: str) -> str:
        """Return the guild's language from settings, defaulting to 'en'.

        Args:
            guild_id: The Discord guild id.

        Returns:
            The ISO code of the language, e.g., "en".
        """
        guild_data = await self.fetch_or_create(guild_id)

        return guild_data.data.get("settings", {}).get("language", "en")

    async def _get_all_settings(self, guild_data: Dict[str, Any], guild: DiscordGuild) -> Dict[str, Setting]:
        """Materialize the full settings map for a guild.

        Combines module-declared settings with values retrieved from the database.
        If a default value is missing in the DB, parses and stores the default.

        Args:
            guild_data: The guild document from MongoDB.
            guild: The Discord guild.

        Returns:
            A mapping from setting id to `Setting` instances with `value` resolved.
        """
        settings_map = {}
        db_settings = guild_data.get("settings", {})

        for module in self.client.modules.values():
            for default_setting in module.settings:
                setting = default_setting.clone()
                self.logger.info(f"Cloned setting: {setting}")

                db_value = db_settings.get(setting.id)
                if db_value is not None:
                    try:
                        setting.value = await setting.parse(db_value, self.client, guild_data, guild)
                        self.logger.debug(f"Loaded setting '{setting.id}' with value: {setting.value}")
                    except Exception as e:
                        self.logger.error(f"Failed to parse setting '{setting.id}' from database: {e}")
                else:
                    try:
                        default_value = await setting.parse(setting.value, self.client, guild_data, guild)
                        self.logger.debug(f"Default value for '{setting.id}': {default_value}")

                        if not isinstance(default_value, (str, int, float, list, dict, bool, type(None))):
                            raise ValueError(f"Invalid default_value type for setting '{setting.id}': {type(default_value).__name__}")

                        query = {f"settings.{setting.id}": default_value}
                        self.logger.debug(f"Update query for guild {guild.id}: {query}")

                        await self.client.db.update_one(
                            "guilds",
                            {"_id": guild_data["_id"]},  # Filtro para encontrar o documento
                            query,  # Atualização com $set
                            upsert=True  # Garantir que ele crie o documento se não existir
                        )
                        setting.value = setting.value  # Valor padrão
                        self.logger.info(f"Created default setting '{setting.id}' for guild {guild.id}")
                    except Exception as e:
                        self.logger.error(f"Failed to create default setting '{setting.id}': {e}")

                settings_map[setting.id] = setting

        return settings_map


    async def find_by_kv(self, filter: Dict[str, Any]) -> List[Guild]:
        """Find guilds matching a filter and return their materialized profiles.

        Prefers `_id` as the guild id key but tolerates legacy documents using `id`.
        Each result is hydrated with settings (merged defaults + DB values) and
        cached under `setting_cache` keyed by the string guild id.

        Args:
            filter: Mongo‑style filter applied to the `guilds` collection.

        Returns:
            A list of `Guild` wrappers with `guild`, `data`, and `settings` populated.
        """
        guild_profiles = await self.client.db.find("guilds", filter)
        guilds = []
        for profile in guild_profiles:
            gid = str(profile.get("_id") or profile.get("id"))  # tolerate both, prefer _id
            if not gid:
                continue
            guild = self.client.get_guild(int(gid)) or await self.client.fetch_guild(int(gid))
            if not guild:
                continue
            settings = self.setting_cache.get(gid) or await self._get_all_settings(profile, guild)
            self.setting_cache[gid] = settings
            guilds.append(Guild(self.client, guild, profile, settings))

        self.logger.info(f"Found {len(guilds)} guilds matching filter {filter}.")
        return guilds

    def invalidate_cache(self, guild_id: str):
        """Invalidate the in-memory settings cache for a guild.

        Args:
            guild_id: The Discord guild id (stringable).
        """
        if guild_id in self.setting_cache:
            del self.setting_cache[guild_id]
            self.logger.debug(f"Invalidated cache for guild {guild_id}.")
