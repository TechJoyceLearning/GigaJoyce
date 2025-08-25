from discord import (
    Embed,
    ButtonStyle,
    Interaction,
    Guild as DiscordGuild,
)
from discord.ui import Button
from typing import Dict, Any, Callable, List, Optional, TypeVar
from utils.InteractionView import InteractionView
from settings.Setting import Setting
from collections import OrderedDict
import inspect

T = TypeVar("T")


def map_schema(schema: Dict[str, Setting[Any]]) -> Dict[str, Setting[Any]]:
    """Normalize a schema to an ordered dict for deterministic iteration.

    Args:
        schema: Mapping of field key -> `Setting`.

    Returns:
        Ordered mapping suitable for stable rendering / iteration.
    """
    return OrderedDict(schema)


def chunk_arr(arr: List[Any], size: int) -> List[List[Any]]:
    """Split a list into chunks of size `size`.

    Args:
        arr: Input list.
        size: Chunk size.

    Returns:
        List of chunks.
    """
    return [arr[i:i + size] for i in range(0, len(arr), size)]


def check_filled_schema(current_config: "ComplexSetting") -> bool:
    """Check if all required schema fields are present in `.value`.

    Args:
        current_config: The complex setting instance.

    Returns:
        True if all required fields are filled; otherwise False.
    """
    for key, value in current_config.schema.items():
        if not current_config.value.get(key) and key not in (current_config.optionals or []):
            return False
    return True


def clone_schema(schema: Dict[str, T]) -> Dict[str, T]:
    """Deep‑clone a schema by calling `.clone()` on each child setting.

    Args:
        schema: Original mapping.

    Returns:
        New ordered mapping with cloned children.
    """
    return OrderedDict({key: value.clone() for key, value in schema.items()})


