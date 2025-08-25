from typing import Any, Dict, Optional, Callable, List
from pathlib import Path
from discord.ext import commands
from discord import app_commands, Object
from logging import Logger
from settings.Setting import Setting
from shared.types import Manifest, ExtendedClient

class Module:
    """Container for a loaded feature module.

    Holds metadata (name, description, version, color), the module's interface
    returned by its `setup()` function, exported commands (text and slash),
    guild/user settings, and event listeners registered by the module.
    """

    def __init__(
        self,
        name: str,
        path: str,
        description: str,
        version: str,
        color: str,
        logger: Logger,
        init_func: Callable[["ExtendedClient", Any, Logger], Any],
        data: Manifest,
        commands: Optional[Dict[str, Dict[str, Any]]] = None,
        interfacer: Optional[Any] = None,
        settings: Optional[List[Setting[Any]]] = None,
        user_settings: Optional[List[Setting[Any]]] = None,
    ):
        """Initialize the module container.

        Args:
            name: Human‑readable module name.
            path: Absolute/relative filesystem path to the module directory.
            description: Short description of the module purpose.
            version: Semantic version string.
            color: Hex color (used in embeds or UI).
            logger: Logger used for this module.
            init_func: Callable returned by the module's `setup()` (executed via `initialize`).
            data: Parsed manifest describing folders and metadata.
            commands: Maps of commands grouped by kind, e.g. {"text": {}, "slash": {}}.
            interfacer: Arbitrary interface object/dict exported by the module.
            settings: Guild‑scoped settings declared by the module.
            user_settings: Member‑scoped settings declared by the module.
        """

        self.name = name
        self.path = path
        self.description = description
        self.version = version
        self.color = color
        self.logger = logger
        self.init_func = init_func
        self.data = data
        self.commands = commands or {"text": {}, "slash": {}}
        self.interfacer = interfacer or {}
        self.settings = settings or []
        self.user_settings = user_settings or []
        self.events: List[Dict[str, Callable]] = []  # Store registered events


    async def unload(self, bot: commands.Bot, sync: Optional[str] = None, guild_id: Optional[str] = None):
        """Unload this module's commands and events from the bot.

        Removes all registered text and slash commands and detaches listeners
        previously recorded via `register_event`.

        Args:
            bot: Discord bot/client instance.
            sync: Optional post‑unload sync mode: `"global"` or `"guild"`.
            guild_id: Guild id to sync if `sync == "guild"`.
        """
        for command_name, command in self.commands["text"].items():
            bot.remove_command(command.name)
            self.logger.info(f"Removed text command '{command_name}' from module '{self.name}'.")

        for command_name, command in self.commands["slash"].items():
            bot.tree.remove_command(command.name)
            self.logger.info(f"Removed slash command '{command_name}' from module '{self.name}'.")

        for event in self.events:
            try:
                bot.remove_listener(event["func"], event["event"])
                self.logger.info(f"Removed event listener '{event['event']}' from module '{self.name}'.")
            except Exception as e:
                self.logger.error(f"Failed to remove event listener '{event['event']}': {e}")

        self.commands = {"text": {}, "slash": {}}
        self.events = []

        # Sincronização opcional dos comandos
        if sync == "global":
            await bot.tree.sync()
            self.logger.info("Commands synchronized globally after unload.")
        elif sync == "guild" and guild_id:
            guild = Object(id=int(guild_id))
            await bot.tree.sync(guild=guild)
            self.logger.info(f"Commands synchronized for guild ID {guild_id} after unload.")


    async def reload(self, bot: commands.Bot, sync: Optional[str] = None, guild_id: Optional[int] = None):
        """Reload the module by unloading then re‑wiring commands and events.

        Args:
            bot: Discord bot/client instance.
            sync: Post‑reload sync mode: `'none'`, `'global'`, or `'guild'`.
            guild_id: Guild id to sync if `sync == 'guild'`.
        """
        await self.unload(bot)

        commands_folder = Path(self.path) / self.data.commands_folder
        base_package = f"modules.{self.name}.commands"
        await self.bot.command_handler.load_commands_from_folder(commands_folder, base_package, self)

        events_folder = Path(self.path) / self.data.events_folder
        if events_folder.exists():
            await self.bot.event_handler.load_events_from_module(self.name, Path(self.path), [events_folder])

        if sync == "global":
            await self.bot.tree.sync()
            self.logger.info(f"Slash commands globally synced after reloading module '{self.name}'.")
        elif sync == "guild" and guild_id:
            guild = Object(id=guild_id)
            await self.bot.tree.sync(guild=guild)
            self.logger.info(f"Slash commands synced for guild {guild_id} after reloading module '{self.name}'.")
        elif sync == "none" or sync is None:
            self.logger.info(f"No slash command synchronization performed for module '{self.name}'.")
            
        

    def register_event(self, event: str, func: Callable):
        """Record an event listener belonging to this module.

        The handler is later removed during `unload`.

        Args:
            event: Discord.py event name, e.g. `"on_message"`.
            func: Listener callable.
        """
        self.events.append({"event": event, "func": func})

    def add_setting(self, setting: Setting[Any]):
        """Add a guild‑scoped setting declared by the module.

        Args:
            setting: A `Setting` instance to append.
        """
        self.settings.append(setting)

    def add_user_setting(self, setting: Setting[Any]):
        """Add a member‑scoped setting declared by the module.

        Args:
            setting: A `Setting` instance to append.
        """
        self.user_settings.append(setting)

    async def initialize(self, client: "ExtendedClient", module_data: Any):
        """Execute the module’s initialization function.

        The `init_func` is the callable returned by the module's `setup()` and is
        responsible for returning the `interfacer` (helpers the module exposes).

        Args:
            client: Extended bot client.
            module_data: Arbitrary data passed from the loader.

        Returns:
            None. The `interfacer` is stored on the instance.
        """
        self.interfacer = await self.init_func(client, module_data, self.logger)
