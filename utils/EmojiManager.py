import json
import re
from pathlib import Path
from typing import Dict, Any, Optional
from logging import Logger


class EmojiManager:
    """Loads and resolves emoji placeholders for global and module scopes.

    Placeholders follow the pattern `:emoji_name:`. This manager supports a
    global emoji catalog (single JSON file) and per‑module catalogs.
    """

    EMOJI_PATTERN = re.compile(r":([a-zA-Z0-9_]+):")

    def __init__(self, bot, global_path: str, logger: Logger):
        """Initialize the emoji manager.

        Args:
            bot: The bot instance (for context; not required to resolve emojis).
            global_path: Directory containing the `emojis.json` file.
            logger: Logger for diagnostics.
        """
        self.bot = bot
        self.logger = logger
        self.global_path = Path(global_path)
        self.global_emojis: Dict[str, str] = {}  # Emojis globais
        self.module_emojis: Dict[str, Dict[str, str]] = {}  # Emojis por módulo

    def load_global_emojis(self):
        """Load global emojis from `<global_path>/emojis.json`."""
        path = self.global_path / "emojis.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                try:
                    self.global_emojis = json.load(f)
                    self.logger.info("Global emojis loaded with success.")
                except json.JSONDecodeError as e:
                    self.logger.error(f"Erro while loading global emojis: {e}")
        else:
            self.logger.warning("File emojis.json wasn't find for global emojis.")

    def load_module_emojis(self, module_name: str, module_path: str):
        """Load per‑module emojis from `<module_path>/emojis.json`.

        Args:
            module_name: Name of the module to associate the catalog.
            module_path: Filesystem path to the module root.
        """
        path = Path(module_path) / "emojis.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                try:
                    self.module_emojis[module_name] = json.load(f)
                    self.logger.info(f"Emojis loaded with succes for the module: {module_name}")
                except json.JSONDecodeError as e:
                    self.logger.error(f"Erro while loading emojis for the module {module_name}: {e}")
        else:
            self.logger.warning(f"File emojis.json not found for the module: {module_name}")

    def replace_emojis(self, text: str, module_name: Optional[str] = None) -> str:
        """Replace `:emoji_name:` placeholders with actual emojis.

        Args:
            text: The source text that may contain placeholders.
            module_name: Optional module name to use a module‑specific catalog.

        Returns:
            The processed text with placeholders substituted.
        """

        def emoji_replacer(match):
            emoji_name = match.group(1)
            if module_name and module_name in self.module_emojis:
                return self.module_emojis[module_name].get(emoji_name, f":{emoji_name}:")
            return self.global_emojis.get(emoji_name, f":{emoji_name}:")

        return self.EMOJI_PATTERN.sub(emoji_replacer, text)
