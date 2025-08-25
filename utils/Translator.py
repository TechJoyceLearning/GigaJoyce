import aiofiles
from shared.types import ExtendedClient
from collections import defaultdict
from pathlib import Path
import json
from typing import Dict, Any, Callable, Optional
import logging

class Translator:
    """High‑level translation service with caching and emoji post‑processing.

    This utility:
      * Resolves the preferred language per guild (with caching).
      * Loads and caches **global** translation files from a shared folder.
      * Loads and caches **module** translation files from each module folder.
      * Replaces emoji placeholders using `EmojiManager` (if available).
      * Exposes convenience helpers to retrieve a translation or a translator
        function (sync/async).

    Notes:
        * Global translations live under `global_path/*.json`.
        * Module translations are discovered under `<module>/translations/*.json`
          unless a different folder is declared in the module's manifest.
    """
    def __init__(self, bot: ExtendedClient, global_path: str, logger: logging.Logger):
        """Initialize the translator and its caches.

        Args:
            bot: The extended Discord client.
            global_path: Filesystem path to the global translations directory.
            logger: Logger for diagnostics.
        """
        self.bot = bot
        self.logger = logger
        self.global_path = Path(global_path)
        self.global_translations_cache = {}
        self.module_translation_cache = {}
        self.language_cache = {}

    async def get_language(self, guild_id: str) -> str:
        """Return the configured language for a guild (default `'en'`).

        Normalizes common aliases like `"English"`, `"en-US"`, `"pt-br"`, etc.
        Results are cached per guild id.

        Args:
            guild_id: Discord guild id.

        Returns:
            Normalized language code such as `"en"` or `"pt"`.
        """
        guild_id = str(guild_id)
        if guild_id in self.language_cache:
            return self.language_cache[guild_id]

        guild = await self.bot.guild_manager.fetch_or_create(guild_id)
        language = guild.data.get("language", "en")

        if language in ["Inglês", "English", "en", "en-US"]:
            self.language_cache[guild_id] = "en"
            language = "en"
        elif language in ["Português", "pt-br", "Português (Brasileiro)", "pt"]:
            self.language_cache[guild_id] = "pt"
            language = "pt"
        else:
            self.language_cache[guild_id] = language
        return language

    def get_language_sync(self, guild_id: Optional[str]) -> str:
        """Synchronous variant of `get_language` using the local cache only.

        If the language for `guild_id` is not cached, returns `'en'`.

        Args:
            guild_id: Guild id (or `None`).

        Returns:
            A normalized language code.
        """
        if guild_id and guild_id in self.language_cache:
            guild_id = str(guild_id)
            return self.language_cache[guild_id]
        return "en"

    def update_language_cache(self, guild_id: str, language: str):
        """Update the local language cache for a guild.

        Args:
            guild_id: Guild id.
            language: Normalized language code to store.
        """
        guild_id = str(guild_id)
        self.language_cache[guild_id] = language

    def _process_emojis(self, text: str, module_name: Optional[str] = None) -> str:
        """Replace emoji placeholders (`:name:`) in a string.

        Delegates to `EmojiManager.replace_emojis` if the bot exposes an
        `emoji_manager` attribute. Otherwise returns the text unchanged.

        Args:
            text: Source text that may contain placeholders.
            module_name: Module name for module‑scoped emoji lookups.

        Returns:
            Text with emoji placeholders resolved.
        """
        if hasattr(self.bot, "emoji_manager"):
            return self.bot.emoji_manager.replace_emojis(text, module_name)
        return text

    def _process_translation(self, translations: Dict[str, Any], module_name: Optional[str] = None) -> Dict[str, Any]:
        """Recursively apply emoji replacements to a translation tree.

        Args:
            translations: Nested mapping of translation keys → values.
            module_name: Module name for module‑scoped emoji lookups.

        Returns:
            A new mapping with emojis processed.
        """
        processed = {}
        for key, value in translations.items():
            if isinstance(value, str):
                processed[key] = self._process_emojis(value, module_name)
            elif isinstance(value, dict):
                processed[key] = self._process_translation(value, module_name)
            else:
                processed[key] = value
        return processed

    async def refresh_translation_cache(self):
        """Reload global and module translation caches asynchronously.

        Scans the `global_path` for `*.json` files and each loaded module's
        translations directory (from its manifest or default `"translations"`).
        """

        available_languages = {file.stem for file in self.global_path.glob("*.json")}
        for language in available_languages:
            path = self.global_path / f"{language}.json"
            if path.exists():
                try:
                    async with aiofiles.open(path, "r", encoding="utf-8") as f:
                        content = await f.read()
                        translations = json.loads(content)
                        self.global_translations_cache[language] = self._process_translation(translations)
                        self.logger.info(f"Global translations loaded for language: {language}")
                except json.JSONDecodeError as e:
                    self.logger.error(f"Error loading global translations for {language}: {e}")

        # Carregar traduções dos módulos
        for module_name, module in self.bot.modules.items():
            translations_folder = module.data.get("translationsFolder") or "translations"
            translations_path = Path(module.path) / translations_folder
            available_languages = {file.stem for file in translations_path.glob("*.json")}
            for language in available_languages:
                path = translations_path / f"{language}.json"
                if path.exists():
                    try:
                        async with aiofiles.open(path, "r", encoding="utf-8") as f:
                            content = await f.read()
                            translations = json.loads(content)
                            processed_translations = self._process_translation(translations, module_name)
                            cache_key = f"{module_name}:{language}"
                            self.module_translation_cache[cache_key] = processed_translations
                            self.logger.info(f"Module translations loaded for {module_name}, language: {language}")
                    except json.JSONDecodeError as e:
                        self.logger.error(f"Error loading module translations for {module_name}, language: {language}: {e}")

    def get_translation(self, key: str, language: str, module_name: Optional[str] = None) -> str:
        """Return the processed translation for a dot‑separated key.

        Args:
            key: Hierarchical key such as `"help.commands.ping.description"`.
            language: Target language code.
            module_name: Module name to search in module cache; if omitted,
                the global cache is used.

        Returns:
            The resolved translation string, or `key` if not found.
        """
        translations = (
            self.module_translation_cache.get(f"{module_name}:{language}", {})
            if module_name
            else self.global_translations_cache.get(language, {})
        )

        keys = key.split(".")
        for k in keys:
            if isinstance(translations, dict):
                translations = translations.get(k)
            else:
                return key  # Retorna a própria chave se não encontrada
        return translations if isinstance(translations, str) else key
    

    async def get_translator(self, guild_id: str, module_name: Optional[str] = None) -> Callable[[str], str]:
        """Return a callable that resolves translations for a guild asynchronously.

        The callable captures the guild's current language and interpolates `**kwargs`
        with standard Python `str.format`.

        Args:
            guild_id: Guild id to derive the language from.
            module_name: Module name for module‑scoped translations.

        Returns:
            A function `fn(key: str, **kwargs) -> str`.
        """
        guild_id = str(guild_id)
        language = await self.get_language(guild_id=guild_id)

        def translator_func(key: str, **kwargs) -> str:
            value = self.get_translation(key=key, language=language, module_name=module_name)
            return value.format(**kwargs)

        return translator_func

    def get_translator_sync(self, language: str, module_name: Optional[str] = None) -> Callable[[str], str]:
        """Return a synchronous translator function for a fixed language.

        Args:
            language: Target language.
            module_name: Optional module context.

        Returns:
            A function `fn(key: str, **kwargs) -> str`.
        """
        def translator_func(key: str, **kwargs) -> str:
            value = self.get_translation(key=key, language=language, module_name=module_name)
            return value.format(**kwargs)
        return translator_func
