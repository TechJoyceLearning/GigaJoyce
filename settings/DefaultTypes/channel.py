from discord import (
    Embed,
    Guild as DiscordGuild,
    GuildChannel,
    SelectOption,
    ButtonStyle,
    TextChannel
)
from discord.ui import Select, Button
from utils.InteractionView import InteractionView
from typing import Optional, List
from settings.Setting import Setting


class ChannelSetting(Setting[GuildChannel]):
    """
    Represents a setting for selecting a Discord channel.
    """

    def __init__(
        self,
        name: str,
        description: str,
        id: str,
        channel_types: Optional[List[type]] = None,
        value: Optional[GuildChannel] = None,
        max_values: int = 1,
        min_values: int = 1,
        color: str = "#ffffff",
        locales: Optional[bool] = False,
        module_name: Optional[str] = None,
    ):
        super().__init__(name=name, description=description, locales=locales, module_name=module_name, id=id, type_="channel")
        self.channel_types = channel_types or [TextChannel]
        self.value = value
        self.max_values = max_values
        self.min_values = min_values
        self.color = color
        self.locales = locales
        self.module_name = module_name

    async def run(self, view: InteractionView) -> Optional[GuildChannel]:
        """Initialize a `ChannelSetting`.

        Args:
            name: Display name.
            description: Description text.
            id: Persistence key.
            channel_types: Allowed channel classes (default: `[TextChannel]`).
            value: Preselected channel.
            max_values: Max selections in the Select.
            min_values: Min selections in the Select.
            color: Hex embed color.
            locales: Enable i18n of display strings.
            module_name: Module context for translations.
        """
        guild_id = str(view.interaction.guild.id)
        translate = await view.client.translator.get_translator(guild_id=guild_id)

        name, description, kwargs = self.name, self.description, self.kwargs

        if self.module_name and self.locales:
            translate_module = await view.client.translator.get_translator(guild_id=guild_id, module_name=self.module_name)
            name, description, kwargs = self.apply_locale(translate_module=translate_module)
            
            
        # Placeholder e mensagem inicial
        select_placeholder = translate("select_channel.placeholder")
        current_channel = (
            translate("select_channel.current", channel_name=self.value.name)
            if self.value
            else translate("select_channel.none")
        )

        embed = Embed(
            title=translate("settings.configure", setting_name=name),
            description=f"{description}\n\n{current_channel}",
            color=int(self.color.lstrip("#"), 16),
        )

        # Menu de seleção de canais
        channel_options = [
            SelectOption(label=channel.name, value=str(channel.id))
            for channel in view.interaction.guild.channels
            if isinstance(channel, tuple(self.channel_types))
        ]
        if not channel_options:
            await view.interaction.response.send_message(
                translate("select_channel.no_channels"), ephemeral=True
            )
            return None

        channel_select_menu = Select(
            placeholder=select_placeholder,
            min_values=self.min_values,
            max_values=self.max_values,
            options=channel_options,
        )

        # Botão de confirmação
        confirm_button = Button(
            label=translate("confirm"),
            style=ButtonStyle.success,
        )

        async def confirm_callback(interaction):
            """
            Callback para confirmar a seleção de canal.
            """
            selected_channel_id = channel_select_menu.values[0] 
            selected_channel = view.interaction.guild.get_channel(int(selected_channel_id))
            if selected_channel:
                self.value = selected_channel
                embed.description = translate(
                    "select_channel.updated", channel_name=selected_channel.name
                )
                await interaction.response.edit_message(embed=embed, view=None)
                view.stop()
            else:
                await interaction.response.send_message(
                    translate("select_channel.error"), ephemeral=True
                )

        async def timeout_callback():
            """
            Callback para timeout.
            """
            embed.description = translate("select_channel.timeout")
            await view.interaction.edit_original_message(embed=embed, view=None)

        # Configuração do menu e callbacks
        channel_select_menu.callback = confirm_callback
        view.add_item(channel_select_menu)
        view.add_item(confirm_button)

        # Envia a interação
        await view.send(embed=embed)
        await view.wait(timeout_callback)

        return self.value

    def parse_to_database(self, value: GuildChannel) -> str:
        """
        Prepares the channel for storage in the database.
        """
        return str(value.id)

    async def parse(self, config: str, guild: DiscordGuild) -> Optional[GuildChannel]:
        """
        Parses a channel ID into a GuildChannel object.
        """
        try:
            return await guild.fetch_channel(int(config))
        except Exception:
            return None

    def parse_to_field(self, value: GuildChannel) -> str:
        """
        Converts the value to a display-friendly string.
        """
        return f"Name: {value.name}\nID: {value.id}"
