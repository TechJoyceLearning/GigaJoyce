from typing import Any, Callable, List, Optional, TypeVar
from discord import Embed, Interaction, ButtonStyle, SelectOption
from discord.ui import Button, Select
from utils.InteractionView import InteractionView
from settings.Setting import Setting
from discord import Guild as DiscordGuild
import discord

T = TypeVar("T")

class ArraySetting(Setting[List[Any]]):
    """A composite setting that manages an array of values interactively.

    This setting renders an embed with **Add**, **Remove**, and **Confirm** UI,
    delegates item creation/edition to a child `Setting`, and optionally exposes
    additional “general” settings as extra buttons.

    Notes:
        - The visual content can be customized via `embed_override` or
          `update_fn`.
        - If `locales=True` and `module_name` is set, text goes through the
          module translator for i18n.
    """

    def __init__(
        self,
        name: str,
        description: str,
        id: str,
        child: Setting[Any],
        value: Optional[List[Any]] = None,
        general_settings: Optional[List[Setting[Any]]] = None,  # Botões extras de configurações gerais
        embed_override: Optional[Embed] = None,
        update_fn: Optional[Callable[[List[T]], Embed]] = None,
        locales: Optional[bool] = False,
        module_name: Optional[str] = None,
    ):
        """Initialize an `ArraySetting`.

        Args:
            name: Human‑readable name.
            description: Short explanation for help/UX.
            id: Unique persistence key.
            child: Setting used to create/edit **each** array item.
            value: Initial list value.
            general_settings: Optional settings exposed as extra buttons.
            embed_override: Static embed to render instead of the default.
            update_fn: Callable that builds a custom embed from current values.
            locales: Enable i18n of display strings.
            module_name: Module name for translation/emoji lookups.
        """
        super().__init__(name=name, description=description, id=id, locales=locales, module_name=module_name, type_="array")
        self.child = child
        self.value = value or []
        self.general_settings = general_settings or []  # Lista de configurações gerais
        self.embed_override = embed_override
        self.update_fn = update_fn
        self.locales = locales
        self.module_name = module_name

    async def run(self, view: InteractionView) -> List[T]:
        """Run the interactive UI to modify the array.

        Flow:
            1. Render the embed (using `update_fn` or default renderer).
            2. **Add** → delegates to `self.child.run(...)` and appends result.
            3. **Remove** → shows a Select to remove an item by index.
            4. **General** buttons → delegates to each provided setting.
            5. **Confirm** → persists current state and ends the view.

        Args:
            view: Active `InteractionView` to render in.

        Returns:
            The final list of values.
        """
        guild_id = str(view.interaction.guild.id)
        translate = await view.client.translator.get_translator(guild_id=guild_id)

        name, description, kwargs = self.name, self.description, self.kwargs
    
        translate_module = lambda value: value

        if self.module_name and self.locales:
            translate_module = await view.client.translator.get_translator(guild_id=guild_id, module_name=self.module_name)
            locale_result = self.apply_locale(translate_module=translate_module)
            if isinstance(locale_result, tuple) and len(locale_result) == 3:
                name, description, kwargs = locale_result
            else:
                name, description, kwargs = self.name, self.description, self.kwargs

        if hasattr(self, "child"):
            self.propagate_locales(self.child)

        current_values = self.value or []

        def update_embed():
            if self.update_fn:
                return self.update_fn(current_values)
            elif self.embed_override:
                embed = self.embed_override
                embed.clear_fields()
                for field in self.parse_to_field_list(translate):
                    embed.add_field(name=field["name"], value=field["value"], inline=field["inline"])
                return embed
            else:
                embed = Embed(
                    title=translate("array_setting.title", setting_name=name),
                    description=description,
                    color=0x00FF00,
                )
                for field in self.parse_to_field_list(translate):
                    embed.add_field(name=field["name"], value=field["value"], inline=field["inline"])
                return embed

        embed = update_embed()
        interaction_view = view.clone()
        

        async def add_callback(interaction: Interaction):
            await interaction.response.defer()
            cloned_view = interaction_view.clone()
            result = await self.child.run(cloned_view)
            cloned_view.destroy()
            if result is not None:
                current_values.append(result)
                self.value = current_values
                await interaction.edit_original_response(embed=update_embed(), view=interaction_view)

        async def remove_callback(interaction: Interaction):
            """
            Callback para remover itens do ArraySetting.
            """
            await interaction.response.defer()
            if not current_values:
                await interaction.followup.send(translate("no_items_to_remove"), ephemeral=True)
                return
            
            cloned_view = interaction_view.clone()

            # Criando as opções para o Select
            options = [
                SelectOption(label=f"{index + 1}", value=str(index))
                for index in range(len(current_values))
            ]
            select = Select(
                placeholder=translate("select_to_remove"),
                options=options,
                custom_id="remove_select",
            )

            async def remove_value_callback(selected_interaction: Interaction):
                """
                Callback interno para manipular a seleção e remoção de valores.
                """
                await selected_interaction.response.defer()
                try:
                    index = int(selected_interaction.data["values"][0])
                    if 0 <= index < len(current_values):
                        # Removendo o valor selecionado
                        current_values.pop(index)
                        self.value = current_values

                    # Atualizando o embed com os valores restantes
                    await interaction.edit_original_response(
                        embed=update_embed(),
                        view=interaction_view,
                    )
                except Exception as e:
                    view.client.logger.error(f"Erro while removing the value: {e}")
                    await interaction.followup.send(
                        translate("error_removing_value"), ephemeral=True
                    )

            # Associando o callback ao Select
            select.callback = remove_value_callback

            # Atualizando a view para incluir o Select
            cloned_view.clear_items()
            cloned_view.add_item(select)

            await interaction.edit_original_response(embed=update_embed(), view=cloned_view)



        async def general_setting_callback(interaction: Interaction, setting: Setting[Any]):
            await interaction.response.defer()
            cloned_view = interaction_view.clone()
            result = await setting.run(cloned_view)
            cloned_view.destroy()
            if result is not None:
                setting.value = result
                await interaction.edit_original_response(embed=update_embed(), view=interaction_view)

        async def confirm_callback(interaction: Interaction):
            await interaction.response.defer()
            embed = Embed(
                title=translate("settings.confirmed"),
                description=translate("settings.saved_successfully"),
                color=0x00FF00,
            )
            await interaction.edit_original_response(embed=embed, view=None)
            interaction_view.stop()

        add_button = Button(label=translate("add"), style=ButtonStyle.primary, custom_id="add")
        add_button.callback = add_callback

        remove_button = Button(label=translate("remove"), style=ButtonStyle.danger, custom_id="remove")
        remove_button.callback = remove_callback

        confirm_button = Button(label=translate("confirm"), style=ButtonStyle.success, custom_id="confirm")
        confirm_button.callback = confirm_callback
        

        for general_setting in self.general_settings:
            view.client.logger.info(f"General Seetting: {general_setting}, name: {general_setting.name}, id: {general_setting.id}")
            general_button = Button(
                label=translate_module(general_setting.name),
                style=ButtonStyle.secondary,
                custom_id=f"general_{general_setting.id}",
            )
            general_button.callback = lambda interaction, setting=general_setting: general_setting_callback(interaction, setting)
            interaction_view.add_item(general_button)

        interaction_view.add_item(add_button)
        interaction_view.add_item(remove_button)
        interaction_view.add_item(confirm_button)

        
        await view.update(embed=embed, components=interaction_view.children)

        await interaction_view.wait()
        return current_values

    def parse_to_field_list(self, translate_module: Optional[callable] = None) -> List[dict]:
        """
        Converts the array values into fields for the embed.
        """
        print(f"Valor do self.value: {self.value}")
        inlined = len(self.value) > 5
        fields = []
        for index, val in enumerate(self.value):
            if translate_module:
                parsed = (
                    self.parse_to_field(val, translate_module)
                    if self.parse_to_field
                    else (str(val) if not isinstance(val, dict) else "\n".join(f"{k}: {v}" for k, v in val.items()))
                )
            else:
                parsed = (
                    self.parse_to_field(val)
                    if self.parse_to_field
                    else (str(val) if not isinstance(val, dict) else "\n".join(f"{k}: {v}" for k, v in val.items()))
                )
            fields.append({"name": f"{index + 1}", "value": parsed, "inline": inlined})
        return fields
    
    def parse_to_field(self, value: Any, translator: Optional[callable] = None) -> str:
        """
        Converts a single array value into a displayable string format.
        """
        if hasattr(self.child, "parse_to_field") and callable(getattr(self.child, "parse_to_field")):
            if translator:
                return self.child.parse_to_field(value, translator=translator)
            else:
                return self.child.parse_to_field(value)
        elif isinstance(value, dict):
            return "\n".join(f"{k}: {v}" for k, v in value.items())
        else:
            return str(value)
        
    
    def parse_to_database(self, value: List[Any]) -> List[Any]:
        """
        Converts the array values into a format suitable for database storage.
        """
        if not isinstance(value, list):
            raise TypeError("Expected value to be a list.")

        self.logger = getattr(self, 'logger', None) or print  # Use logger if available, else fallback to print
        serialized_data = []

        for item in value:
            try:
                if hasattr(self.child, "parse_to_database") and callable(getattr(self.child, "parse_to_database")):
                    self.logger(f"Parsing item with child parse_to_database: {item}")
                    serialized_item = self.child.parse_to_database(item)
                    self.logger(f"Serialized item: {serialized_item}")
                else:
                    self.logger(f"Child does not have parse_to_database. Using raw item: {item}")
                    serialized_item = item
                serialized_data.append(serialized_item)
            except Exception as e:
                self.logger(f"Error while parsing item: {e}")
                raise

        return serialized_data


    def parse_from_database(self, config: List[Any]) -> List[T]:
        """
        Reconstructs the array values from the database.
        """
        if isinstance(config, list):
            return [self.child.parse(val) for val in config]
        return []

    async def parse(self, config: Any, client, guild_data: Any, guild: DiscordGuild) -> List[T]:
        """
        Parses the configuration data from the database or input.
        """
        if isinstance(config, list):
            parsed_values = []
            for item in config:
                parsed_values.append(await self.child.parse(item, client, guild_data, guild))
            return parsed_values
        return []

    def clone(self) -> "ArraySetting":
        return ArraySetting(
            name=self.name,
            description=self.description,
            id=self.id,
            child=self.child.clone(),
            value=self.value[:],
            embed_override=self.embed_override,
            general_settings=self.general_settings,
            update_fn=self.update_fn,
            locales=self.locales,
            module_name=self.module_name,
        )