class ComplexSetting(Setting[Dict[str, Any]]):
    """A composite setting that edits a dict of child settings interactively.

    Renders one button per child field; clicking a button opens the child
    setting UI. A **Confirm** button validates required fields and finalizes.

    Attributes:
        schema: Ordered map of field key -> child `Setting`.
        update_fn: Callable (sync or async) that builds the current summary embed.
        optionals: Optional list of keys that are not required.
    """

    def __init__(
        self,
        name: str,
        description: str,
        id: str,
        schema: Dict[str, Setting[Any]],
        update_fn: Callable[[Dict[str, Any], InteractionView], Embed],
        optionals: Optional[List[str]] = None,
        value: Optional[Dict[str, Any]] = None,
        locales: Optional[bool] = False,
        module_name: Optional[str] = None,
    ):
        """Initialize a `ComplexSetting`.

        Args:
            name: Display name.
            description: Description for UX.
            id: Persistence key.
            schema: Child settings map (one button per key).
            update_fn: Function that summarizes current state into an embed.
            optionals: Keys that may be omitted.
            value: Initial value (defaults to `{}`).
            locales: Enable i18n of display strings.
            module_name: Module context for translations/emojis.
        """
        super().__init__(name=name, description=description, locales=locales, module_name=module_name, id=id, type_="complex")
        self.schema = map_schema(schema)
        self.update_fn = update_fn
        self.optionals = optionals
        self.value = value or {}
        self.locales = locales
        self.module_name = module_name

    async def run(self, view: InteractionView) -> Dict[str, Any]:
        """Render the complex editor and handle child edits/confirmation.

        Flow:
            1. Build a summary embed via `update_fn`.
            2. Render a button for each `schema` key; clicking opens the child.
            3. Confirm validates required fields via `check_filled_schema`.
            4. On success, closes the view and returns the dict.

        Args:
            view: Active `InteractionView`.

        Returns:
            Final dictionary value.
        """
        
        guild_id = str(view.interaction.guild.id)
        translate = await view.client.translator.get_translator(guild_id=guild_id)

        name, description, kwargs, schema = self.name, self.description, self.kwargs, self.schema

        if self.module_name and self.locales:
            translate_module = await view.client.translator.get_translator(guild_id=guild_id, module_name=self.module_name)
            name, description, kwargs = self.apply_locale(translate_module=translate_module)
            schema = {}
            if hasattr(self, "schema"):
                for key, child in self.schema.items():
                    self.propagate_locales(child=child)
                    if child.module_name and child.locales:
                        translate_module = await view.client.translator.get_translator(guild_id=guild_id, module_name=child.module_name)
                        schema[key] = child.apply_locale(translate_module=translate_module, clone=True)
                        view.client.logger.info(f"Key: {key}, name: {child.name}, description: {child.description}")            


        async def update_embed():
            """
            Updates the embed with the current state of the settings.
            """
            if inspect.iscoroutinefunction(self.update_fn):
                return await self.update_fn(self.value, view)
            else:
                return self.update_fn(self.value, view)

        async def handle_child(interaction: Interaction, key: str):
            """
            Handles interactions for child settings.
            """
            await interaction.response.defer()
            setting = schema.get(key)
            if not setting:
                view.client.logger.warning(f"No setting found for key: {key}")
                return

            current_value = self.value or {}
            clone = setting.clone()
            
            if current_value.get(key):
                clone.value = current_value[key]
            
            try:
                # clone.value = self.value.get(key)
                new_value = await clone.run(view.clone())
                if new_value is not None:
                    self.value[key] = new_value
                    view.client.logger.debug(f"Updated value for key {key}: {new_value}")
            finally:
                updated_embed = await update_embed()
                await view.update(embeds=[updated_embed], components=buttons)


        async def handle_confirm(interaction: Interaction):
            """
            Handles the confirmation button interaction.
            """
            await interaction.response.defer()

            if not check_filled_schema(self):
                error_embed = Embed(
                    title=translate("error.title"),
                    description=translate("error.incomplete"),
                    color=0xFF6767,
                )
                await interaction.message.edit(embed=error_embed, view=view)
                return

            success_embed = Embed(
                title=translate("settings.completed", setting_name=name or self.name),
                description=translate("settings.success"),
                color=0xFFFFFF,
            )
            await interaction.message.edit(embed=success_embed, view=None)
            view.stop()
            view.client.logger.info("Configuration confirmed and view stopped.")

        def rebuild_buttons():
            """
            Rebuilds the buttons for the parent view.
            """
            buttons = []
            for key, setting in schema.items():
                button = Button(
                    label=setting.name,
                    style=ButtonStyle.primary,
                    custom_id=key,
                )

                async def child_callback(inter: Interaction, key=key):
                    await handle_child(inter, key)

                button.callback = child_callback
                buttons.append(button)

            confirm_button = Button(
                label=translate("settings.confirm"),
                style=ButtonStyle.success,
                custom_id="confirm",
            )
            confirm_button.callback = handle_confirm
            buttons.append(confirm_button)
            return buttons

        embed = await update_embed()
        buttons = rebuild_buttons()
        await view.update(embed=embed, components=buttons)

        await view.wait()
        return self.value

    def parse_to_database(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepares the complex value for database storage.
        """
        self.logger = getattr(self, 'logger', None) or print  # Use logger if available, else fallback to print
        serialized_data = {}
        self.logger(f"Schema Items: {self.schema.items()}")
        for key, setting in self.schema.items():
            try:
                if setting.parse_to_database:
                    self.logger(f"Parsing key '{key}' with value: {value.get(key)}")
                    serialized_value = setting.parse_to_database(value.get(key))
                    self.logger(f"Serialized value for key '{key}': {serialized_value}")
                else:
                    self.logger(f"No parse_to_database method for key '{key}'. Using raw value.")
                    serialized_value = value.get(key)
                serialized_data[key] = serialized_value
            except Exception as e:
                self.logger(f"Error while parsing key '{key}': {e}")
                raise

        return serialized_data


    async def parse(self, config: Any, client, guild_data: Any, guild: DiscordGuild) -> Dict[str, Any]:
        """
        Parses the configuration data from the database or input.
        """
        if isinstance(config, dict):
            parsed_values = {}
            for key, setting in self.schema.items():
                if setting.parse:
                    parsed_values[key] = await setting.parse(config.get(key), client, guild_data, guild)
                else:
                    parsed_values[key] = config.get(key)
            return parsed_values
        return {}

    def clone(self) -> "ComplexSetting":
        return ComplexSetting(
            name=self.name,
            description=self.description,
            id=self.id,
            schema=clone_schema(self.schema),
            update_fn=self.update_fn,
            optionals=self.optionals,
            value=self.value.copy(),
            locales=self.locales,
            module_name=self.module_name,
        )
