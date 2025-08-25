from discord import (
    ActionRow,
    Button,
    ButtonStyle,
    Embed,
    Interaction,
    SelectOption,
    SelectMenu,
)
from typing import Callable, List, Optional, Dict, Any, Tuple
from utils.InteractionView import InteractionView
from settings.Setting import Setting
from classes.structs.Member import Member

def chunk_array(arr: List[Any], size: int) -> List[List[Any]]:
    """Split a list into rows of `size`."""
    return [arr[i:i + size] for i in range(0, len(arr), size)]

class DynamicSelectSetting(Setting[List[str]]):
    """Split a list into rows of `size`."""

    def __init__(
        self,
        name: str,
        description: str,
        id: str,
        get_fn: Callable[[Member], List[str]],
        max_values: Optional[int] = 1,
        min_values: Optional[int] = 1,
        style: Optional[str] = "StringSelectMenu",
        value: Optional[List[str]] = None,
        permission: Optional[int] = None,
    ):
        """Initialize a `DynamicSelectSetting`.

        Args:
            name: Display name.
            description: Description text.
            id: Persistence key.
            get_fn: Callable that returns option labels for the current member.
            max_values: Maximum options selectable.
            min_values: Minimum options selectable.
            style: "StringSelectMenu" or "Button".
            value: Initial selection.
            permission: Optional permission flag/bit.
        """
        super().__init__(name=name, description=description, id=id, permission=permission, type_="dynamicSelect")

        self.get_fn = get_fn
        self.max_values = max_values
        self.min_values = min_values
        self.style = style
        self.value = value or []
        self.permission = permission


    async def run(self, view: InteractionView) -> List[str]:
        guild_id = str(view.interaction.guild.id)
        translate = await view.client.translator.get_translator(guild_id=guild_id)

        name, description, kwargs = self.name, self.description, self.kwargs

        if self.module_name and self.locales:
            translate_module = await view.client.translator.get_translator(guild_id=guild_id, module_name=self.module_name)
            name, description, kwargs = self.apply_locale(translate_module=translate_module)

        member = await self.bot.guild_manager.fetch_member(view.interaction.member.id, view.interaction.guild.id)
        options = await self.get_fn(member)

        if not options:
            embed = Embed(
                title=translate("dynamic_select.no_options"),
                color=0xFF0000
            )
            await view.interaction.response.send_message(embed=embed, ephemeral=True)
            return []

        if self.style == "StringSelectMenu":
            return await self._run_string_select_menu(view.interaction, options, translate, (name, description, kwargs))
        elif self.style == "Button":
            return await self._run_button_style(view.interaction, options, translate, (name, description, kwargs))
        else:
            raise ValueError("Unsupported style for DynamicSelectSetting")

    async def _run_string_select_menu(self, interaction: Interaction, options: List[str], translate: Callable, describers: Tuple[str]) -> List[str]:
        name, description, kwargs = describers
        
        select_menu = SelectMenu(
            custom_id="select",
            placeholder=translate("dynamic_select.placeholder"),
            options=[SelectOption(label=option, value=option) for option in options[:25]],
            max_values=min(self.max_values, len(options)),
            min_values=min(self.min_values, len(options)),
        )
        row = ActionRow(components=[select_menu])

        embed = Embed(
            title=translate("dynamic_select.configure", setting_name=name),
            description=description,
            color=0x00FF00
        )

        view = InteractionView(interaction)
        await view.update(embed=embed, components=[row])

        async def on_select(inter: Interaction):
            await inter.response.defer()
            self.value = inter.data.get("values", [])
            await view.stop()

        view.on("select", on_select)
        await view.wait()

        return self.value

    async def _run_button_style(self, interaction: Interaction, options: List[str], translate: Callable, describers: Tuple[str]) -> List[str]:
        name, description, kwargs = describers
        
        buttons = [
            Button(label=option, custom_id=option, style=ButtonStyle.primary)
            for option in options[:20]
        ]
        rows = [ActionRow(components=row) for row in chunk_array(buttons, 5)]

        embed = Embed(
            title=translate("dynamic_select.configure", setting_name=name),
            description=description,
            color=0x00FF00
        )

        view = InteractionView(interaction)
        await view.update(embed=embed, components=rows)

        async def on_button_click(inter: Interaction):
            await inter.response.defer()
            self.value = [inter.data["custom_id"]]
            await view.stop()

        view.on("any", on_button_click)
        await view.wait()

        return self.value

    def clone(self) -> "DynamicSelectSetting":
        return DynamicSelectSetting(
            name=self.name,
            description=self.description,
            id=self.id,
            get_fn=self.get_fn,
            max_values=self.max_values,
            min_values=self.min_values,
            style=self.style,
            value=self.value,
            bot=self.bot,
        )
