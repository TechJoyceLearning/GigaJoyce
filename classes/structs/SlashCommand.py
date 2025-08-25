# classes/structs/SlashCommand.py

import logging
from discord import app_commands
from typing import Callable, Optional, Any

class SlashCommand:
    """Descriptor for a Discord slash command.

    Wraps an `app_commands.Command`, optional autocomplete function, and some
    visibility flags used by help/registration flows.
    """

    def __init__(
        self,
        data: app_commands.Command,
        func: Optional[Callable[..., Any]] = None,
        global_cmd: bool = False,
        auto_complete_func: Optional[Callable[..., Any]] = None,
        logger: Optional[logging.Logger] = None,
        module: Optional[str] = None,
        disabled: bool = False
    ):
        """Create a slash command descriptor.

        Args:
            data: The `app_commands.Command` object.
            func: Optional explicit callback; defaults to `data.callback`.
            global_cmd: Whether it should be synced globally by default.
            auto_complete_func: Optional autocomplete callback.
            logger: Optional logger; defaults to a name derived from the command.
            module: Owning module name, if applicable.
            disabled: If True, the command should not appear or be registered.
        """
        self.data = data
        self.func = func or data.callback
        self.global_cmd = global_cmd
        self.auto_complete_func = auto_complete_func
        self.logger = logger or logging.getLogger(data.name)
        self.module = module
        self.disabled = disabled

        self.logger.debug(f"Initialized SlashCommand: {data.name}, func: {self.func.__name__}")

    def register_to_tree(self, bot_tree: app_commands.CommandTree):
        """Register the slash command into a command tree.

        Args:
            bot_tree: The bot's `CommandTree` to add the command to.
        """
        bot_tree.add_command(self.data)
        self.logger.debug(f"Registered slash command: {self.data.name}")


    @property
    def should_appear_in_help(self) -> bool:
        """Return whether the command should appear in help UIs."""
        return not self.disabled
