from discord import app_commands, Interaction
from typing import Callable

class Subcommand:
    """Lightweight descriptor for a dynamic subcommand.

    Holds the metadata required to attach a subcommand under a parent group
    at a later time (via the CommandHandler's deferred processing).
    """

    def __init__(self, name: str, description: str, callback: Callable, parent_name: str = None):
        """Create a subcommand descriptor.

        Args:
            name: Subcommand name (leaf).
            description: Short description for help/UX.
            callback: Async function that will execute the subcommand.
            parent_name: The parent slash group name this subcommand belongs to.
        """
        self.name = name
        self.description = description
        self.callback = callback
        self.parent_name = parent_name

    def to_app_command(self) -> app_commands.Command:
        """Convert this descriptor into a Discord app command.

        Returns:
            A constructed `app_commands.Command` using the stored metadata.
        """
        return app_commands.Command(
            name=self.name,
            description=self.description,
            callback=self.callback,
        )
