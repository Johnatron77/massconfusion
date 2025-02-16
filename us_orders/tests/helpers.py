from typing import Optional

from us_orders.models.order import Order
from us_orders.models.order_group import OrderGroup
from us_orders.tests.factory.order_factory import OrderFactory
from us_orders.tests.factory.order_group_factory import OrderGroupFactory
from woo.api_types import OrderSide, AlgoOrderRequestParams, OrderType, AlgoType, AlgoOrderStatus


class MockResponse:

    def __init__(self, json_data: dict, status_code: int = 200):
        self.status_code = status_code
        self.json_data = json_data

    def json(self) -> dict:
        return {"success": self.status_code == 200, "data": self.json_data}


def create_order_for_test(
    side: OrderSide,
    trigger_price: float,
    stop_loss_difference: float,
    status: Optional[AlgoOrderStatus] = None,
    quantity: float = 0.1,
    trigger_trade_price: float = 0.0
) -> (Order, OrderGroup):
    order = OrderFactory(
        direction=side.value,
        order__trigger_price=trigger_price,
        order__trigger_trade_price=trigger_trade_price,
        order__quantity=quantity
    )
    group = OrderGroupFactory(side=side.value, orders=[order], group__strategy_variables__stop_loss_difference=stop_loss_difference)
    if status:
        order.order.status = status.value
    order.order.save()
    return order, group


def get_expected_params_for_reduce_only_order(
    symbol: str,
    side: OrderSide,
    quantity: float,
    trigger_price: str,
    order_tag: str
) -> AlgoOrderRequestParams:
    return {
        "symbol": symbol,
        "side": side,
        "reduceOnly": True,
        "type": OrderType.MARKET.value,
        "quantity": str(quantity),
        "algoType": AlgoType.STOP.value,
        "triggerPrice": trigger_price,
        "orderTag": order_tag,
        'orderCombinationType': 'STOP_MARKET',
    }


def get_count_of_orders_on_side_with_status(side: OrderSide, status: AlgoOrderStatus) -> int:
    return len(list(filter(lambda o: o.side == side and o.status == status, Order.objects.all())))


def get_count_of_stop_orders_on_side_with_status(side: OrderSide, status: AlgoOrderStatus) -> int:
    return len(list(filter(lambda o: o.stop is not None and o.stop.side == side and o.stop.status == status, Order.objects.all())))