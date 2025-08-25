from discord.ext.commands import Bot
from typing import Dict, Any, Optional, TYPE_CHECKING
from classes.structs.Permissions import Permissions 
from utils.parsingRelated import parse_from_database
from classes.structs.ObjectFlags import ObjectFlags
from shared.types import ExtendedClient
from discord import Guild as DiscordGuild

if TYPE_CHECKING:
    from settings.Setting import Setting




class Guild:
    """Wrapper for a Discord guild with bot-specific data and settings.

    Exposes:
      - `guild`: the underlying Discord guild object
      - `data`: the backing database document
      - `settings`: resolved module settings for this guild
      - `permission_overrides`: parsed permission overrides
      - `flags`: feature/behavior flags for the guild
    """

    def __init__(self, client: ExtendedClient, guild: DiscordGuild, guild_data: Dict[str, Any], settings: Dict[str, "Setting"]):
        """Create a hydrated Guild wrapper.

        Args:
            client: Extended bot client.
            guild: Discord guild object.
            guild_data: Backing DB document for this guild.
            settings: Map of resolved settings (id → `Setting`).
        """
        self.client = client
        self.guild = guild
        self.data = guild_data
        self.settings = settings
        self.permission_overrides = Permissions(client.logger, parse_from_database(guild_data.get("permissions_overrides", [])))
        self.id = guild.id
        self.flags = ObjectFlags(client, self)


    def get_setting(self, setting_id: str) -> Optional["Setting"]:
        """Return a setting by id for this guild.

        Args:
            setting_id: Identifier of the setting.

        Returns:
            The `Setting` instance or `None` if missing.
        """
        return self.settings.get(setting_id)
