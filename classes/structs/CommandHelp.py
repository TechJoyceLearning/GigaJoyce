from typing import Optional, Callable, Dict

class CommandHelp:
    """Rich, localized help metadata for a command.

    Stores per‑language dictionaries with keys such as `description`, `usage`,
    and `examples`. Retrieval is language‑aware with a safe fallback to English.
    """

    def __init__(
        self, 
        name: str, 
        translations: Dict[str, Dict[str, Optional[str]]]
    ):
        """Initialize a `CommandHelp` descriptor.

        Args:
            name: Command name this help refers to.
            translations: Mapping of language code → help fields. Expected keys
                include:
                  - "description": short explanation of what the command does
                  - "usage": usage string
                  - "examples": one or more example invocations
                Example::
                    {
                        "en": {
                            "description": "Shows the current XP and level of a user.",
                            "usage": "/xp [user]",
                            "examples": ["/xp", "/xp @User123"]
                        },
                        "pt": {
                            "description": "Mostra o XP atual e o nível de um usuário.",
                            "usage": "/xp [usuário]",
                            "examples": ["/xp", "/xp @Usuario123"]
                        }
                    }
        """
        self.name = name  
        self.translations = translations 

    def get_translation(self, language: str) -> Dict[str, Optional[str]]:
        """Return the help metadata for the requested language.

        Falls back to English ("en") if the requested language is not available.
        Returns an empty dict if neither is present.

        Args:
            language: BCP‑47/ISO language code (e.g., "en", "pt-BR").

        Returns:
            A dict including keys such as "description", "usage", and "examples".
        """
        return self.translations.get(language, self.translations.get("en", {}))
