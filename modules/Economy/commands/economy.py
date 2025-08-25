# modules/Economy/commands/economy.py
from __future__ import annotations

from typing import Optional, List
import datetime
import io

import discord
from discord import app_commands, Interaction, Embed, ButtonStyle
from discord.ui import Button, View

"""
Slash command group for the Economy module.

Commands:
    /economy manage: Admin operations (add/remove/transfer funds).
    /economy pay: User-to-user transfer.
    /economy finances: Show balance, recent transactions, and provide options to view history or export CSV.
"""

try:
    from modules.Economy.types import TransactionType, RemoveErrorReason
except Exception:
    class RemoveErrorReason:
        """Reasons for failed removals."""
        INSUFFICIENT_FUNDS = 0

    class TransactionType:
        """Transaction types."""
        ADD_MONEY = 0
        REMOVE_MONEY = 1
        TRANSFER_MONEY = 2


def _coin_strings(guild_profile) -> tuple[str, str, str]:
    """
    Build display strings for bank name, coin symbol, and coin name from guild settings.

    Args:
        guild_profile: Guild profile object.

    Returns:
        tuple[str, str, str]: (bank_name, coin_symbol, coin_name)
    """
    settings = getattr(guild_profile, "settings", {}) or {}
    econ = settings.get("economy")
    econ_val = getattr(econ, "value", None) if econ else None

    bank_name = (econ_val or {}).get("name") or str(guild_profile.guild)
    coin_symbol = (econ_val or {}).get("coinSymbol") or "R$"
    coin_name = (econ_val or {}).get("coinName") or guild_profile.guild
    return bank_name, coin_symbol, coin_name


def _csv_for(transactions: List[dict]) -> bytes:
    """
    Create a CSV file (bytes) for a list of transactions.

    Args:
        transactions: List of transaction dictionaries.

    Returns:
        bytes: CSV encoded as UTF-8.
    """
    headers = ["ID", "Type", "Payer", "Receiver", "Value", "Timestamp"]
    lines = [",".join(headers)]
    for tx in transactions:
        row = [
            f"\"{tx.get('id','')}\"",
            f"\"{tx.get('type','')}\"",
            f"\"{tx.get('payer','')}\"",
            f"\"{tx.get('receiver','')}\"",
            f"\"{tx.get('value','')}\"",
            f"\"{tx.get('timestamp','')}\"",
        ]
        lines.append(",".join(row))
    return "\n".join(lines).encode("utf-8")


economy = app_commands.Group(
    name="economy",
    description="Manage the guild economy and view finances.",
)


