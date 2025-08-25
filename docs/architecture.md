# Architecture overview

```
main.py
 └─ handlers/
    ├─ commandHandler.py      Command parsing and dispatch
    ├─ eventHandler.py        Event subscription and routing
    ├─ moduleHandler.py       Dynamic module lifecycle (load, enable, disable)
    ├─ settingsHandler.py     Settings registry and persistence
    ├─ database_handler.py    DB access helpers
    ├─ xp_config.py           Leveling and XP logic
    └─ logger.py              Structured logging

utils/
 ├─ Loader.py                 Dynamic import helpers
 ├─ EmojiManager.py           Emoji assets management
 ├─ Translator.py             i18n helpers
 ├─ InteractionView.py        Generic interaction views
 ├─ MessageView.py            Message view helpers
 ├─ ViewRouter.py             Route interactions to views
 └─ components/
    ├─ PaginatorComponent.py  Pagination for long lists
    └─ EmbedCreatorComponent.py Embed building utilities

settings/
 ├─ Setting.py                Base Setting class
 └─ DefaultTypes/             Built-in typed fields
```

This section explains how control flows from `main.py` into handlers, then into modules.
