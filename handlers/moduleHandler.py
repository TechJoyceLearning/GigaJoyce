import json
import importlib
from pathlib import Path
from typing import Dict, Any, Optional, List
from logging import Logger
from discord.ext import commands
from classes.structs.Module import Module
from shared.types import ExtendedClient
import sys


class ModuleHandler:
    """Discover, initialize, and manage feature modules.

    Scans the `./modules` directory, reads each module's `manifest.json`, executes the
    module's `initFile` (usually `main.py`) and wires exported commands, events,
    interface hooks and settings into the running bot.
    """

    def __init__(self, bot: ExtendedClient, logger: Logger):
        """Initialize the handler.

        Args:
            bot: The extended Discord client.
            logger: Logger used for diagnostics.
        """
        self.bot = bot
        self.logger = logger
        self.modules_path = Path("./modules")
        self.loaded_modules: Dict[str, Module] = {}
        
    def register_permissions(self, module_name: str, permissions: List[str]):
        """Register a list of permission nodes on behalf of a module.

        Note:
            This implementation registers nodes that always resolve to `True`.
            Replace the lambda with proper checks (or namespace handlers) if your
            modules rely on real permission enforcement.

        Args:
            module_name: Name of the module requesting the nodes.
            permissions: Permission paths (e.g., "Feature.Admin.Purge", "Role.*").
        """
        for permission in permissions:
            try:
                self.bot.permission_manager.register_node(permission, lambda client, node, member, channel: True)
                self.logger.info(f"Permission '{permission}' registered for module '{module_name}'.")
            except Exception as e:
                self.logger.error(f"Failed to register permission '{permission}' for module '{module_name}': {e}")


    async def load_modules(self, specific_module: Optional[str] = None):
        """Load modules from disk and attach their commands/events.

        Walks `self.modules_path`, reads each `manifest.json`, executes the module
        setup file, builds a :class:`Module` instance and delegates:
          - commands to `CommandHandler.load_commands_from_folder`
          - events to `EventHandler.load_events_from_module`

        Args:
            specific_module: If provided, load only that folder name; otherwise load all.
        """
        modules_path = self.modules_path

        for module_folder in modules_path.iterdir():
            if not module_folder.is_dir():
                continue
            
            if specific_module and module_folder.name != specific_module:
                continue

            manifest_path = module_folder / "manifest.json"
            if not manifest_path.exists():
                self.logger.warning(f"Manifest not found for module: {module_folder.name}")
                continue

            # Load the module's manifest
            try:
                with open(manifest_path, "r", encoding="utf-8") as manifest_file:
                    manifest = json.load(manifest_file)
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse manifest for module {module_folder.name}: {e}")
                continue

            # Extract module information
            name = manifest.get("name", module_folder.name)
            self.logger.info(f"Loading {name} module...")
            description = manifest.get("description", "No description provided.")
            version = manifest.get("version", "1.0.0")
            color = manifest.get("color", "#FFFFFF")
            setup_file = module_folder / manifest.get("initFile", "main.py")

            commands_folder = module_folder / manifest.get("commandsFolder", "commands")
            events_folder = module_folder / manifest.get("eventsFolder", "events")
            translations_folder = module_folder / manifest.get("translationsFolder", "translations")

            base_package = f"modules.{module_folder.name}.commands"

            # Execute the setup function and retrieve interface and settings
            setup_data = self._execute_setup(setup_file)
            if setup_data is None:
                self.logger.error(f"Setup failed for module {name}. Skipping module.")
                continue

            interface = setup_data.get("interface", {})
            settings = setup_data.get("settings", [])
            user_settings = setup_data.get("userSettings", [])

            # Create the module instance
            module = Module(
                name=name,
                path=str(module_folder),
                description=description,
                version=version,
                color=color,
                logger=self.logger,
                init_func=setup_data.get("initFunc"),
                data=manifest,
                commands={"text": {}, "slash": {}},
                interfacer=interface,
                settings=settings,
                user_settings=user_settings,
            )

            if self.bot.command_handler:
                await self.bot.command_handler.load_commands_from_folder(commands_folder, base_package, module)
            else:
                self.logger.error("CommandHandler is not initialized.")

            # Load events
            if self.bot.event_handler:
                self.bot.event_handler.load_events_from_module(name, events_folder, module)
            else:
                self.logger.error("EventHandler is not initialized.")

            # Store the module in the loaded modules dictionary
            self.loaded_modules[name] = module
            self.logger.info(f"Successfully loaded module: {name}")

        self.bot.modules = self.loaded_modules

    def _execute_setup(self, setup_file_path: Path) -> Optional[Dict[str, Any]]:
        """Execute the `setup(bot, logger)` function exported by the module init file.

        The `setup` function should return a dict with any of:
            - "interface": an object or dict with callable utilities the module exposes
            - "settings": a list of guild‑scoped Setting instances
            - "userSettings": a list of member‑scoped Setting instances
            - "initFunc": optional callable to run after loading (stored on Module)

        Args:
            setup_file_path: Absolute path to the module's init file.

        Returns:
            A dict with setup data, or `None` if the init file cannot be executed
            or does not return a proper mapping.
        """
        if not setup_file_path.exists():
            self.logger.warning(f"Init file not found: {setup_file_path}")
            return None

        module_name = f"init_{setup_file_path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, setup_file_path)
        if spec is None:
            self.logger.error(f"Failed to load init file: {setup_file_path}")
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        loader = spec.loader
        if loader is None:
            self.logger.error(f"Loader not found for init file: {setup_file_path}")
            return None

        try:
            loader.exec_module(module)
            setup_func = getattr(module, "setup", None)
            if callable(setup_func):
                setup_data = setup_func(self.bot, self.logger)
                if isinstance(setup_data, dict):
                    return setup_data
                else:
                    self.logger.error(f"Setup function in {setup_file_path} did not return a dictionary.")
                    return None
            else:
                self.logger.error(f"No callable 'setup' function found in {setup_file_path}.")
                return None
        except Exception as e:
            self.logger.error(f"Error executing setup function in {setup_file_path}: {e}")
            return None

    async def unload_modules(self):
        """Unload all modules that were previously loaded.

        Calls each module's `unload(bot)` coroutine (if implemented), removes it
        from the in‑memory registry, and logs results.
        """
        for module_name, module in list(self.loaded_modules.items()):
            try:
                await module.unload(self.bot)
                del self.loaded_modules[module_name]
                self.logger.info(f"Unloaded module: {module_name}")
            except Exception as e:
                self.logger.error(f"Failed to unload module {module_name}: {e}")

    async def reload_modules(self):
        """Reload all modules by unloading then loading them again.

        Useful during development or when hot‑reloading code on disk.
        """
        await self.unload_modules()
        await self.load_modules()