@economy.command(name="manage", description="Admin: add, remove, or transfer funds.")
@app_commands.describe(
    action="Transaction type",
    member="Target member",
    amount="Transaction amount",
    target="Destination member (required for transfer)",
)
@app_commands.choices(
    action=[
        app_commands.Choice(name="Add", value="add"),
        app_commands.Choice(name="Remove", value="remove"),
        app_commands.Choice(name="Transfer", value="transfer"),
    ]
)
async def manage(
    interaction: Interaction,
    action: app_commands.Choice[str],
    member: discord.Member,
    amount: float,
    target: Optional[discord.Member] = None,
):
    """
    Perform an administrative transaction.

    Args:
        interaction: Discord interaction object.
        action: Type of transaction.
        member: Target member.
        amount: Transaction amount.
        target: Destination member (for transfers).
    """
    await interaction.response.defer(ephemeral=False, thinking=True)

    can_manage = False
    if isinstance(interaction.user, discord.Member):
        if interaction.user.guild_permissions.manage_guild:
            can_manage = True
        else:
            perm = getattr(interaction.client, "permission_manager", None)
            if perm and hasattr(perm, "check_permission_for"):
                can_manage = await perm.check_permission_for(
                    "economy.manage", interaction.user, interaction.channel  # type: ignore[arg-type]
                )
    if not can_manage:
        return await interaction.edit_original_response(
            content="You don't have permission to run this command."
        )

    mod = getattr(interaction.client, "modules", {}).get("Economy")
    if not mod or not getattr(mod, "interfacer", None):
        return await interaction.edit_original_response(content="Economy module is not initialized.")
    iface = mod.interfacer

    guild_profile = await interaction.client.guild_manager.fetch_or_create(str(interaction.guild_id))
    user = await interaction.client.member_manager.fetch_or_create(member.id, interaction.guild_id)
    bank_name, coin_symbol, _ = _coin_strings(guild_profile)
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        if action.value == "add":           
            res = await iface.createTransaction(
                interaction=interaction,
                tx_type=TransactionType.ADD_MONEY,
                user_id=member.id,
                guild_id=str(interaction.guild_id),
                value=amount,
                channel=interaction.channel,
            )
            emb = Embed(
                title="✅ Transaction – Add",
                description=f"Added **{coin_symbol}{amount}** to <@{member.id}>.",
                color=0x00AE86,
            )
            emb.add_field(name="Previous Balance", value=f"{coin_symbol}{res['userPreviousBalance']}", inline=True)
            emb.add_field(name="Current Balance", value=f"{coin_symbol}{res['userCurrentBalance']}", inline=True)
            emb.set_footer(text=f"Executed at {now_str}")
            return await interaction.edit_original_response(embeds=[emb])

        if action.value == "remove":
            res = await iface.createTransaction(
                interaction=interaction,
                tx_type=TransactionType.REMOVE_MONEY,
                user_id=member.id,
                guild_id=str(interaction.guild_id),
                value=amount,
                channel=interaction.channel,
            )
            emb = Embed(
                title="✅ Transaction – Remove",
                description=f"Removed **{coin_symbol}{amount}** from <@{member.id}>.",
                color=0xE74C3C,
            )
            emb.add_field(name="Previous Balance", value=f"{coin_symbol}{res['userPreviousBalance']}", inline=True)
            emb.add_field(name="Current Balance", value=f"{coin_symbol}{res['userCurrentBalance']}", inline=True)
            emb.set_footer(text=f"Executed at {now_str}")
            return await interaction.edit_original_response(embeds=[emb])

        if action.value == "transfer":
            if target is None:
                return await interaction.edit_original_response(
                    content="For transfer, you must provide a destination member."
                )
            dest = await interaction.client.member_manager.fetch_or_create(target.id, interaction.guild_id)
            res = await iface.createTransaction(
                interaction=interaction,
                tx_type=TransactionType.TRANSFER_MONEY,
                user_id=member.id,
                guild_id=str(interaction.guild_id),
                value=amount,
                channel=interaction.channel,
                target_user_id=target.id,
            )
            emb = Embed(
                title="✅ Transaction – Transfer",
                description=f"Transferred **{coin_symbol}{amount}** from <@{member.id}> to <@{target.id}>.",
                color=0x3498DB,
            )
            emb.add_field(name="Sender (Prev.)", value=f"{coin_symbol}{res['payerPreviousBalance']}", inline=True)
            emb.add_field(name="Sender (Curr.)", value=f"{coin_symbol}{res['payerCurrentBalance']}", inline=True)
            emb.add_field(name="Receiver (Prev.)", value=f"{coin_symbol}{res['receiverPreviousBalance']}", inline=True)
            emb.add_field(name="Receiver (Curr.)", value=f"{coin_symbol}{res['receiverCurrentBalance']}", inline=True)
            emb.set_footer(text=f"Executed at {now_str}")
            return await interaction.edit_original_response(embeds=[emb])

        return await interaction.edit_original_response(content="Invalid action.")
    except Exception as e:
        reason = getattr(e, "reason", None)
        msg = "Insufficient funds." if reason == RemoveErrorReason.INSUFFICIENT_FUNDS else "Unknown error, contact the dev <@840707271385284628>."
        if reason != RemoveErrorReason.INSUFFICIENT_FUNDS:
            print(f"Unexpected error during transaction: {e}")
        return await interaction.edit_original_response(content=f"Could not complete the transaction: {msg}")


