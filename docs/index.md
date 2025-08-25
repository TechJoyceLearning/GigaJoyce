# GigaJoyce

GigaJoyce is a Discord bot developed for the [TechJoyce channel](https://www.youtube.com/@TechJoyce).  
Its purpose is to serve both as a learning platform and as a practical framework that demonstrates how a modular Discord bot can be built from scratch.

The bot is **modular by design**. Every feature lives inside its own module, containing its commands, events, and optional settings. This means that contributors do not need to modify the internal framework of the bot in order to add new features. Creating a new command or system is simply a matter of adding a new module with its own `init.py` and command files. The core automatically loads and registers everything that is exported.

At the same time, the internals of the bot are **fully documented**. Handlers, managers, and utility classes are all explained in this documentation. The reason is not that you are expected to change them — in fact, the core should remain stable — but because contributors may want to understand how the system works, or even suggest improvements to its architecture.

This approach makes GigaJoyce a project that is open for collaboration. Developers who want to help can focus on writing new modules, improving existing features, or polishing the documentation itself. The framework is there to ensure that contributions can happen without breaking the rest of the bot.  

In short, GigaJoyce is a bot where the **core is stable and documented**, and the **modules are the playground** for contributors. If you want to help, you are encouraged to create modules and expand its functionality, while also having the freedom to explore the internals whenever you are curious about how things work under the hood.

---

## Project layout

```
GigaJoyce/
├─ classes/             # Core structures (Guild, Member, etc.)
├─ settings/            # Settings framework (base + default types)
├─ utils/               # InteractionView and helper components
├─ modules/             # Your plug-and-play modules
│  ├─ Economy/          # Example module (see Examples → Economy)
│  └─ ...
├─ commandHandler.py    # Registers commands from modules
├─ eventHandler.py      # Registers events from modules
├─ moduleHandler.py     # Discovers and initializes modules
└─ ...
```

---

## Quick start

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment** (Discord token, DB, etc.) via `.env` or your preferred method.

3. **Run the bot**
   ```bash
   python main.py
   ```

> Looking to build your first feature? Jump to **Examples → Economy** to see a complete, real module.

---

## Credits

- Created by [elementare](https://github.com/elementare)for the **TechJoyce** community: <https://discord.gg/joyce>

---

## License

MIT — see `LICENSE`.
