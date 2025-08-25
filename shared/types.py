from typing import (
    Dict, Callable, Union, Awaitable, Any, Optional, List, TypedDict, DefaultDict, TYPE_CHECKING
)
from discord import (
    Guild as DiscordGuild, Member as GuildMember, Role, TextChannel, Interaction, Message
)
from discord.ext.commands import Bot
import logging
from collections import defaultdict
from shared.async_lock import AsyncLock
import asyncio

if TYPE_CHECKING:
    from classes.structs.Guild import Guild
    from classes.structs.Member import Member
    from classes.structs.Command import Command
    from classes.structs.SlashCommand import SlashCommand
    from classes.structs.Module import Module
    from classes.managers.MemberManager import MemberManager
    from classes.managers.GuildManager import GuildManager
    from classes.managers.SlashManager import SlashManager
    from classes.managers.SettingsManager import SettingsManager
    from classes.managers.FlagsManager import FlagsManager
    from classes.managers.PermissionsManager import PermissionsManager
    from handlers.moduleHandler import ModuleHandler
    from handlers.commandHandler import CommandHandler
    from handlers.eventHandler import EventHandler
    from utils.Translator import Translator
    from utils.EmojiManager import EmojiManager
    from utils.InteractionView import InteractionView
    from utils.MessageView import MessageView
    from db.db import MongoDBAsyncORM


class OverrideNode(TypedDict):
    allow: List[str]
    deny: List[str]


PermissionOverrideTree = Dict[str, Union["PermissionOverrideTree", OverrideNode]]


PermissionNode = Callable[
    [
        "ExtendedClient",
        str,
        GuildMember,
        Optional[TextChannel],
    ],
    Awaitable[bool]
]


Schema = Dict[str, Union[str, int, float, bool, list, dict]] 
    

class RawManifest(TypedDict):
    name: str
    description: str
    version: str
    color: str
    schemaDataFile: Optional[Union[str, Schema]]
    initFile: str
    eventsFolder: Optional[str]
    commandsFolder: str
    translationsFolder: Optional[str]
    emojisFolder: Optional[str]    
    disabled: Optional[bool]

class Manifest(RawManifest):
    data: RawManifest


# Tipo para atualização de mensagens em views
class MessageViewUpdate(TypedDict):
    content: Optional[str]
    embeds: Optional[List[Dict[str, Any]]]
    components: Optional[List[Dict[str, Any]]]
    ephemeral: Optional[bool]


