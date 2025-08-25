from code import interact
from typing import Optional
from discord import Embed, Interaction, ButtonStyle
from discord.ui import Button
from utils.InteractionView import InteractionView
from settings.Setting import Setting


class BooleanSetting(Setting[bool]):
    """
    Represents a boolean setting that can be modified via interactions.
    """

    def __init__(self, name: str, description: str, id: str, value: Optional[bool] = None, color: str = "#ffffff", locales: Optional[bool] = False, module_name: Optional[str] = None):
        """Initialize a `BooleanSetting`.

        Args:
            name: Display name.
            description: Short explanation.
            id: Persistence key.
            value: Initial value (defaults to `False`).
            color: Hex color to render the embed.
            locales: Enable i18n of display strings.
            module_name: Module context for translations.
        """
        super().__init__(name=name, description=description, locales=locales, module_name=module_name, id=id, type_="boolean")
        self.value = value or False
        self.color = color
        self.locales = locales
        self.module_name = module_name

    async def run(self, view: InteractionView) -> bool:
        """Render two buttons to toggle the boolean value.

        Returns the final value when the view ends (or current value on timeout).

        Args:
            view: Active `InteractionView`.
        """
        guild_id = str(view.interaction.guild.id)
        translate = await view.client.translator.get_translator(guild_id=guild_id)

        name, description, kwargs = self.name, self.description, self.kwargs

        if self.module_name and self.locales:
            translate_module = await view.client.translator.get_translator(guild_id=guild_id, module_name=self.module_name)
            localized = self.apply_locale(translate_module=translate_module)
            # If apply_locale returns a dict with keys 'name', 'description', 'kwargs'
            if isinstance(localized, dict):
                name = localized.get("name", name)
                description = localized.get("description", description)
                kwargs = localized.get("kwargs", kwargs)
            
        value = self.value
        embed = Embed(
            
            title=translate("boolean_setting.title", setting_name=name),
            description=description,
            color=int(self.color.lstrip("#"), 16)
        ).add_field(
            name=translate("current_value"),
            value=translate("enabled") if value else translate("disabled")
        )
        
        enable = Button(label=translate("enable"), custom_id="activate", style=ButtonStyle.secondary, disabled=value)
        disable = Button(label=translate("disable"), custom_id="deactivate", style=ButtonStyle.secondary, disabled=not value)

    
        async def button_callback(interaction: Interaction):
            await interaction.response.defer()
            nonlocal value
            value = not value
            view.stop()
            

        enable.callback = button_callback
        disable.callback = button_callback
        
        await view.update(embed=embed, components=[enable, disable])

        await view.wait()

        if not view.is_finished():
            # Handle timeout
            embed = Embed(
                title=translate("boolean_setting.title", setting_name=self.name),
                description=translate("timeout"),
                color=int(self.color.lstrip("#"), 16)
            )
            await view.update(embed=embed, components= [])

        return value
    
    def parse_to_database(self, value: bool) -> bool:
        """
        Prepares the channel for storage in the database.
        """
        return value