@economy.command(name="pay", description="Transfer money from your account to another member.")
@app_commands.describe(target="Member to receive the payment", amount="Amount to pay")
async def pay(
    interaction: Interaction,
    target: discord.Member,
    amount: float,
):
    """
    Peer-to-peer transfer: current user → target member.

    Args:
        interaction: Discord interaction object.
        target: Receiving member.
        amount: Transfer amount.
    """
    await interaction.response.defer(ephemeral=False, thinking=True)

    mod = getattr(interaction.client, "modules", {}).get("Economy")
    if not mod or not getattr(mod, "interfacer", None):
        return await interaction.edit_original_response(content="Economy module is not initialized.")
    iface = mod.interfacer

    origin = await interaction.client.member_manager.fetch_or_create(interaction.user.id, interaction.guild_id)
    dest = await interaction.client.member_manager.fetch_or_create(target.id, interaction.guild_id)
    guild_profile =  await interaction.client.guild_manager.fetch_or_create(str(interaction.guild_id))
    bank_name, coin_symbol, _ = _coin_strings(guild_profile)
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        res = await iface.createTransaction(
            interaction=interaction,
            tx_type=TransactionType.TRANSFER_MONEY,
            user_id=interaction.user.id,
            guild_id=str(interaction.guild_id),
            value=amount,
            channel=interaction.channel,
            target_user_id=target.id,
        )
        emb = Embed(
            title="✅ Payment Completed",
            description=f"You transferred **{coin_symbol}{amount}** to <@{target.id}>.",
            color=0x00AE86,
        )
        emb.add_field(name="Your Balance (Prev.)", value=f"{coin_symbol}{res['payerPreviousBalance']}", inline=True)
        emb.add_field(name="Your Balance (Curr.)", value=f"{coin_symbol}{res['payerCurrentBalance']}", inline=True)
        emb.add_field(name="Receiver (Prev.)", value=f"{coin_symbol}{res['receiverPreviousBalance']}", inline=True)
        emb.add_field(name="Receiver (Curr.)", value=f"{coin_symbol}{res['receiverCurrentBalance']}", inline=True)
        emb.set_footer(text=f"Executed at {now_str}")
        return await interaction.edit_original_response(embeds=[emb])
    except Exception as e:
        reason = getattr(e, "reason", None)
        msg = "Insufficient funds." if reason == RemoveErrorReason.INSUFFICIENT_FUNDS else "Unknown error, contact the dev <@840707271385284628>."
        if reason != RemoveErrorReason.INSUFFICIENT_FUNDS:
            print(f"Unexpected error during payment: {e}")
        return await interaction.edit_original_response(content=f"Could not complete the transaction: {msg}")


def _balance_from_profile_data(data: dict) -> int:
    """
    Extract balance value from a stored profile.

    Args:
        data: Profile data dictionary.

    Returns:
        int: Balance value or 0 if not found.
    """
    if not isinstance(data, dict):
        return 0
    econ = data.get("economy")
    if isinstance(econ, dict) and isinstance(econ.get("balance"), (int, float)):
        return int(econ["balance"])
    econ = data.get("Economy")
    if isinstance(econ, dict) and isinstance(econ.get("balance"), (int, float)):
        return int(econ["balance"])
    return 0


