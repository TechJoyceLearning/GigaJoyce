from abc import ABC, abstractmethod
from typing import Callable, Awaitable, Optional, Union, TypeVar, Any, Generic, TYPE_CHECKING
from utils.InteractionView import InteractionView
from shared.types import ExtendedClient
from classes.structs.Guild import Guild
from classes.structs.Member import Member

if TYPE_CHECKING:
    from settings.DefaultTypes.boolean import BooleanSettingFile

T = TypeVar("T")


class Setting(ABC, Generic[T]):
    """Abstract base class for all settings.

    A `Setting[T]` represents a configurable value owned either by a **Guild**
    or a **Member** (user). Subclasses define how the value is:
    - **run** (collected/edited via UI),
    - **serialized** to database (**parse_to_database**),
    - **deserialized** from database (**parse_from_database** / **parse**).

    Attributes:
        name: Human‑readable name to display in UIs.
        description: Short explanation of what this setting controls.
        id: Unique identifier for persistence (used as the document field key).
        type: String type label (e.g., "string", "boolean", "role", etc.).
        value: Current in‑memory value (deserialized form).
        permission: Optional permission bit/level required to change this setting.
        locales: Whether this setting’s display strings should be translated.
        module_name: Owning module name, if the setting belongs to a module.
        kwargs: Extra configuration specific to a given concrete setting type.
    """

    def __init__(
        self,
        name: str,
        description: str,
        id: str,
        type_: str,
        value: Optional[T] = None,
        permission: Optional[int] = None,
        locales: Optional[bool] = False,
        module_name: Optional[str] = None,
        **kwargs,
    ):
        self.name = name
        self.description = description
        self.id = id
        self.type = type_
        self.value = value
        self.permission = permission
        self.locales = locales
        self.module_name = module_name
        self.kwargs = kwargs


    def run(self, view: InteractionView) -> Awaitable[T]:
        """Execute the interactive flow for this setting.

        Implementations should render the necessary UI (buttons, selects, etc.)
        and resolve with the updated value.

        Args:
            view: Active `InteractionView` used to present the UI.

        Returns:
            An awaitable that resolves to the new value of type `T`.

        Raises:
            NotImplementedError: If the subclass does not override this method.
        """
        raise NotImplementedError("Must be implemented in derived classes.")


    def parse_to_database(self, value: T) -> Any:
        """Serialize the runtime value into a DB‑friendly representation.

        This is the inverse of `parse_from_database`.

        Args:
            value: The runtime value.

        Returns:
            A JSON‑serializable value suitable for your database.

        Raises:
            NotImplementedError: If the subclass does not override this method.
        """
        raise NotImplementedError("Must be implemented in derived classes.")


    def parse_from_database(self, config: Any) -> T:
        """Reconstruct the runtime value from the DB representation.

        This is the inverse of `parse_to_database`.

        Args:
            config: Raw stored value from the database.

        Returns:
            The deserialized runtime value of type `T`.

        Raises:
            NotImplementedError: If the subclass does not override this method.
        """
        raise NotImplementedError("Must be implemented in derived classes.")

    async def parse(self, config: Any, client: ExtendedClient, guild_data: Any, guild: Guild) -> Awaitable[T]:
        """Optional async hook to parse a value with context.

        Subclasses may override this to perform context‑aware parsing (e.g.
        resolve IDs to Discord objects). Default behavior returns `config` as‑is.

        Args:
            config: Raw config value from DB or input.
            client: Extended bot client.
            guild_data: Raw guild document (for extra context if needed).
            guild: Hydrated guild wrapper.

        Returns:
            The parsed value (usually of type `T`).
        """
        return config

    async def save(self, client: ExtendedClient, entity: Union["Guild", "Member"], setting: "Setting[T]") -> bool:
        """Persist the setting value using the client DB API.

        Default behavior:
          1. Serializes `setting.value` via `parse_to_database` if available.
          2. Writes to:
             - `guilds` collection with filter `{"_id": str(guild.id)}` when
               `entity` is a `Guild`;
             - `members` collection with filter `{"_id": str(member.id)}` when
               `entity` is a `Member`.

        Note:
            If your schema uses different keys (e.g., composite keys
            `{"id": ..., "guildId": ...}` for members), override this method in
            your concrete setting type or adapt it at call‑site.

        Args:
            client: Extended bot client (exposes `client.db.update_one`).
            entity: Guild or Member instance that owns the setting.
            setting: The concrete `Setting` instance being saved.

        Returns:
            An awaitable that resolves truthy on success.
        """
        client.logger.debug(f"Using default save method for setting: {self.id}")

        if hasattr(setting, "parse_to_database") and callable(setting.parse_to_database):
            if setting.value is not None:
                value = setting.parse_to_database(setting.value)
            else:
                client.logger.warning(f"Setting value is None; storing as None in database.")
                value = None
        else:
            client.logger.warning(f"Setting does not have a parse_to_database method. Using raw value.")
            value = setting.value

        query = {f"settings.{setting.id}": value}

        if isinstance(entity, Guild):
            result = await client.db.update_one(
                "guilds",
                {"_id": str(entity.id)},
                {"$set": query},
            )
            return bool(result)
        elif isinstance(entity, Member):
            result = await client.db.update_one(
                "members",
                {"_id": str(entity.id)},
                {"$set": query},
            )
            return bool(result)
        else:
            raise TypeError("Entity must be a Guild or Member.")

    def apply_locale(self, translate_module: Callable[[str], str], clone: Optional[bool] = False) -> Union["Setting[T]", tuple[str, str, str]]:
        """Apply module‑scoped translation to all display fields.

        If `self.locales` is truthy, this will translate `name`, `description`,
        and any string values inside `kwargs` using the provided function.

        Args:
            translate_module: Function that maps a translation key to its value.
            clone: If True, returns a **new** translated copy of this setting;
                otherwise returns a tuple `(name, description, kwargs)` with
                translated values without mutating the instance.

        Returns:
            - If `clone=True`: a new `Setting` instance (same type) with fields
              translated;
            - If `clone=False`: a tuple `(name, description, kwargs)`; or
            - If `self.locales` is falsy: `None`.
        """
        if self.locales:
            if clone:
                setting_clone = self.clone()
                setting_clone.name = translate_module(self.name)
                setting_clone.description = translate_module(self.description)
                setting_clone.kwargs = {}
                for key, value in self.kwargs.items():
                    if isinstance(value, str):
                        setting_clone.kwargs[key] = translate_module(value)
                return setting_clone
            else:
                name = translate_module(self.name)
                description = translate_module(self.description)
                kwargs = {}
                for key, value in self.kwargs.items():
                    kwargs[key] = translate_module(value)
                return name, description, kwargs

    def propagate_locales(self, child: "Setting[Any]"):
        """Propagate `locales` and `module_name` flags to a child setting.

        Useful when composite settings are composed of other settings and you
        want consistent translation behavior across the hierarchy.

        Args:
            child: The setting that should inherit locale info.
        """
        if self.locales and self.module_name:
            child.locales = self.locales
            child.module_name = self.module_name

    def clone(self) -> "Setting[T]":
        """Return a shallow copy of this setting instance.

        The copy is constructed by re‑invoking the concrete class `__init__`
        with parameters that exist as attributes on `self`.

        Returns:
            A new instance of the concrete `Setting` subclass.
        """
        cls = self.__class__
        init_params = cls.__init__.__code__.co_varnames[1:]  # Ignora 'self'
        init_args = {key: getattr(self, key) for key in init_params if hasattr(self, key)}
        return cls(**init_args)
