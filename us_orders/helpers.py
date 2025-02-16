from typing import Optional

from us.models import TimeframeKlineSignal, StrategyVariables
from us_orders.models.order import Order
from us_orders.models.order_group import OrderGroup

from woo.api_types import OrderSide
from woo.helpers import create_algo_order, update_algo_order, cancel_algo_order


def remove_none_values_from_dict(d: dict):
    return {k: v for k, v in d.items() if v is not None}


def get_opposite_side_to_order(order: Order) -> OrderSide:
    return [OrderSide.BUY, OrderSide.SELL][order.side == 'BUY']


def get_trigger_price_for_order(side: OrderSide, low: float, high: float, diff: float)-> float:
    return [low - diff, high + diff][side == OrderSide.BUY]


def get_trigger_price_for_stop_order(order: Order) -> float:
    order_group = OrderGroup.objects.get_group_by_order(order)
    algo_order = order.order
    trigger_trade_price = 0 if algo_order.trigger_trade_price is None else algo_order.trigger_trade_price
    order_trigger_price = float(trigger_trade_price) if trigger_trade_price != 0 else float(algo_order.trigger_price)
    diff = order_group.group.strategy_variables.stop_loss_difference
    side = get_opposite_side_to_order(order)
    if side == OrderSide.BUY:
        diff = -diff
    return order_trigger_price - diff


def get_attributes_for_order(sgnl: TimeframeKlineSignal,strategy_vars: StrategyVariables):
    tf_kline = sgnl.timeframe_kline
    side = [OrderSide.BUY, OrderSide.SELL][sgnl.type == 'SELL']
    diff = strategy_vars.trigger_price_difference
    trigger_price = get_trigger_price_for_order(side, float(tf_kline.low), float(tf_kline.high), diff)

    return {
        'symbol': tf_kline.symbol.type,
        'side': side,
        'quantity': strategy_vars.get_quantity(),
        'trigger_price': trigger_price,
    }


def get_or_create_latest_order_group_for_side(side: str, timeframe_group_id: int) -> OrderGroup:
    order_group: Optional[OrderGroup] = OrderGroup.objects.get_latest_group_for_side(side)

    if not order_group or order_group.is_closed:
        order_group = OrderGroup.objects.create(
            group_id=timeframe_group_id,
            side=side
        )

    return order_group


def is_order_group_allowing_orders(order_group: OrderGroup) -> bool:

    if not order_group.has_exceeded_allowed_minutes_since_last_filled_order:
        return False

    if order_group.has_reached_max_order_limit:
        return False

    return True


def create_order(
    sgnl: TimeframeKlineSignal,
    symbol: str,
    side: OrderSide,
    quantity: float,
    trigger_price: float,
    order_tag: str
) -> Optional[Order]:

    algo_order = create_algo_order(
        symbol,
        side,
        str(quantity),
        False,
        str(trigger_price),
        order_tag
    )

    return Order.objects.create(indicator=sgnl, order=algo_order)


def update_order(
    sgnl: TimeframeKlineSignal,
    order: Order,
    order_attributes: dict
) -> Optional[Order]:
    updated_trigger_price = order_attributes['trigger_price']
    if order.trigger_price != updated_trigger_price:
        update_algo_order(order.order, {
            'triggerPrice': updated_trigger_price
        })
    order.update_indicator(sgnl)
    return order


def create_stop_for_order(order: Order):
    side = get_opposite_side_to_order(order)
    trigger_price = get_trigger_price_for_stop_order(order)

    stop = create_algo_order(
        order.order.symbol,
        side,
        str(order.quantity),
        True,
        str(trigger_price),
        f'stop-for-{order.order_id}'
    )

    order.set_stop(stop)


def cancel_all_pending_stop_orders_for_side(side: str):
    for ordr in Order.objects.get_all_pending_reduce_only_orders_for_side(side):
        cancel_algo_order(ordr.stop)


def cancel_all_pending_orders_for_side(side: str):
    for ordr in Order.objects.get_all_pending_non_reduce_only_orders_for_side(side):
        cancel_algo_order(ordr.order)


def cancel_pending_order_group_stop(order_group: OrderGroup):
    stop = order_group.stop
    if stop is None or stop.status != 'NEW':
        return
    cancel_algo_order(stop)


def update_or_cancel_order_group_stop(order_group: OrderGroup):
    stop = order_group.stop
    if order_group.quantity == 0:
        order_group.set_stop(None)
        cancel_algo_order(stop)
    else:
        update_algo_order(stop, {'quantity': order_group.quantity})
