from discord.ext.commands import Bot
from typing import Union, Any
from collections import defaultdict
import logging
from classes.structs.Guild import Guild  # Import explícito para validação


class FlagsManager:
    """
    Central registry for feature flags and defaults.

    This manager holds **global default flag values** and exposes helpers to read
    per-guild flag values via the guild's own `ObjectFlags` facade.

    Typical usage:
        - Call :meth:`register_flag` at startup to declare a flag and its default.
        - Use :meth:`get_flag` inside your features to read the value for a given guild,
          falling back to the global default when the guild did not override it.
        - Use :meth:`has_flag` to quickly check if a flag exists either locally (guild)
          or globally.

    Notes
    -----
    Guild-level reads are delegated to :class:`classes.structs.ObjectFlags.ObjectFlags`
    via ``guild.flags`` (which is created in :class:`classes.structs.Guild.Guild`).
    """

    def __init__(self, client: Bot, logger: logging.Logger):
        """
        Parameters
        ----------
        client:
            The Discord client/bot instance.
        logger:
            Logger used for diagnostics.
        """
        self.client = client
        self.flags = {}  # Stores global default flags
        self.logger = logger

    def register_flag(self, flag: str, default_value: Union[str, bool, list]):
        """
        Register (or overwrite) a global flag and its default value.

        Parameters
        ----------
        flag:
            Unique flag identifier (e.g., ``"features.xp_enabled"``).
        default_value:
            Default value used when the guild has no explicit override.

        Returns
        -------
        FlagsManager
            Self, to allow call chaining.

        Examples
        --------
        >>> flags.register_flag("features.xp_enabled", True)
        """
        if flag in self.flags:
            self.logger.warning(f"Flag {flag} already exists, overwriting it.")
        self.flags[flag] = default_value
        return self

    def delete_flag(self, flag: str):
        """
        Remove a global flag definition.

        If the flag is not present, this is a no-op.

        Parameters
        ----------
        flag:
            The flag identifier to remove.

        Returns
        -------
        FlagsManager
            Self, to allow call chaining.
        """
        if flag in self.flags:
            del self.flags[flag]
        return self

    def get_flag(self, guild: Union[Guild, Any], flag: str) -> Any:
        """
        Resolve a flag value for a specific guild.

        The lookup order is:
        1) Guild override via ``guild.flags.get(flag)``.
        2) Global default from this manager.

        Parameters
        ----------
        guild:
            The target :class:`classes.structs.Guild.Guild` instance.
        flag:
            The flag identifier.

        Returns
        -------
        Any
            The resolved flag value (guild override if present, otherwise global default).

        Raises
        ------
        TypeError
            If ``guild`` is not an instance of :class:`classes.structs.Guild.Guild`.
        """
        if not isinstance(guild, Guild):
            self.logger.error(f"Expected a Guild instance, got {type(guild).__name__}.")
            raise TypeError("Invalid guild type.")
        return guild.flags.get(flag) or self.flags.get(flag)

    def has_flag(self, guild: Union[Guild, Any], flag: str) -> bool:
        """
        Check if a flag exists for a guild (override) or globally.

        Parameters
        ----------
        guild:
            The target :class:`classes.structs.Guild.Guild` instance.
        flag:
            The flag identifier.

        Returns
        -------
        bool
            ``True`` if the flag is available either in the guild override or in
            the manager's global defaults; ``False`` otherwise.

        Raises
        ------
        TypeError
            If ``guild`` is not an instance of :class:`classes.structs.Guild.Guild`.
        """
        if not isinstance(guild, Guild):
            self.logger.error(f"Expected a Guild instance, got {type(guild).__name__}.")
            raise TypeError("Invalid guild type.")
        return guild.flags.has(flag) or flag in self.flags