@economy.command(name="finances", description="Show your balance summary and recent transactions.")
async def finances(interaction: Interaction):
    """
    Display summary card with balance, recent transactions, and options for history/CSV.

    Args:
        interaction: Discord interaction object.
    """
    await interaction.response.defer(ephemeral=False, thinking=True)

    client = interaction.client

    economy_module = getattr(client, "modules", {}).get("economy") or \
                     getattr(client, "modules", {}).get("Economy")
    if not economy_module or not getattr(economy_module, "interfacer", None):
        return await interaction.edit_original_response(
            content="Economy module is not available right now."
        )
    interfacer = economy_module.interfacer

    try:
        user_profile = await client.member_manager.fetch_or_create(
            str(interaction.user.id),
            str(interaction.guild_id)
        )
    except Exception:
        return await interaction.edit_original_response(content="Profile unavailable right now.")

    data = getattr(user_profile, "data", {}) or {}
    balance = _balance_from_profile_data(data)

    guild_profile = await client.guild_manager.fetch_or_create(str(interaction.guild_id))
    bank_name, coin_symbol, _ = _coin_strings(guild_profile)
    now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    try:
        txs = await interfacer.consultTransactions(
            str(interaction.user.id),
            guild_id=str(interaction.guild_id),
            limit=7,
            order="desc"
        )
    except Exception as e:
        print(f"Error while consulting transactions: {e}")
        return await interaction.edit_original_response(content="An error occurred, contact dev <@840707271385284628> for support.")
        txs = []

    embed = Embed()
    embed.set_author(
        name=bank_name,
        icon_url=(interaction.guild.icon.url if interaction.guild and interaction.guild.icon else None)
    )
    embed.description = f"## Welcome <@{interaction.user.id}>!"
    embed.add_field(name="Balance", value=f"{coin_symbol}{balance}", inline=False)
    embed.add_field(name="Last Check", value=now_str, inline=False)
    embed.add_field(name="\u200B", value="**Last 7 Transactions:**", inline=False)

    def tx_value_str(tx: dict) -> str:
        t = tx.get("type")
        v = tx.get("value")
        if t == TransactionType.ADD_MONEY:
            return f"+{coin_symbol}{v}"
        if t == TransactionType.REMOVE_MONEY:
            return f"-{coin_symbol}{v}"
        if t == TransactionType.TRANSFER_MONEY:
            if tx.get("payer") == str(interaction.user.id):
                return f"-{coin_symbol}{v}"
            if tx.get("receiver") == str(interaction.user.id):
                return f"+{coin_symbol}{v}"
        return f"{coin_symbol}{v}"

    for idx, tx in enumerate(txs[:7]):
        ts = tx.get("timestamp") or ""
        try:
            dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
            ts_fmt = dt.strftime("%d/%m/%Y %H:%M:%S")
        except Exception:
            ts_fmt = ts
        payer = "SYSTEM" if tx.get("payer") == "SYSTEM" else f"<@{tx.get('payer')}>"
        recv  = "SYSTEM" if tx.get("receiver") == "SYSTEM" else f"<@{tx.get('receiver')}>"
        embed.add_field(
            name=f"Transaction {idx + 1}",
            value=f"**ID:** {tx.get('id')}\n**From:** {payer}\n**To:** {recv}\n**Value:** {tx_value_str(tx)}\n**Date:** {ts_fmt}",
            inline=False
        )

    embed.color = 0x3498DB
    embed.set_footer(
        text=f"Summary issued at {now_str}",
        icon_url=(interaction.guild.icon.url if interaction.guild and interaction.guild.icon else None)
    )

    view = View(timeout=300)
    btn_history = Button(custom_id="view_history", label="View History", style=ButtonStyle.primary)
    btn_export  = Button(custom_id="export_csv",  label="Export CSV",   style=ButtonStyle.secondary)
    view.add_item(btn_history)
    view.add_item(btn_export)

    async def on_history(btn_inter: Interaction):
        await btn_inter.response.defer()
        try:
            full = await interfacer.consultTransactions(
                str(interaction.user.id),
                guild_id=str(interaction.guild_id),
                limit=50,
                order="desc"
            )
        except Exception as e:
            print(f"Error while loading history: {e}")
            return await interaction.followup.send("Failed to load history.", ephemeral=True)

        hist = Embed(title="📜 Transaction History")
        if not full:
            hist.description = "No transactions found."
        else:
            for tx in full[:10]:
                dt = datetime.datetime.fromisoformat(tx.get('timestamp', ''))
                readable = dt.strftime("%m/%d/%Y %H:%M:%S")
                payer = "SYSTEM" if tx.get("payer") == "SYSTEM" else f"<@{tx.get('payer')}>"
                recv  = "SYSTEM" if tx.get("receiver") == "SYSTEM" else f"<@{tx.get('receiver')}>"
                hist.add_field(
                    name=readable,
                    value=f"{payer} → {recv} | {tx_value_str(tx)} | {tx.get('_id','')}",
                    inline=False
                )
        await interaction.edit_original_response(embeds=[hist], view=view)

    async def on_export(btn_inter: Interaction):
        await btn_inter.response.defer()
        try:
            full = await interfacer.consultTransactions(
                str(interaction.user.id),
                guild_id=str(interaction.guild_id),
                limit=10000,
                order="desc"
            )
            csv_bytes = _csv_for(full)
            file = discord.File(io.BytesIO(csv_bytes), filename="statement.csv")
            await interaction.followup.send(content="Statement generated.", file=file, ephemeral=False)
        except Exception as e:
            print(f"Error while exporting CSV: {e}")
            await interaction.followup.send("Could not export your statement (unknown error).", ephemeral=True)

    btn_history.callback = on_history
    btn_export.callback  = on_export

    await interaction.edit_original_response(embeds=[embed], view=view)


exports = [economy]
