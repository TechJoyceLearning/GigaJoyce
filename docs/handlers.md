# Handlers

This section explains how handlers glue the bot, modules, and Discord together.

## Responsibilities at a glance
- **ModuleHandler**: discovers module folders, reads `manifest.json`, executes the
  module's `setup(bot, logger)` function, and wires commands/events.
- **CommandHandler**: imports command files and registers slash, prefix, and Cog exports.
- **EventHandler**: imports event files and registers listeners exposed via an `exports` list.

## Export patterns

### Commands folder
Each `modules/<name>/commands/**/*.py` file can expose an `exports` list with any of:
- `discord.app_commands.Command` or `discord.app_commands.Group`
- `discord.ext.commands.Command`
- `discord.ext.commands.Cog` **instance**
- `Subcommand`
- `CommandHelp`
- A class with `async def setup(bot)`
- A Cog class without `setup`

### Events folder
Each event file exposes an `exports` list of dicts with keys `event` and `func`.
