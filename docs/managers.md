# Managers

Managers encapsulate persistence, caching, and orchestration around guilds, members, settings, and permissions.

## GuildManager
- Ensures the guild document exists in MongoDB (`guilds` collection).
- Materializes the full guild settings map by merging module defaults with DB values.
- Caches settings per guild and invalidates on demand.

## MemberManager
- Ensures the member profile document exists in MongoDB (`members` collection).
- Hydrates a `Member` domain object (Discord member + guild wrapper + user settings).
- Provides helpers to create, update, delete, and query member profiles.

## SettingsManager
- Facade to load/persist guild- and member-level settings.
- Delegates to `GuildManager` and `MemberManager` for hydration and storage.

## PermissionsManager
- Hierarchical permission tree with wildcard support (e.g., `Role.*`, `User.<id>`, custom paths).
- Resolves permission nodes to async callables and evaluates overrides (`allow`/`deny`).
