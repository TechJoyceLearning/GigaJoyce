# handlers/eventHandler.py

import importlib.util
import sys
from pathlib import Path
from discord.ext import commands
from logging import Logger
from classes.structs.Module import Module

class EventHandler:
    """Dynamic loader/registrar for module events.

    Imports Python files from each module's `events` folder and registers exported
    event listeners on the bot using `bot.add_listener`.
    """

    def __init__(self, bot: commands.Bot, logger: Logger):
        """Initialize the handler.

        Args:
            bot: Discord.py bot (or ExtendedClient).
            logger: Logger used for diagnostics.
        """
        self.bot = bot
        self.logger = logger

    def load_events_from_module(self, module_name: str, events_path: Path, module: Module):
        """Import and register event listeners from a module's `events` directory.

        Each event file may expose an `exports` list of dicts with keys:
            - "event": Discord.py event name (e.g., "on_message")
            - "func": callable listener to be registered via `bot.add_listener`

        Args:
            module_name: Module's folder name (used to build import name).
            events_path: Path to the module's events directory.
            module: The owning :class:`Module` to record listeners against.
        """
        if not events_path.exists() or not events_path.is_dir():
            self.logger.warning(f"Events folder '{events_path}' not found for module '{module_name}'.")
            return

        # Recursively search for .py files in the events directory
        for event_file in events_path.rglob("*.py"):
            if event_file.stem.startswith("_"):  # Skip special files like __init__.py
                continue

            # Import the event module
            
            event_module_name = f"modules.{module_name}.events.{event_file.stem}"  # Inclui 'modules.'

            spec = importlib.util.spec_from_file_location(event_module_name, event_file)
            if spec is None:
                self.logger.error(f"Failed to load event '{event_file}' in module '{module_name}'.")
                continue

            event_module = importlib.util.module_from_spec(spec)
            sys.modules[event_module_name] = event_module
            loader = spec.loader
            if loader is None:
                self.logger.error(f"Loader not found for event '{event_file}' in module '{module_name}'.")
                continue

            try:
                loader.exec_module(event_module)
            except Exception as e:
                self.logger.error(f"Error executing event '{event_file}' in module '{module_name}': {e}")
                continue

            # Register event listeners
            if hasattr(event_module, "exports"):
                exports = getattr(event_module, "exports")
                if isinstance(exports, list):
                    for export in exports:
                        if isinstance(export, dict):
                            event_name = export.get("event")
                            func = export.get("func")
                            if event_name and callable(func):
                                try:
                                    self.bot.add_listener(func, event_name)
                                    module.register_event(event_name, func)  # Register in the module
                                    self.logger.info(f"Registered event '{event_name}' from module '{module_name}'.")
                                except Exception as e:
                                    self.logger.error(f"Error registering event '{event_name}' from module '{module_name}': {e}")
