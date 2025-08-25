from typing import Callable, List, Optional
import logging
from discord.ext import commands

class Command:
    """Decorator-style wrapper for a text (prefix) command.

    Captures a function and registers it into `discord.ext.commands` using the
    provided metadata (name, description, aliases).
    """

    def __init__(
        self,
        name: str,
        description: str,
        how_to_use: str,
        aliases: Optional[List[str]] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """Create a command descriptor.

        Args:
            name: Command name (prefix-based).
            description: Short description for help.
            how_to_use: Usage string to display in help.
            aliases: Optional list of alternate names.
            logger: Optional logger; defaults to a logger named after `name`.
        """
        self.name = name
        self.description = description
        self.how_to_use = how_to_use
        self.aliases = aliases or []
        self.logger = logger or logging.getLogger(name)
        self.func: Optional[Callable] = None  # Placeholder for the decorated function

    def __call__(self, func: Callable) -> "Command":
        """Decorator entrypoint to bind the underlying function.

        Args:
            func: The implementation function.

        Returns:
            The same `Command` instance, now pointing to `func`.
        """
        self.func = func  # Capture the decorated function
        return self

    def get_command_function(self) -> Callable:
        """Return the bound implementation function.

        Raises:
            RuntimeError: If no function has been bound via the decorator.
        """
        if not self.func:
            raise RuntimeError(f"Command '{self.name}' has no associated function.")
        return self.func

    def register(self, bot: commands.Bot):
        """Register this command with the bot's command registry.

        Wraps the original function into a discord.py command callback and
        attaches it to the bot.

        Args:
            bot: The Discord bot to register against.
        """
        async def wrapped(ctx, *args, **kwargs):
            if self.func is None:
                raise RuntimeError(f"Command '{self.name}' has no associated function to call.")
            await self.func(
                client=bot,
                message=ctx.message,
                args=args,
                profile=None,
                logger=self.logger,
                guild=ctx.guild,
                interfacer=None,
                used_name=self.name,
            )

        bot.command(
            name=self.name,
            description=self.description,
            aliases=self.aliases,
        )(wrapped)

        print(f"Registered command '{self.name}' with the bot.")
