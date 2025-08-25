Economy example module (GigaJoyce)

This document explains the concrete code that ships with the Economy example: what each file does, the functions that matter, and how the pieces fit together at runtime. It is written to help contributors understand the real module surface, not a generic template.

Folder layout (relative to repo root)

```
modules/
  Economy/
    main.py
    types.py
    manifest.json
    commands/
      economy.py
```
 
manifest.json

The module loader (ModuleHandler) reads this file to discover the module. A typical manifest for this module is:

```json
{
  "name": "Economy",
  "description": "Simple banking system with balances and transactions.",
  "version": "1.0.0",
  "color": "#daccff",
  "initFile": "main.py",
  "commandsFolder": "commands",
  "eventsFolder": "events",
  "translationsFolder": "translations",
  "permissions": ["economy.manage"]
}
```

ModuleHandler will import initFile and call its `setup(bot, logger)` function. Whatever that returns is stored under `bot.modules["Economy"]` and used by the rest of the system. `commandsFolder` is scanned by CommandHandler; any file that exposes `exports = [...]` gets registered into the slash tree.

main.py

The file exposes three important things:
• a tiny dataclass to normalize the settings payload,
• an Interfacer object that is the runtime API (what commands call),
• the server‑level settings tree and the setup(...) entrypoint.

Dataclass and config resolver

```python
@dataclass
class EconomyConfig:
    """Resolved, display‑friendly config taken from the module setting."""
    name: str
    coin_name: str
    coin_symbol: str

def _resolve_config(raw: Dict[str, Any]) -> EconomyConfig:
    """Convert raw dict from ComplexSetting into a strongly‑typed config."""
```

Interfacer (runtime API)

The Interfacer owns all balance/transaction logic. It uses Mongo through `client.db` and writes to two places:

1) a member profile document in the `members` collection, field `Economy.balance`,
2) a row in the `economy_transactions` collection with a UUID transaction id and an ISO UTC timestamp.

Key helpers and operations (real names from the file):

```python
async def _get_member_doc(self, member_id: int, guild_id: int) -> Dict[str, Any]:
    """Fetch or create a member document and ensure Economy.balance exists."""

async def _save_balance(self, member_id: int, guild_id: int, new_balance: int) -> None:
    """Update members.{Economy.balance} with upsert."""

async def get_balance(self, member_id: int, guild_id: int) -> int:
    """Return the current stored balance."""

async def _save_transaction(self, *, guild_id: int, tx_type: TransactionType,
                            payer: Optional[int], receiver: Optional[int], value: int) -> str:
    """Insert a document into 'economy_transactions' and return transactionId (uuid4)."""

async def consultTransactions(self, user_id: int, *, guild_id: Optional[int] = None,
                              limit: int = 50, order: str = "desc") -> List[Dict[str, Any]]:
    """Return transactions where the user is payer or receiver, optionally filtered by guild."""

async def add(self, *, user_id: int, guild_id: int, value: int) -> Dict[str, Any]:
    """Increase balance and append an ADD transaction."""

async def remove(self, *, user_id: int, guild_id: int, value: int) -> Dict[str, Any]:
    """Decrease balance (with sufficient‑funds check) and append a REMOVE transaction."""

async def transfer(self, *, from_user_id: int, to_user_id: int, guild_id: int, value: int) -> Dict[str, Any]:
    """Move funds between users and append a TRANSFER transaction."""

async def createTransaction(self, *, interaction, tx_type: TransactionType,
                            user_id: int, guild_id: int, value: int, channel,
                            target_user_id: Optional[int] = None) -> Dict[str, Any]:
    """Show a Confirm/Cancel view and run the chosen operation if confirmed; returns the result payload."""
```

On storage shape, a member document ends up like:

```json
{
  "id": "123",
  "guildId": "456",
  "Economy": { "balance": 2500 }
}
```

And a transaction row looks like:

```json
{
  "transactionId": "uuid-v4",
  "timestamp": "2025-08-23T19:12:33.123456+00:00",
  "guildId": "456",
  "type": 0,              // ADD=0, REMOVE=1, TRANSFER=2
  "payer": "SYSTEM",      // or a userId string
  "receiver": "123",      // or "SYSTEM"
  "value": 100
}
```

Settings (server‑level)

`ComplexSetting` composes three `StringSettingFile`s so the guild can change the bank name, the coin name, and the coin symbol. While editing, `_economy_update_embed` renders a live preview embed.

```python
economy_setting = ComplexSetting(
    name="Economy",
    description="Configure server‑wide economy properties",
    id="economy",
    schema={
        "name": StringSettingFile(...),
        "coinName": StringSettingFile(...),
        "coinSymbol": StringSettingFile(...),
    },
    update_fn=_economy_update_embed,
)
```

The setup entrypoint returns an Interfacer and the settings list:

```python
def setup(bot, logger):
    interface = Interfacer(bot, logger)
    return {"interface": interface, "settings": [economy_setting], "userSettings": []}
```

commands/economy.py

This file declares the slash command group and three subcommands, then exposes them via `exports = [economy]` so CommandHandler can register them. The group is named `economy`, which yields `/economy ...` in Discord.

Manage

```python
@economy.command(name="manage")
async def manage(interaction, action: app_commands.Choice[str],
                 member: discord.Member, amount: float,
                 target: Optional[discord.Member] = None):
    """Admin: add, remove, or transfer."""
```

The function checks permissions (Manage Guild or your permission manager), pulls the interfacer from `client.modules["Economy"]`, calls `createTransaction(...)`, and returns a receipt embed. On insufficient funds, it maps the error to a clear message.

Pay

```python
@economy.command(name="pay")
async def pay(interaction, target: discord.Member, amount: float):
    """User‑to‑user transfer."""
```

This is the self‑service version of transfer; it also uses `createTransaction(...)` for confirmation.

Finances

```python
@economy.command(name="finances")
async def finances(interaction):
    """Show balance, last transactions, and provide View History / Export CSV buttons."""
```

The handler reads the current balance from the stored member profile, fetches the last transactions via `consultTransactions(...)`, and renders an embed. Two buttons are attached to the same message:

• View History → refetch up to 50 transactions and present a simple page.
• Export CSV → build a `statement.csv` with a helper that formats rows as `ID,Type,Payer,Receiver,Value,Timestamp`.

The CSV helper in this file is `_csv_for(transactions: List[dict]) -> bytes` and it’s used by the export button callback.

Putting it all together

ModuleHandler loads `manifest.json`, executes `main.py:setup(...)`, and stores the Interfacer under `bot.modules["Economy"].interfacer`. CommandHandler imports `commands/economy.py` and registers the group from `exports`. The slash commands call the Interfacer, which persists balances and transactions. The settings editor lets each guild choose its bank/coin labels without touching code.
