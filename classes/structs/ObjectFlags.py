from discord.ext.commands import Bot
from typing import Any, Dict
import logging


class ObjectFlags:
    """In‑memory flags for a Guild or Member domain object.

    Provides a thin wrapper to read/write boolean or arbitrary values inside
    the object's backing `data["flags"]` and to consult defaults from
    `client.flags.flags` when unset on the object.
    """

    def __init__(self, client: Bot, obj: Any):
        """Initialize a flags manager bound to a specific object.

        Args:
            client: Discord bot client. Expected to expose `client.flags.flags`
                with default values for known flag keys.
            obj: The domain object (e.g., Guild or Member) holding `data`.
        """
        self.client = client
        self.obj = obj  # Pode ser uma instância de Guild ou outra classe
        self.logger = logging.getLogger(f"{self.obj.id} Flags")  # Use o atributo id diretamente


    def _default_flags(self) -> Dict[str, Any]:
        """Return the global defaults from the client, or an empty mapping."""
        fm = getattr(self.client, "flags_manager", None)
        return getattr(fm, "flags", {}) if fm else {}

    def _ensure_flags_dict(self) -> Dict[str, Any]:
        """Ensure `obj.data['flags']` exists and return it (or an empty dict)."""
        if hasattr(self.obj, "data") and isinstance(self.obj.data, dict):
            return self.obj.data.setdefault("flags", {})
        return {}
    
    def set(self, flag: str, value: Any) -> bool:
        """Set a custom flag on the object (synchronous).

        Returns False if the flag key is unknown or if the object data is invalid.

        Args:
            flag: Flag key to set.
            value: Arbitrary value to assign.

        Returns:
            True if the flag was set, False otherwise.
        """
        defaults = self._default_flags()
        if defaults and flag not in defaults:
            self.logger.warning(f"Flag '{flag}' is not registered, ignoring.")
            return False

        flags = self._ensure_flags_dict()
        if flags is not None:
            flags[flag] = value
            return True

        self.logger.error(f"Object '{self.obj}' does not have a valid data attribute.")
        return False

    async def awaitable_set(self, flag: str, value: Any) -> bool:
        """Set a custom flag on the object (async signature convenience).

        Same semantics as `set()`, but with an awaitable signature for call sites
        that are already async.

        Args:
            flag: Flag key to set.
            value: Arbitrary value to assign.

        Returns:
            True if the flag was set, False otherwise.
        """
        return self.set(flag, value)

    def delete(self, flag: str) -> bool:
        """Delete a custom flag from the object if present.

        Args:
            flag: Flag key to remove.

        Returns:
            True if the flag existed and was removed, False otherwise.
        """
        if hasattr(self.obj, "data") and isinstance(self.obj.data, dict):
            self.obj.data.setdefault("flags", {}).pop(flag, None)
            return True
        return False

    def get(self, flag: str) -> Any:
        """Return the effective value for a flag.

        Looks first at the object's `data["flags"]`, then falls back to
        the global default in `client.flags.flags`.

        Args:
            flag: Flag key to read.

        Returns:
            The value set on the object or the default if unset.
        """
        defaults = self._default_flags()
        if hasattr(self.obj, "data") and isinstance(self.obj.data, dict):
            obj_val = self.obj.data.get("flags", {}).get(flag, None)
            return obj_val if obj_val is not None else defaults.get(flag)
        return defaults.get(flag)

    def has(self, flag: str) -> bool:
        """Return whether a flag key is recognized by the client.

        Note:
            This checks registration (existence in client defaults), not whether
            a truthy value is set on the object.

        Args:
            flag: Flag key to verify.

        Returns:
            True if the flag key is registered, otherwise False.
        """
        defaults = self._default_flags()
        return flag in defaults

    @property
    def all(self) -> Dict[str, Any]:
        """Return the full flag map stored on the object (without defaults).

        Returns:
            A dict of object‑level flags, or `{}` if no flags were persisted.
        """
        if hasattr(self.obj, "data") and isinstance(self.obj.data, dict):
            return self.obj.data.get("flags", {})
        return {}
