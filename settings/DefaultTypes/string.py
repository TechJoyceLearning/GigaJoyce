from discord import (
    Embed,
    ButtonStyle,
    ActionRow
)
from discord.ui import Button, View
from typing import Callable, Optional, Dict, Any
from utils.InteractionView import InteractionView
from settings.Setting import Setting


class StringSettingFile(Setting[str]):
    """Interactive free‑text string setting with optional validation."""

    def __init__(
        self,
        name: str,
        description: str,
        id: str,
        filter: Optional[Dict[str, Any]] = None,
        color: str = "#ffffff",
        value: Optional[str] = None,
        locales: Optional[bool] = False,
        module_name: Optional[str] = None

    ):
        """Initialize a StringSettingFile.

        Args:
            name: Display name.
            description: UX description.
            id: Persistence key.
            filter: Optional dict with keys: `fn` (Callable[[str], bool]), `error` (str), `footer` (str).
            color: Hex color for the embed.
            value: Initial value.
            locales: Enable i18n of display strings.
            module_name: Module context for translations.
        """
        super().__init__(name=name, description=description, locales=locales, module_name= module_name, id=id, type_="string")
        self.filter = filter
        self.color = color
        self.value = value
        self.locales = locales
        self.module_name = module_name


    async def run(self, view: InteractionView) -> str:
        """Render the editor, collect free text, validate, and return it.

        Args:
            view: Active interaction view.

        Returns:
            The updated string value.

        Raises:
            TimeoutError: When the user does not provide input in time.
        """
        guild_id = str(view.interaction.guild.id)
        translate = await view.client.translator.get_translator(guild_id=guild_id)

        name, description, kwargs = self.name, self.description, self.kwargs

        if self.module_name and self.locales:
            translate_module = await view.client.translator.get_translator(guild_id=guild_id, module_name=self.module_name)
            name, description, kwargs = self.apply_locale(translate_module=translate_module)

        value_text = (
            translate("string_setting.too_long")
            if (len(self.value or "") > 1000)
            else (self.value or translate("string_setting.not_defined"))
        )

        embed = Embed(
            title=translate("string_setting.title", setting_name=name),
            description=description,
            color=int(self.color.lstrip("#"), 16),
        )
        embed.add_field(name=translate("string_setting.current_value"), value=value_text)
        if self.filter and "footer" in self.filter:
            embed.set_footer(text=self.filter["footer"])

        async def handle_set(inter: InteractionView):
            """
            Handles the set action to update the string value.
            """
            await inter.response.defer()
            input_embed = Embed(
                title=translate("string_setting.title", setting_name=name),
                description=description,
                color=int(self.color.lstrip("#"), 16),
            )
            input_embed.add_field(name=translate("string_setting.current_value"), value=value_text)
            input_embed.set_footer(text=translate("string_setting.enter_value"))
            await view.update(embeds=[input_embed], components=[])

            def message_filter(message):
                return message.author.id == view.interaction.user.id

            try:
                message = await view.client.wait_for(
                    "message", check=message_filter, timeout=30
                )
            except TimeoutError:
                embed.set_footer(text=translate("string_setting.timeout"))
                await view.update(embeds=[embed])
                return

            value = message.content
            await message.delete()

            if self.filter and not self.filter["fn"](value):
                error_embed = Embed(
                    title=translate("string_setting.title", setting_name=name),
                    description=description,
                    color=int(self.color.lstrip("#"), 16),
                )
                error_embed.add_field(name=translate("string_setting.current_value"), value=value_text)
                error_embed.set_footer(text=self.filter["error"])
                await view.update(embeds=[error_embed], components=[setButton])
                return

            self.value = value
            new_value_text = (
                translate("string_setting.too_long")
                if len(value) > 1000
                else value
            )
            embed = Embed(
                title=translate("string_setting.title", setting_name=self.name),
                color=int(self.color.lstrip("#"), 16),
            )
            embed.add_field(
                name=translate("string_setting.previous_value"), value=value_text
            )
            embed.add_field(
                name=translate("string_setting.new_value"), value=new_value_text
            )
            await view.update(embeds=[embed], components=[])
            view.stop()

        setButton = Button(
            label=translate("string_setting.set"),
            style=ButtonStyle.primary,
            custom_id="set",
        )
        setButton.callback = handle_set
        
        await view.update(embeds=[embed], components=[setButton])
        await view.wait()

        return self.value

    def parse_to_database(self, value: str) -> str:
        """
        Parse the value to a database-friendly format.
        """
        return value

    def parse_to_field(self, value: str) -> str:
        """
        Parse the value to a displayable string format.
        """
        return value

    def clone(self) -> "StringSettingFile":
        """
        Clone the current instance.
        """
        return StringSettingFile(
            name=self.name,
            description=self.description,
            id=self.id,
            filter=self.filter,
            color=self.color,
            value=self.value,
            locales = self.locales,
            module_name = self.module_name 
        )

