# main.py

import argparse
import asyncio
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

import aiohttp
from discord import Intents, Activity, ActivityType, Object
from shared.types import ExtendedClient
from handlers.moduleHandler import ModuleHandler
from handlers.commandHandler import CommandHandler
from handlers.eventHandler import EventHandler
from db.db import MongoDBAsyncORM
from classes.managers.SettingsManager import SettingsManager
from classes.managers.GuildManager import GuildManager
from classes.managers.MemberManager import MemberManager
from classes.managers.PermissionsManager import PermissionsManager
from utils.Translator import Translator
from utils.EmojiManager import EmojiManager
from modules.Defaults.permissionNamespace import *

# -----------------------------------------------------------------------------
# Argument Parsing
# -----------------------------------------------------------------------------
def parse_args():
    """Parse command line arguments.

    Returns:
        Parsed arguments including the debug flag used to control logging verbosity.
    """
    parser = argparse.ArgumentParser(description="Discord Bot")
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    return parser.parse_args()

# -----------------------------------------------------------------------------
# Environment Setup
# -----------------------------------------------------------------------------
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
MONGODB_URI = os.getenv("MONGODB_URI")
OWNER_IDS = [322773637772083201, 840707271385284628, 930644246539665408]
TEST_GUILD_ID = 1160309121929728111  # Replace with your test guild ID

# -----------------------------------------------------------------------------
# Argument Parsing
# -----------------------------------------------------------------------------
args = parse_args()
DEBUG_MODE = args.debug

