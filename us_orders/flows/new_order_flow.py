from typing import Optional

from us.models import TimeframeKlineSignal, StrategyVariables

from us_orders.models.order import Order
from us_orders.models.order_group import OrderGroup
from us_orders.helpers import get_or_create_latest_order_group_for_side, is_order_group_allowing_orders, update_algo_order, \
    create_order, create_algo_order, get_attributes_for_order, update_order

from woo.models import WooAlgoOrder


def handle_new_signal(
    timeframe_group_id: int,
    sgnl: TimeframeKlineSignal,
    strategy_vars: StrategyVariables
):
    # TODO - do i need to rethink the order in which this is executed? If any of the API calls fail
    # it can end up in an inconsistent state. Empty group with no order. Or active group with no stop order
    # Maybe this should just be a get not an or create?
    order_group = get_or_create_latest_order_group_for_side(sgnl.type, timeframe_group_id)

    if not is_order_group_allowing_orders(order_group):
        return

    # if the new order is part of an active group
    # if the group has a stop order it only needs to be updated once an order on this side is filled
    if order_group.is_active:
        order, created = create_or_update_order(
            sgnl,
            strategy_vars,
            order_group.id,
            order_group.current_pending_order
        )
        if created:
            order_group.orders.add(order)
    else:

        # this should be 'get_group_for_side(opposite side to sgnl)' then if not None and active, create or update stop
        active_group = OrderGroup.objects.get_current_active_group()
        stop_created = False
        stop = None
        '''
        There's an issue here - the way in which group.is_active is calculated
        is different to the way in which OrderGroup.objects.get_current_active_group is determined.

        OrderGroup.objects.get_current_active_group is incorrect as it calculates the active group
        by getting the latest FILLED order on that side.

        This creates a problem here as the active_group returned can be the same as order_group
        even though order_group.is_active is False.
        '''
        if active_group is not None and active_group != order_group:
            stop, stop_created = create_or_update_stop_order_for_group(active_group, sgnl, strategy_vars)

        order, order_created = create_or_update_order(
            sgnl,
            strategy_vars,
            order_group.id,
            order_group.current_pending_order
        )

        if order_created:
            order_group.orders.add(order)

        if stop_created:
            active_group.set_stop(stop)


def create_or_update_order(
    sgnl: TimeframeKlineSignal,
    strategy_vars: StrategyVariables,
    order_group_id: int,
    order: Optional[Order] = None
) -> (Order, bool):

    order_attributes = get_attributes_for_order(sgnl, strategy_vars)
    created = False

    if order:
        order = update_order(
            sgnl,
            order,
            order_attributes
        )

    else:
        order = create_order(
            sgnl,
            order_tag=f'group-{order_group_id}-order',
            **order_attributes
        )
        created = True

    return order, created


def create_or_update_stop_order_for_group(
    order_group: OrderGroup,
    sgnl: TimeframeKlineSignal,
    strategy_vars: StrategyVariables
) -> (WooAlgoOrder, bool):

    order_attributes = get_attributes_for_order(sgnl, strategy_vars)
    stop = order_group.stop
    created = False

    if order_group.side == order_attributes['side']:
        raise Exception('Order must be on the opposite side to the group')

    if stop is not None:
        updated_trigger_price = order_attributes['trigger_price']
        if stop.trigger_price != updated_trigger_price:
            update_algo_order(stop, {
                'triggerPrice': updated_trigger_price
            })
    else:
        stop = create_algo_order(
            order_attributes['symbol'],
            order_attributes['side'],
            str(order_group.quantity),
            True,
            str(order_attributes['trigger_price']),
            f'group-{order_group.id}-closer'
        )
        created = True

    return stop, created