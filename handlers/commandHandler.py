from discord.ext import commands
from discord import app_commands
from pathlib import Path
from typing import Any
import importlib.util
import sys
from logging import Logger
from inspect import isclass, iscoroutinefunction
from classes.structs.Subcommand import Subcommand
from classes.structs.CommandHelp import CommandHelp
from classes.structs.Module import Module


class CommandHandler:
    """Central registry and loader for module commands.

    Dynamically imports command files, collects exported objects, and registers:
      - Slash commands / groups into the app command tree
      - Prefix commands into the bot
      - Cogs (async add + bookkeeping)
      - Detailed help entries
      - Deferred Subcommand attachments (processed later)
    """

    def __init__(self, bot: commands.Bot, logger: Logger):
        """Initialize the handler.

        Args:
            bot: Discord.py bot (or ExtendedClient).
            logger: Logger used for diagnostics.
        """
        self.bot = bot
        self.logger = logger
        self.pending_subcommands = []  # Queue for subcommands waiting for parent groups
        self.detailed_help = {}  # Store detailed help information

    async def load_commands_from_folder(self, folder: Path, base_package: str, module: Module):
        """Import and register all command files found under a folder.

        Recursively walks `folder`, imports each `.py` file as a module under
        `base_package`, then processes its `exports` iterable (if present).

        Args:
            folder: Directory containing command files.
            base_package: Python package prefix to assign to imports (e.g. "modules.foo.commands").
            module: The owning :class:`Module` instance for bookkeeping.
        """
        if not folder.exists():
            self.logger.warning(f"Commands folder '{folder}' does not exist for module '{module.name}'.")
            return

        for command_file in folder.rglob("*.py"):
            if "__pycache__" in command_file.parts:
                continue
            if command_file.stem.startswith("_"):
                continue

            # Determine the module name based on the relative path
            relative_path = command_file.relative_to(folder).with_suffix("")  # Remove .py
            module_name = f"{base_package}.{'.'.join(relative_path.parts)}"

            # Load the module
            spec = importlib.util.spec_from_file_location(module_name, command_file)
            if spec is None:
                self.logger.error(f"Failed to load command module: {command_file} for module '{module.name}'.")
                continue

            module_obj = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module_obj
            loader = spec.loader
            if loader is None:
                self.logger.error(f"Loader not found for command module: {command_file} in module '{module.name}'.")
                continue

            try:
                loader.exec_module(module_obj)
            except Exception as e:
                self.logger.error(f"Error executing module '{module_name}': {e}")
                continue

            # Process the exported items in the module
            exports = getattr(module_obj, "exports", [])
            for item in exports:
                await self.process_export(item, module)

    async def process_export(self, export: Any, module: Module):
        """Process a single exported symbol from a command file.

        Supported export types:
            - `app_commands.Command` / `app_commands.Group` → slash registration
            - `commands.Command` → prefix command registration
            - `commands.Cog` instance → async add, track commands
            - `CommandHelp` → stored in `bot.detailed_help`
            - `Subcommand` → queued and attached by `process_pending_subcommands`
            - A class with `async def setup(bot)` → invoked
            - A subclass of `commands.Cog` without `setup` → instantiated and added

        Args:
            export: The exported object to register.
            module: The owning module.
        """
        if isinstance(export, app_commands.Command) or isinstance(export, app_commands.Group):
            self.register_slash_command(export, module)
        elif isinstance(export, commands.Command):
            self.register_regular_command(export, module)
        elif isinstance(export, commands.Cog):
            await self._add_cog_async(export, module)
        elif isinstance(export, CommandHelp):
            self.bot.detailed_help[export.name] = export
            self.logger.info(f"Registered detailed help for '{export.name}' in module '{module.name}'.")
        elif isinstance(export, Subcommand):
            self.register_subcommand(export, module)
        elif isclass(export):
            setup_method = getattr(export, "setup", None)
            if setup_method:
                if iscoroutinefunction(setup_method):
                    await setup_method(self.bot)
                    self.logger.info(f"Async setup invoked for '{export.__name__}' in module '{module.name}'.")
                else:
                    self.logger.error(f"Setup method for '{export.__name__}' is not async. Skipping in module '{module.name}'.")
            else:
                if issubclass(export, commands.Cog):
                    try:
                        cog_instance = export(self.bot)
                        await self._add_cog_async(cog_instance, module)
                    except Exception as e:
                        self.logger.error(f"Failed to instantiate cog '{export.__name__}' in module '{module.name}': {e}")
                else:
                    self.logger.error(
                        f"Unrecognized class '{export.__name__}' in module '{module.name}'. It has no setup method and is not a Cog."
                    )
        else:
            self.logger.warning(f"Unrecognized export: {export} in module '{module.name}'")

    def register_slash_command(self, command: app_commands.Command | app_commands.Group, module: Module):
        """Register a slash command or group into the bot's command tree.

        Also records the command under `module.commands["slash"]`.

        Args:
            command: The slash command or group to add.
            module: The owning module used for bookkeeping.
        """
        if isinstance(command, app_commands.Group):
            self.bot.tree.add_command(command)
            self.logger.info(f"Registered command group '{command.name}' in module '{module.name}'.")
            module.commands["slash"][command.name] = command
        else:
            self.bot.tree.add_command(command)
            self.logger.info(f"Registered slash command '{command.name}' in module '{module.name}'.")
            module.commands["slash"][command.name] = command

    def register_regular_command(self, command: commands.Command, module: Module):
        """Register a text (prefix) command into the bot.

        Also records the command under `module.commands["text"]`.

        Args:
            command: The command object to add via `bot.add_command`.
            module: The owning module used for bookkeeping.
        """
        self.bot.add_command(command)
        self.logger.info(f"Registered regular command '{command.name}' in module '{module.name}'.")
        module.commands["text"][command.name] = command

    def register_subcommand(self, subcommand: Subcommand, module: Module):
        """Queue a `Subcommand` for attachment to its parent group.

        If the parent group does not yet exist, the subcommand is queued until
        `process_pending_subcommands()` creates or finds the parent.

        Args:
            subcommand: The subcommand descriptor.
            module: The owning module used for bookkeeping.
        """
        if subcommand.parent_name:
            self.pending_subcommands.append({
                "command": app_commands.Command(
                    name=subcommand.name,
                    description=subcommand.description,
                    callback=subcommand.callback,
                ),
                "parent_name": subcommand.parent_name,
                "module": module  # Associar o módulo ao subcomando
            })
            self.logger.info(f"Queued subcommand '{subcommand.name}' for parent '{subcommand.parent_name}' in module '{module.name}'.")
        else:
            self.logger.warning(f"Subcommand '{subcommand.name}' has no parent group specified in module '{module.name}'.")

    def process_pending_subcommands(self):
        """Attach queued subcommands to their parent groups.

        If a parent group is missing, creates it automatically and adds it to
        the app command tree. Updates `module.commands["slash"]` accordingly.
        """
        for item in self.pending_subcommands[:]:
            parent = self.bot.tree.get_command(item["parent_name"])
            module = item["module"]
            if not parent:
                # Automatically create a parent group if it doesn't exist
                parent = app_commands.Group(
                    name=item["parent_name"],
                    description=f"Group for {item['parent_name']} commands.",
                )
                self.bot.tree.add_command(parent)
                self.logger.info(f"Created missing parent group '{item['parent_name']}' in module '{module.name}'.")

            if isinstance(parent, app_commands.Group):
                parent.add_command(item["command"])
                self.logger.info(f"Added subcommand '{item['command'].name}' to group '{item['parent_name']}' in module '{module.name}'.")
                # Associar o subcomando ao módulo
                module.commands["slash"][item["command"].name] = item["command"]
                self.pending_subcommands.remove(item)
            else:
                self.logger.warning(
                    f"Parent group '{item['parent_name']}' is not a valid group for subcommand '{item['command'].name}' in module '{module.name}'."
                )

    async def _add_cog_async(self, cog_instance: commands.Cog, module: Module):
        """Add a Cog asynchronously and record its commands.

        After adding the Cog, enumerates both text and slash commands available
        from the Cog and stores them under `module.commands`.

        Args:
            cog_instance: Instantiated Cog to add.
            module: The owning module used for bookkeeping.
        """
        try:
            await self.bot.add_cog(cog_instance)
            text_commands = cog_instance.get_commands()
            slash_commands = cog_instance.get_app_commands()
            
            for command in text_commands:
                module.commands["text"][command.name] = command

            for slash in slash_commands:
                module.commands["slash"][slash.name] = slash
                
            self.logger.info(f"Registered cog '{type(cog_instance).__name__}' in module '{module.name}'.")
        except Exception as e:
            self.logger.error(f"Failed to register cog '{type(cog_instance).__name__}' in module '{module.name}': {e}")
