from __future__ import annotations

from enum import Enum

import sys

if sys.version_info < (3, 11):
    from typing_extensions import TypedDict, NotRequired
else:
    from typing import TypedDict, NotRequired


class AlgoOrderStatus(str, Enum):
    NEW = "NEW"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    FILLED = "FILLED"
    PARTIAL_FILLED = "PARTIAL_FILLED"
    REPLACED = "REPLACED"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    IOC = "IOC"
    FOK = "FOK"
    ONLY = "POST_ONLY"
    ASK = "ASK"
    BID = "BID"


class AlgoType(str, Enum):
    STOP = "STOP"
    OCO = "OCO"


class AlgoOrderUpdateRequestParams(TypedDict):
    quantity: NotRequired[str]
    triggerPrice: NotRequired[str]


class AlgoOrderRequestParams(TypedDict):
    quantity: str
    triggerPrice: str
    symbol: str
    side: OrderSide
    reduceOnly: bool
    type: OrderType
    algoType: AlgoType
    orderTag: NotRequired[str]


class AlgoOrderResponseData(AlgoOrderRequestParams):
    algoOrderId: int
    algoStatus: AlgoOrderStatus
    isTriggered: bool
    triggerStatus: str
    triggerTradePrice: float
    triggerPriceType: str
    triggerTime: int
    tradeId: int
    createdTime: int
    updatedTime: int
    executedPrice: float
    executedQuantity: float
    totalExecutedQuantity: str
    averageExecutedPrice: str
    realizedPnl: float