# -----------------------------------------------------------------------------
# Logging Configuration
# -----------------------------------------------------------------------------
log_level = logging.DEBUG if DEBUG_MODE else logging.INFO
logging.basicConfig(level=log_level, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logging.getLogger("discord").setLevel(logging.WARNING)
logging.getLogger("pymongo").setLevel(logging.WARNING)
logger = logging.getLogger("Bot")
logger.info("Logger initialized.")

# -----------------------------------------------------------------------------
# Bot Initialization
# -----------------------------------------------------------------------------
class Bot(ExtendedClient): 
    """Discord client with database, managers, handlers and i18n.

    Args:
        logger: Root logger used to create component specific child loggers.

    Attributes:
        session: Shared aiohttp session for outbound HTTP requests.
        db: MongoDBAsyncORM instance for persistence.
        detailed_help: Optional mapping for extended help entries.
        setting_cache: In‑memory cache for frequently accessed settings.
        ready: Indicates whether the bot finished the first on_ready cycle.
    """
    def __init__(self, logger: logging.Logger):
        intents = Intents.default()
        intents.message_content = True 

        super().__init__(intents=intents, logger=logger, command_prefix="j!", owner_ids=OWNER_IDS, help_command=None)

        self.session: aiohttp.ClientSession = None
        self.db = None
        self.detailed_help = {}
        self.setting_cache = {}
        self.ready = False

    async def setup_hook(self):
        """Initialize external services and internal subsystems before the bot is ready.

        This connects to MongoDB, prepares HTTP session, instantiates managers and handlers,
        registers default permission namespaces, loads modules, then offers slash command sync.
        """
        # Initialize MongoDB connection
        self.logger.info("Connecting to MongoDB...")
        try:
            self.db = MongoDBAsyncORM(uri=MONGODB_URI, db_name="GigaJoyce-Test")
            await self.db.create_index("members", [("id", 1), ("guildId", 1)], unique=True)
            self.db.members = self.db.get_collection("members")
            self.db.guilds = self.db.get_collection("guilds")
            self.db.users = self.db.get_collection("users")
            self.logger.info("Successfully connected to the database and collected data.")
        except Exception as e:
            self.logger.error(f"Failed to connect to MongoDB: {e}")
            return

        # Initialize HTTP session+
        self.session = aiohttp.ClientSession()

        # Initialize Managers
        self.logger.info("Initializing Managers...")
        self.guild_manager= GuildManager(self, self.logger)
        self.member_manager = MemberManager(self, self.logger)
        self.settings_manager = SettingsManager(self, self.logger)
        self.permission_manager = PermissionsManager(self, self.logger)
        self.logger.info("Managers initialized.")

        # Register default permission namespaces
        self.logger.info("Registering default permission namespaces...")
        self.permission_manager.register_node("Role.*", RolesNamespace)
        self.permission_manager.register_node("User.*", UsersNamespace)
        self.permission_manager.register_node("Channel.*", ChannelsNamespace)
        self.logger.info("Default permission namespaces registered.")

        # Initialize EmojiManager
        self.logger.info("Initializing EmojiManager...")
        translations_path = Path("./shared/emojis")
        self.emoji_manager = EmojiManager(self, translations_path, self.logger )
        self.logger.info("EmojiManager initialized.")
        
        # Initialize Translator
        self.logger.info("Initializing Translator...")
        translations_path = Path("./shared/translations")
        self.translator = Translator(self, translations_path, self.logger )
        self.logger.info("Translator initialized.")
  
        # Initialize Handlers
        self.logger.info("Initializing Handlers...")
        self.command_handler = CommandHandler(self, self.logger)
        self.event_handler = EventHandler(self, self.logger)
        self.logger.info("Handlers initialized.")

        # Initialize and load modules
        self.logger.info("Initializing ModuleHandler...")
        self.module_handler = ModuleHandler(self, self.logger)
        await self.module_handler.load_modules()
        self.logger.info("ModuleHandler initialized.")

        # Sync slash commands
        await self.sync_slash_commands()

    async def sync_slash_commands(self):
        """Interactively synchronize slash commands.

        Offers options to sync globally, to specific guilds, to the configured test guild,
        or to skip syncing. Consider a non‑interactive flag for headless deployments.
        """

        print("\nChoose a sync option for slash commands:")
        print("1. Sync globally (all servers)")
        print("2. Sync to a specific guild")
        print(f"3. Sync to the test guild (ID: {TEST_GUILD_ID})")
        print("4. Do not sync (skip this step)")
        sync_choice = input("Enter your choice (1/2/3/4): ").strip()
        # sync_choice = ""

        try:
            if sync_choice == "1":
                await self.tree.sync()
                self.logger.info("Slash commands synced globally.")
            elif sync_choice == "2":
                guild_ids = input("Enter guild IDs separated by commas: ").strip().split(",")
                for guild_id in guild_ids:
                    guild = Object(id=int(guild_id.strip()))
                    await self.tree.sync(guild=guild)
                    self.logger.info(f"Slash commands synced to guild {guild_id.strip()}.")
            elif sync_choice == "3":
                guild = Object(id=TEST_GUILD_ID)
                await self.tree.sync(guild=guild)
                self.logger.info(f"Slash commands synced to test guild {TEST_GUILD_ID}.")
            elif sync_choice == "4":
                self.logger.info("Slash command synchronization skipped.")
            else:
                print("Invalid choice. No sync performed.")
        except Exception as e:
            self.logger.error(f"Failed to sync slash commands: {e}")
            
    async def _populate_language_cache(self):
        """Preload per‑guild language into the Translator cache."""
        self.logger.info("Populating language cache...")
        # self.logger.info(f"Guilds: {self.guilds}")
        try:
            for guild in self.guilds:
                guild_id = str(guild.id)
                language = await self.guild_manager.get_language(guild_id)
                self.translator.language_cache[guild_id] = language
                self.logger.debug(f"Cached language '{language}' for guild '{guild_id}'")
        except Exception as e:
            self.logger.error(f"Error while populating language cache: {e}")
        self.logger.info("Language cache populated.")

    def get_logger(self, name: str) -> logging.Logger:
        """Return a child logger derived from the bot's root logger.

        Args:
            name: Name suffix for the child logger.

        Returns:
            A configured child logger.
        """
        return self.logger.getChild(name)

    async def on_ready(self):
        """Run one‑time tasks after the bot connects for the first time.

        Sets presence, warms the language cache, refreshes translation data,
        and flips the internal ready flag.
        """
        if not self.ready:
            self.logger.info(f"Bot connected as {self.user}")
            await self.change_presence(activity=Activity(type=ActivityType.watching, name="TechJoyce"))
            await self._populate_language_cache()
            await self.translator.refresh_translation_cache()
            self.ready = True

    async def close(self):
        """
        Gracefully close the bot, including HTTP sessions and database connections.
        """
        self.logger.info("Shutting down bot...")
        if self.session:
            await self.session.close()
        if self.db:
            await self.db.close()
        await super().close()

# -----------------------------------------------------------------------------
# Entry Point
# -----------------------------------------------------------------------------
async def main():
    if not TOKEN:
        logger.error("BOT_TOKEN not found in environment variables.")
        return

    bot = Bot(logger)  # Use the ExtendedClient-derived Bot
    try:
        await bot.start(TOKEN)
    except KeyboardInterrupt:
        logger.info("Bot interrupted by user.")
    except Exception as e:
        logger.exception(f"Unexpected exception: {e}")
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())
