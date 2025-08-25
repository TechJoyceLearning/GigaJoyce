from discord import (
    Embed,
    Guild,
    GuildMember,
    Interaction,
    ActionRow,
    SelectOption,
    StringSelectMenu,
    SelectMenuInteraction,
)
from typing import Optional, Any
from utils.InteractionView import InteractionView
from settings.Setting import Setting


class MemberSetting(Setting[GuildMember]):
    """Interactive setting to pick a guild member."""
    def __init__(
        self,
        name: str,
        description: str,
        id: str,
        max_select: Optional[int] = 1,
        min_select: Optional[int] = 1,
        placeholder: Optional[str] = None,
        embed_description: Optional[str] = None,
        color: Optional[str] = "#ffffff",
        value: Optional[GuildMember] = None,
        locales: Optional[bool] = False,
        module_name: Optional[str] = None,
    ):
        """Initialize a `MemberSetting`.

        Args:
            name: Display name.
            description: Description text.
            id: Persistence key.
            max_select: Max users selectable.
            min_select: Min users selectable.
            placeholder: Custom placeholder text.
            embed_description: Override for the embed description.
            color: Hex embed color.
            value: Preselected member.
            locales: Enable i18n of display strings.
            module_name: Module context for translations.
        """
        super().__init__(name=name, description=description, locales=locales, module_name=module_name, id=id, type_="member")
        self.max = max_select
        self.min = min_select
        self.placeholder = placeholder or "Selecione um membro"
        self.embed_description = embed_description
        self.color = color
        self.value = value
        self.locales = locales
        self.module_name = module_name


    async def run(self, view: InteractionView) -> GuildMember:
        """
        Runs the interactive session for selecting a guild member.
        """
        guild_id = str(view.interaction.guild.id)
        translate = await view.client.translator.get_translator(guild_id=guild_id)

        name, description, kwargs = self.name, self.description, self.kwargs

        if self.module_name and self.locales:
            translate_module = await view.client.translator.get_translator(guild_id=guild_id, module_name=self.module_name)
            name, description, kwargs = self.apply_locale(translate_module=translate_module)

        member_select_menu = StringSelectMenu(
            custom_id="select",
            placeholder=translate("member.placeholder"),
            min_values=self.min,
            max_values=self.max,
            options=[],
        )
        row = ActionRow(components=[member_select_menu])
        embed = Embed(
            title=translate("member.title", setting_name=name),
            description=description or translate("member.description"),
            color=int(self.color.lstrip("#"), 16),
        )

        row_view = InteractionView()
        row_view.add_item = row
        await view.update({"embeds": [embed], "components": [row_view.children]})

        async def handle_select(menu_interaction: SelectMenuInteraction):
            """
            Handles the user selection.
            """
            await menu_interaction.response.defer()
            selected_members = [
                f"{view.interaction.guild.get_member(user_id).mention}" for user_id in menu_interaction.values
            ]
            if len(selected_members) > 1:
                embed.description = translate(
                    "member.multiple_selected", members=", ".join(selected_members)
                )
            else:
                embed.description = translate(
                    "member.single_selected", member=selected_members[0]
                )
            await view.update({"embeds": [embed], "components": []})
            view.stop()
            return view.interaction.guild.get_member(menu_interaction.values[0])

        view.on("select", handle_select)
        await view.wait()

        return None

    async def parse(self, config: str, client: Any, data: Any, guild: Guild) -> GuildMember:
        """
        Parses a member ID from the configuration and fetches the member.
        """
        member = guild.get_member(int(config)) or await guild.fetch_member(int(config))
        if not member:
            raise ValueError("Member not found")
        return member

    def parse_to_database(self, value: GuildMember) -> str:
        """
        Parses the member to its database representation.
        """
        return str(value.id)

    def parse_to_field(self, value: GuildMember) -> str:
        """
        Parses the member to a displayable field.
        """
        ...

    def clone(self) -> "MemberSetting":
        """
        Clones the current setting instance.
        """
        return MemberSetting(
            name=self.name,
            description=self.description,
            id=self.id,
            max_select=self.max,
            min_select=self.min,
            placeholder=self.placeholder,
            embed_description=self.embed_description,
            color=self.color,
            value=self.value,
        )