class ExtendedClient(Bot):
    """Discord client extended.

    Provides high-level services shared across the bot, such as logging, in-memory
    caches, async locks, managers, a lightweight internal event bus, and command middleware.

    Args:
        logger: Root logger used to create component-specific child loggers.

    Attributes:
        db: Async MongoDB connection (see :class:`MongoDBAsyncORM`).
        ready: Whether the first `on_ready` cycle has completed.
        detailed_help: Optional mapping for extended help entries.
        view_registry: Registry of interactive views keyed by an identifier.
        setting_cache: In-memory cache for frequently accessed settings.
        logger: Root logger instance.
        global_lock: Process-wide async lock for critical sections.
        flags_manager: Flags manager for feature toggles.
        member_manager: Manager for guild members.
        guild_manager: Manager for guild-level data.
        slash_manager: Manager for slash commands.
        permission_manager: Permission manager and resolver.
        settings_manager: Settings manager and storage adapter.
        command_middleware: List of async middlewares invoked before command execution.
            If any middleware returns False, the command is aborted.
        modules: Loaded modules keyed by module name.
        cached_events: Internal event listeners keyed by event name.
        module_handler: Dynamic module lifecycle handler.
        command_handler: Prefix-command handler.
        event_handler: Discord gateway event handler.
        translator: Internationalization service.
        emoji_manager: Emoji/assets manager.
        _events: Internal event bus mapping from event name to listeners.
    """


    def __init__(self, *args, logger: logging.Logger, **kwargs):
        super().__init__(*args, **kwargs)
        self.db: MongoDBAsyncORM = None

        self.ready = False
        self.detailed_help = {}
        self.view_registry: Dict[str, InteractionView] = {}
        self.setting_cache = {}
        
        # Logger
        self.logger: logging.Logger = logger

        # Locks and caches
        self.global_lock: AsyncLock = AsyncLock()

        # Managers
        self.flags_manager: "FlagsManager" = None
        self.member_manager: "MemberManager" = None
        self.guild_manager: "GuildManager" = None
        self.slash_manager: Optional["SlashManager"] = None
        self.permission_manager: "PermissionsManager" = None
        self.settings_manager: "SettingsManager" = None

        # Middleware
        self.command_middleware: List[Callable[[Dict], Awaitable[bool]]] = []

        # Modules and events
        self.modules: Dict[str, "Module"] = {}
        self.cached_events: DefaultDict[str, List] = defaultdict(list)

        # Handlers
        self.module_handler: "ModuleHandler" = None
        self.command_handler:"CommandHandler" = None
        self.event_handler: "EventHandler" = None

        # Translator
        self.translator: Translator = None
        self.emoji_manager: "EmojiManager" = None
        
        self._events: Dict[str, List[Callable[..., Awaitable[Any]]]] = {}

    def add_middleware(self, func: Callable[[Dict], Awaitable[bool]]) -> None:
        """
        Adds a middleware function to be called on every command.
        """
        self.command_middleware.append(func)

    async def on_ready(self):
        """
        Called when the bot is ready.
        """
        self.logger.info(f"Bot connected as {self.user}")

    async def on_command_error(self, ctx, error):
        """
        Handles command errors globally.
        """
        self.logger.error(f"Command error: {error}")
        
    def on(self, event: str, listener: Callable[..., Awaitable[Any]]):
        """Register a listener on the client's internal event bus.

        This is separate from `discord.py` events and is intended for module-level decoupling.

        Args:
            event: Logical internal event name.
            listener: Async callable to be invoked when the event is emitted.
        """
        if event not in self._events:
            self._events[event] = []
        self._events[event].append(listener)

    def once(self, event: str, listener: Callable[..., Awaitable[Any]]):
        """Register a one-shot listener removed after its first invocation.

        Args:
            event: Internal event name.
            listener: Async callable to run exactly once.
        """
        async def wrapper(*args, **kwargs):
            await listener(*args, **kwargs)
            self.off(event, wrapper)

        self.on(event, wrapper)

    def emit(self, event: str, *args, **kwargs):
        """Emit an internal event and schedule all listeners.

        Listeners are scheduled via `asyncio.create_task`.

        Args:
            event: Internal event name.
            *args: Positional arguments passed to listeners.
            **kwargs: Keyword arguments passed to listeners.
        """
        if event in self._events:
            for listener in self._events[event]:
                asyncio.create_task(listener(*args, **kwargs))

    def off(self, event: str, listener: Callable[..., Awaitable[Any]]):
        """Remove a specific listener from an internal event.

        Args:
            event: Internal event name.
            listener: Previously registered listener.
        """
        if event in self._events and listener in self._events[event]:
            self._events[event].remove(listener)

    def remove_all_listeners(self, event: str = None):
        """Remove all listeners from an event, or from all events if none is given.

        Args:
            event: Optional internal event name. If None, clears all events.
        """
        if event:
            if event in self._events:
                del self._events[event]
        else:
            self._events.clear()


# Estrutura de argumentos de middleware para comandos
class MiddlewareArgs(TypedDict):
    client: "ExtendedClient"
    logger: logging.Logger
    profile: "Member"
    guild: "Guild"
    interfacer: Any
    command: Union["Command", "SlashCommand"]


# Construtor para comandos regulares
class CommandConstructor(TypedDict):
    name: str
    aliases: List[str]
    description: str
    how_to_use: str
    func: Callable[[Dict[str, Any]], None]
    permissions: Optional[List[int]]


# Construtor para comandos slash
class SlashCommandConstructor(TypedDict):
    data: Any
    func: Callable[[Dict[str, Any]], None]
    global_: bool
    auto_complete_func: Optional[Callable]


# Argumentos para execução de comandos regulares
class CommandArgs(TypedDict):
    client: "ExtendedClient"
    logger: logging.Logger
    message: Message
    profile: "Member"
    args: List[str]
    guild: "Guild"
    interfacer: Any
    used_name: str


# Argumentos para execução de comandos slash
class SlashCommandArgs(TypedDict):
    client: "ExtendedClient"
    logger: logging.Logger
    interaction: Interaction
    profile: "Member"
    guild: "Guild"
    interfacer: Any


# Tipo para a árvore de permissões recursivas
RecursiveMap = Dict[str, Union["RecursiveMap", Any]]


# Estrutura para eventos dinâmicos
class DynamicEvent(TypedDict):
    event: str
    func: Callable[["ExtendedClient", logging.Logger, Any], None]


# Estrutura para eventos pré-definidos
class Event(TypedDict):
    event: str
    func: Callable[["ExtendedClient", logging.Logger, Any], None]


# Definição de AnyView
AnyView = Union["InteractionView", "MessageView"]
