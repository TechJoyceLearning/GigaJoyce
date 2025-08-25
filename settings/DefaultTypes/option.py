from discord import (
    Embed,
    ButtonStyle,
    Interaction,
    ActionRow,
)
from typing import List, Optional, TypeVar, Generic, Awaitable, Callable, Any
from utils.InteractionView import InteractionView
from settings.Setting import Setting
from discord.ui import  Button, View

T = TypeVar("T")


class OptionSetting(Setting[T], Generic[T]):
    """Single-choice setting built from a list of child `Setting`s.

    Each option is represented by a child `Setting` used only for metadata
    (name/id/value). The user selects one option via buttons.
    """

    def __init__(
        self,
        name: str,
        description: str,
        id: str,
        options: List[Setting[T]],
        value: Optional[T] = None,
        permission: Optional[T] = None,
        locales: Optional[bool] = False,
        module_name: Optional[str] = None
    ):
        """Initialize an OptionSetting.

        Args:
            name: Display name.
            description: UX description.
            id: Persistence key.
            options: List of child settings representing choices.
            value: Initial selected value.
            permission: Optional permission flag/bit.
            locales: Enable i18n of display strings.
            module_name: Module context for translations.
        """
        super().__init__(name=name, description=description, id=id, locales=locales, module_name=module_name, permission=permission, type_="option")
        self.options = options
        self.value = value
        self.permission = permission
        self.locales = locales
        self.module_name = module_name
        
        if self.locales and self.module_name:
            self._apply_locales_to_options()

    def _apply_locales_to_options(self):
        """
        Propaga as configurações de 'locales' e 'module_name' para as opções.
        """
        for option in self.options:
            if isinstance(option, Setting):
                option.locales = self.locales
                option.module_name = self.module_name

    def apply_locale(self, translate_module: Callable[[str], str]):
        """
        Applies the modular translation to all fields, including options.
        """
        super().apply_locale(translate_module) 

        for option in self.options:
            if isinstance(option, Setting):
                option.apply_locale(translate_module)

    async def run(self, view: InteractionView) -> T:
        """Render the selector and return the chosen option's value.

        Args:
            view: Active interaction view.

        Returns:
            The selected option value.

        Raises:
            TimeoutError: When the user does not choose in time.
        """
        language = await view.client.translator.get_language(view.interaction.guild.id)
        translate = view.client.translator.get_global(language)
        
        if self.module_name and self.locales:
            translate_module = (
                view.client.translator.get_module_translations(self.module_name, language)
                if self.locales
                else lambda key, **kwargs: key
            )

            self.apply_locale(translate_module)

        buttons = [
            Button(
                label=option.name,
                custom_id=option.id,
                style=ButtonStyle.primary,
            )
            for option in self.options
        ]
        rows = [ActionRow(*buttons)]

        rows_view = View()
        rows_view.add_item(rows)
        # Embed with options description
        embed = Embed(
            title=translate("option_setting.title", setting_name=self.name),
            description=self.description,
            color=0xFFFFFF,
        )
        await view.update({"embeds": [embed], "components": rows_view.children})

        # Await user selection
        result = await self._await_selection(view, translate)
        if result is None:
            embed.description = translate("option_setting.timeout")
            await view.update({"embeds": [embed], "components": []})
            raise TimeoutError(translate("option_setting.timeout_error"))

        return result

    async def _await_selection(self, view: InteractionView, translate: Callable[[str, Any], str]) -> Optional[T]:
        """
        Handles the selection of an option asynchronously.
        """
        selection = None

        def handle_selection(inter: Interaction):
            nonlocal selection
            selected_id = inter.data["custom_id"]
            selected_option = next((opt for opt in self.options if opt.id == selected_id), None)
            if selected_option:
                selection = selected_option.value

        view.on("any", handle_selection)
        await view.wait()

        if selection is not None:
            selected_option = next((opt for opt in self.options if opt.value == selection), None)
            success_embed = Embed(
                title=translate("option_setting.selected"),
                description=translate("option_setting.success", option_name=selected_option.name),
                color=0x00FF00,
            )
            await view.update({"embeds": [success_embed], "components": []})

        return selection

    def parse_to_database(self, value: T, translator: Optional[callable] = None) -> str:
        """
        Parse the selected value for database storage.
        """
        return str(value)

    def parse_from_database(self, config: str) -> T:
        """
        Parse the value from the database configuration.
        """
        return next((opt.value for opt in self.options if str(opt.value) == config), None)

    def parse_to_field(self, value: T) -> str:
        """
        Parse the value to a displayable string format.
        """
        option = next((opt for opt in self.options if opt.value == value), None)
        return option.name if option else "N/A"

    def clone(self) -> "OptionSetting[T]":
        """Return a clone of this selector (options are shallow‑cloned).

        Notes:
            We clone each child option if it has `clone()`, otherwise we reuse
            the instance (safe for read‑only metadata).
        """
        cloned_options: List[Setting[T]] = [
            (opt.clone() if hasattr(opt, "clone") and callable(opt.clone) else opt)
            for opt in self.options
        ]
        return OptionSetting(
            name=self.name,
            description=self.description,
            id=self.id,
            options=cloned_options,
            value=self.value,
            permission=self.permission,
            locales=self.locales,
            module_name=self.module_name,
        )