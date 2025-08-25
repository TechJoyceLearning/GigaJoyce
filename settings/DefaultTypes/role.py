from discord import (
    Embed,
    Interaction,
    Role,
    ActionRow,
    SelectOption
)
from discord.ui import Select,  View
from typing import Optional, Any, Awaitable
from utils.InteractionView import InteractionView
from settings.Setting import Setting
from classes.structs.Guild import Guild
from shared.types import ExtendedClient

class RoleSetting(Setting[Role]):
    """Interactive role selector.

    Renders a dropdown with all non‑managed roles in the guild and persists the
    selected role.
    """
    def __init__(
        self,
        name: str,
        description: str,
        id: str,
        max_values: Optional[int] = 1,
        min_values: Optional[int] = 1,
        placeholder: Optional[str] = None,
        embed_description: Optional[str] = None,
        color: str = "#ffffff",
        value: Optional[Role] = None,
        locales: Optional[bool] = False,
        module_name: Optional[str] = None
    ):
        """Initialize a RoleSetting.

        Args:
            name: Display name.
            description: UX description.
            id: Persistence key.
            max_values: Max selectable roles.
            min_values: Min selectable roles.
            placeholder: Placeholder for the select.
            embed_description: Optional description override.
            color: Hex color for the embed.
            value: Initial role.
            locales: Enable i18n of display strings.
            module_name: Module context for translations.
        """
        super().__init__(name=name, description=description, locales=locales, module_name=module_name, id=id, type_="role")
        self.max_values = max_values
        self.min_values = min_values
        self.placeholder = placeholder
        self.embed_description = embed_description
        self.description = description
        self.name = name
        self.color = color
        self.value = value
        self.locales = locales
        self.module_name = module_name

    async def run(self, view: InteractionView) -> Role:
        """Render the dropdown and return the chosen role.

        Args:
            view: Active interaction view.

        Returns:
            The selected `Role`.

        Raises:
            TimeoutError: If the selection is not completed in time.
        """
        guild_id = str(view.interaction.guild.id)
        translate = await view.client.translator.get_translator(guild_id=guild_id)

        name, description, kwargs = self.name, self.description, self.kwargs

        if self.module_name and self.locales:
            translate_module = await view.client.translator.get_translator(guild_id=guild_id, module_name=self.module_name)
            name, description, kwargs = self.apply_locale(translate_module=translate_module)

        placeholder = self.placeholder or translate("role_setting.placeholder")
        embed = Embed(
            title=translate("role_setting.title", setting_name=name),
            description=description or translate("role_setting.description"),
            color=int(self.color.lstrip("#"), 16),
        )

        roles = view.interaction.guild.roles
        options = [
            SelectOption(label=role.name, value=str(role.id)) for role in roles if not role.managed
        ]

        select = Select(
            placeholder=placeholder,
            options=options,
            custom_id=f"select-{view.view_id}",  # Adiciona o ID único
            max_values=self.max_values,
            min_values=self.min_values,
        )

        view.clear_items()
        view.add_item(select)

        await view.update(embed=embed, components=view.children)

        async def handle_select(inter: Interaction):
            await inter.response.defer()
            selected_role_id = inter.data["values"][0]
            selected_role = view.interaction.guild.get_role(int(selected_role_id))
            if not selected_role:
                return

            self.value = selected_role
            embed.description = translate("role_setting.selected", role_name=selected_role.name)

            await view.update(embed=embed, components=[])
            view.stop()
            
            return self.value

        select.callback = handle_select

        await view.wait()

        if not self.value:
            raise TimeoutError(translate("role_setting.timeout_error"))

        return self.value



    def parse_to_database(self, value: Role) -> str:
        """
        Parse the role to a database-friendly format.
        """
        return value.id

    async def parse(self, config: Any, client: ExtendedClient, guild_data: Any, guild: Guild) -> Role:
        """
        Parse the role from the database configuration.
        """
        return f"<@&{config}>"

    def parse_to_field(self, value: Role, translator: Optional[callable] = None) -> str:
        """
        Parse the role to a displayable string format.
        """
        if translator:
            return f'{translator("role_setting.display_value")}: <@{value.id}>'
        else:
            return f'Role: <@{value.id}>'


    def clone(self) -> "RoleSetting":
        """Return a shallow clone preserving selector configuration."""
        return RoleSetting(
            name=self.name,
            description=self.description,
            id=self.id,
            max_values=self.max_values,
            min_values=self.min_values,
            placeholder=self.placeholder,
            embed_description=self.embed_description,
            color=self.color,
            value=self.value,
            locales=self.locales,
            module_name=self.module_name
        )