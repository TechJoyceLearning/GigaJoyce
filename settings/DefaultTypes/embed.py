from discord import Embed
from utils.InteractionView import InteractionView
from utils.components.EmbedCreatorComponent import EmbedCreator
from settings.Setting import Setting
from typing import Optional, Callable

class EmbedSettingFile(Setting[Embed]):
    """Interactive setting for building a Discord `Embed` with a wizard."""

    def __init__(self, name: str, description: str, id: str, module_name: str = None, locales: Optional[bool] = False, value: Embed = None):
        """Initialize an `EmbedSettingFile`.

        Args:
            name: Display name.
            description: UX text.
            id: Persistence key.
            module_name: Module context for translations.
            locales: Enable i18n of display strings.
            value: Initial embed (used to prefill the editor).
        """
        super().__init__(name=name, description=description, id=id, type_="embed")
        self.value = value
        self.module_name = module_name
        self.locales = locales

    async def run(self, view: InteractionView) -> Embed:
        """Open the interactive embed creator and return the result.

        Args:
            view: Active `InteractionView`.

        Returns:
            The resulting `Embed`.

        Raises:
            ValueError: If creation is aborted or fails.
        """
        guild_id = str(view.interaction.guild.id)
        translate = await view.client.translator.get_translator(guild_id=guild_id)

        name, description, kwargs = self.name, self.description, self.kwargs

        if self.module_name and self.locales:
            translate_module = await view.client.translator.get_translator(guild_id=guild_id, module_name=self.module_name)
            name, description, kwargs = self.apply_locale(translate_module=translate_module)

        embed = await EmbedCreator(
            view=view,
            check=lambda m: m.author.id == view.interaction.user.id,
            options={
                "shouldComplete": True,
                "data": self.value.to_dict() if self.value else None,
            },
        ).catch(lambda _: None
                )

        if not embed:
            raise ValueError(translate("error.failed_to_create_embed"))

        return embed

    def parse_to_database(self, value: Embed) -> dict:
        """
        Converts the embed to a database-storable format.

        Args:
            value (Embed): The embed to be parsed.

        Returns:
            dict: The parsed embed in dictionary format.
        """
        return value.to_dict()

    def parse(self, config: dict) -> Embed:
        """
        Parses a stored configuration back into an Embed object.

        Args:
            config (dict): The configuration dictionary.

        Returns:
            Embed: The parsed Embed object.
        """
        return Embed.from_dict(config)

    def parse_to_field(self, value: Embed, translate: Callable) -> str:
        """
        Converts the embed to a concise string representation.

        Args:
            value (Embed): The embed to be represented.

        Returns:
            str: A concise description of the embed.
        """
        description = value.description or translate("embed.no_description")
        truncated_description = (
            description[:55] + "..." if len(description) > 55 else description
        )
        return f"{translate('embed.title')}: {value.title}\n{translate('embed.description')}: {truncated_description}"

    def clone(self) -> "EmbedSettingFile":
        """
        Clones the current embed setting.

        Returns:
            EmbedSettingFile: A clone of this setting.
        """
        return EmbedSettingFile(
            name=self.name, description=self.description, id=self.id, bot=self.bot, value=self.value, locales=self.locales, module_name=self.module_name
        )
