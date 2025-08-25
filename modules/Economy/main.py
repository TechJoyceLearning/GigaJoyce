from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from logging import Logger
from typing import Any, Dict, Optional, List

from discord import Embed, ButtonStyle, Interaction
from discord.ui import Button

from discord.ext import commands

from settings.DefaultTypes.complex import ComplexSetting
from settings.DefaultTypes.string import StringSettingFile
from utils.InteractionView import InteractionView
from shared.types import ExtendedClient
from modules.Economy.types import TransactionType, RemoveErrorReason  # noqa


@dataclass
class EconomyConfig:
    """Resolved, display-friendly config taken from the module setting."""
    name: str
    coin_name: str
    coin_symbol: str


def _resolve_config(raw: Dict[str, Any]) -> EconomyConfig:
    """Convert raw dict from ComplexSetting into a strongly-typed config."""
    return EconomyConfig(
        name=str(raw.get("name") or "Bank"),
        coin_name=str(raw.get("coinName") or "Coin"),
        coin_symbol=str(raw.get("coinSymbol") or "$"),
    )


class Interfacer:
    """
    Runtime API for the Economy module.

    All write operations update two places:
      1) Member balance stored in Mongo collection `members` (per-guild).
      2) Transaction appended to collection `economy_transactions`.
    """

    def __init__(self, client: ExtendedClient, logger: Logger):
        self.client = client
        self.logger = logger.getChild("EconomyInterfacer")
        self.transactions_collection = "economy_transactions"
        self.module_key = "Economy"  # used as the namespaced field under members.settings or members data

    # --------------------------
    # balance helpers
    # --------------------------
    async def _get_member_doc(self, member_id: int, guild_id: int) -> Dict[str, Any]:
        """Fetch (or create) the member profile document."""
        member_id_s, guild_id_s = str(member_id), str(guild_id)
        doc = await self.client.db.find_one("members", {"id": member_id_s, "guildId": guild_id_s})
        if not doc:
            # create a skeleton profile
            await self.client.db.insert_one("members", {"id": member_id_s, "guildId": guild_id_s, self.module_key: {"balance": 0}})
            doc = await self.client.db.find_one("members", {"id": member_id_s, "guildId": guild_id_s})
        if self.module_key not in doc:
            doc[self.module_key] = {"balance": 0}
        elif "balance" not in doc[self.module_key]:
            doc[self.module_key]["balance"] = 0
        return doc

    async def _save_balance(self, member_id: int, guild_id: int, new_balance: int) -> None:
        """Persist new balance in members collection."""
        await self.client.db.update_one(
            "members",
            {"id": str(member_id), "guildId": str(guild_id)},
            {"$set": {f"{self.module_key}.balance": int(new_balance)}},
            upsert=True,
        )

    async def get_balance(self, member_id: int, guild_id: int) -> int:
        """Return current stored balance for a member in a guild."""
        doc = await self._get_member_doc(member_id, guild_id)
        return int(doc.get(self.module_key, {}).get("balance", 0))

    # --------------------------
    # transaction helpers
    # --------------------------
    async def _save_transaction(
        self,
        *,
        guild_id: int,
        tx_type: TransactionType,
        payer: Optional[int],
        receiver: Optional[int],
        value: int,
    ) -> str:
        """
        Persist a transaction in the `economy_transactions` collection.

        Returns:
            str: The generated transaction ID (UUIDv4).
        """
        tx_id = str(uuid.uuid4())
        doc = {
            "transactionId": tx_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "guildId": str(guild_id),
            "type": tx_type.value,
            "payer": str(payer) if payer is not None else "SYSTEM",
            "receiver": str(receiver) if receiver is not None else "SYSTEM",
            "value": int(value),
        }
        await self.client.db.insert_one(self.transactions_collection, doc)
        return tx_id

    async def consultTransactions(
        self,
        user_id: int,
        *,
        guild_id: Optional[int] = None,
        limit: int = 50,
        order: str = "desc",
    ) -> List[Dict[str, Any]]:
        """
        List transactions where the user is payer or receiver.

        Args:
            user_id: Discord user ID.
            guild_id: Optional guild filter.
            limit: Max number of documents.
            order: "asc" or "desc" by timestamp.

        Returns:
            A list of transaction dicts.
        """
        q: Dict[str, Any] = {
            "$or": [{"payer": str(user_id)}, {"receiver": str(user_id)}]
        }
        if guild_id is not None:
            q["guildId"] = str(guild_id)

        # We don't have an index/sort helper in the simple ORM, so keep it simple:
        docs = await self.client.db.find(self.transactions_collection, q)
        docs.sort(key=lambda d: d.get("timestamp", ""), reverse=(order == "desc"))
        return docs[:limit]

    # --------------------------
    # operations
    # --------------------------
    async def add(self, *, user_id: int, guild_id: int, value: int) -> Dict[str, Any]:
        """
        Add `value` coins to a user.

        Returns:
            Dict with transactionId, previous and current balance.
        """
        if value <= 0:
            raise ValueError("Value must be positive.")
        current = await self.get_balance(user_id, guild_id)
        new_balance = current + value
        await self._save_balance(user_id, guild_id, new_balance)

        tx_id = await self._save_transaction(
            guild_id=guild_id, tx_type=TransactionType.ADD_MONEY, payer=None, receiver=user_id, value=value
        )
        return {
            "transactionId": tx_id,
            "userPreviousBalance": current,
            "userCurrentBalance": new_balance,
            "value": value,
            "userId": str(user_id),
        }

    async def remove(self, *, user_id: int, guild_id: int, value: int) -> Dict[str, Any]:
        """
        Remove `value` coins from a user, if they have sufficient funds.

        Raises:
            ValueError on insufficient funds.
        """
        if value <= 0:
            raise ValueError("Value must be positive.")
        current = await self.get_balance(user_id, guild_id)
        if current < value:
            raise ValueError(RemoveErrorReason.INSUFFICIENT_FUNDS.value)
        new_balance = current - value
        await self._save_balance(user_id, guild_id, new_balance)
        tx_id = await self._save_transaction(
            guild_id=guild_id, tx_type=TransactionType.REMOVE_MONEY, payer=user_id, receiver=None, value=value
        )
        return {
            "transactionId": tx_id,
            "userPreviousBalance": current,
            "userCurrentBalance": new_balance,
            "value": value,
            "userId": str(user_id),
        }

    async def transfer(self, *, from_user_id: int, to_user_id: int, guild_id: int, value: int) -> Dict[str, Any]:
        """
        Transfer `value` coins between two users, atomically at the application level.
        """
        if value <= 0:
            raise ValueError("Value must be positive.")
        payer_balance = await self.get_balance(from_user_id, guild_id)
        if payer_balance < value:
            raise ValueError(RemoveErrorReason.INSUFFICIENT_FUNDS.value)

        # apply changes
        await self._save_balance(from_user_id, guild_id, payer_balance - value)
        receiver_balance = await self.get_balance(to_user_id, guild_id)
        await self._save_balance(to_user_id, guild_id, receiver_balance + value)

        tx_id = await self._save_transaction(
            guild_id=guild_id,
            tx_type=TransactionType.TRANSFER_MONEY,
            payer=from_user_id,
            receiver=to_user_id,
            value=value,
        )
        return {
            "transactionId": tx_id,
            "payerPreviousBalance": payer_balance,
            "payerCurrentBalance": payer_balance - value,
            "receiverPreviousBalance": receiver_balance,
            "receiverCurrentBalance": receiver_balance + value,
            "value": value,
            "fromUserId": str(from_user_id),
            "toUserId": str(to_user_id),
        }

    # --------------------------
    # interactive confirm
    # --------------------------
    async def createTransaction(
        self,
        *,
        interaction,
        tx_type: TransactionType,
        user_id: int,
        guild_id: int,
        value: int,
        channel,
        target_user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Show a confirmation view and execute the chosen transaction if confirmed.
        """
        # Build confirmation text
        print(tx_type)
        if tx_type == TransactionType.ADD_MONEY:
            label = f"Add {value} to <@{user_id}>?"
            action = lambda: self.add(user_id=user_id, guild_id=guild_id, value=value)
        elif tx_type == TransactionType.REMOVE_MONEY:
            label = f"Remove {value} from <@{user_id}>?"
            action = lambda: self.remove(user_id=user_id, guild_id=guild_id, value=value)
        elif tx_type == TransactionType.TRANSFER_MONEY:
            if target_user_id is None:
                raise ValueError("target_user_id is required for TRANSFER.")
            label = f"Transfer {value} from <@{user_id}> to <@{target_user_id}>?"
            action = lambda: self.transfer(from_user_id=user_id, to_user_id=target_user_id, guild_id=guild_id, value=value)
        else:
            raise ValueError("Invalid transaction type.")

        # View + buttons
        view = InteractionView(interaction=interaction, channel=channel, client=self.client, ephemeral=False, timeout=60_000)

        result: Dict[str, Any] = {}

        async def _confirmed(_i: Interaction):
            nonlocal result
            await view.update(content=label, components=[])
            result = await action()
            view.stop()

        async def _canceled(_i: Interaction):
            view.destroy("canceled")
            raise RuntimeError("Transaction canceled by user.")

        # wire our simple events
        
        confirm = Button(label="Confirm", style=ButtonStyle.success, custom_id="confirm_transaction")
        confirm.callback = _confirmed

        cancel = Button(label="Cancel", style=ButtonStyle.danger, custom_id="cancel_transaction")
        cancel.callback = _canceled

        buttons = [confirm, cancel]
        
        await view.update(content=label, components=buttons)

        await view.wait()

        print(f"result: {result}")
        return result


# --------------------------
# Settings (server-level)
# --------------------------
async def _economy_update_embed(value: Dict[str, Any], view: InteractionView) -> Embed:
    """
    Compose the preview embed for the ComplexSetting editor.
    """
    cfg = _resolve_config(value or {})
    e = Embed(
        title="Economy",
        description="Server economy configuration",
        color=0xDACCFF,
    )
    e.add_field(name="Bank Name", value=cfg.name or "—", inline=True)
    e.add_field(name="Coin Name", value=cfg.coin_name or "—", inline=True)
    e.add_field(name="Coin Symbol", value=cfg.coin_symbol or "—", inline=True)
    return e


def setup(bot: ExtendedClient, logger: Logger):
    """
    Module setup entrypoint. Called by ModuleHandler._execute_setup.

    Returns:
        dict: {"interface": <Interfacer>, "settings": [Setting, ...], "userSettings": []}
    """
    economy_setting = ComplexSetting(
        name="Economy",
        description="Configure server-wide economy properties",
        id="economy",
        schema={
            "name": StringSettingFile(
                name="Bank name",
                description="Display name for your bank.",
                id="name",
                color="#eee8ff",
            ),
            "coinName": StringSettingFile(
                name="Coin name",
                description="Human-readable name of your currency.",
                id="coinName",
                color="#eee8ff",
            ),
            "coinSymbol": StringSettingFile(
                name="Coin symbol",
                description="Symbol shown next to values (e.g. $, R$, ¥).",
                id="coinSymbol",
                color="#eee8ff",
            ),
        },
        update_fn=_economy_update_embed,
    )

    interface = Interfacer(bot, logger)
    return {
        "interface": interface,
        "settings": [economy_setting],
        "userSettings": [],
    }
