# modules/Economy/types.py
from enum import IntEnum
from typing import TypedDict


class RemoveErrorReason(IntEnum):
    """Reasons for failing a removal/transfer operation."""
    INSUFFICIENT_FUNDS = 0


class TransactionType(IntEnum):
    """Kinds of economy transactions."""
    ADD_MONEY = 0
    REMOVE_MONEY = 1
    TRANSFER_MONEY = 2


class EconomySettings(TypedDict):
    """Config stored by the module's ComplexSetting."""
    name: str
    coinName: str
    coinSymbol: str
