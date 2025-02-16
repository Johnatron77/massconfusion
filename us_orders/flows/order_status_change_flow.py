from typing import Optional

from us_orders.models.order import Order
from us_orders.models.order_group import OrderGroup
from us_orders.helpers import create_stop_for_order, get_opposite_side_to_order, \
    cancel_all_pending_stop_orders_for_side, cancel_all_pending_orders_for_side, \
    cancel_pending_order_group_stop, update_or_cancel_order_group_stop
from woo.helpers import map_woo_algo_order_data

from woo.models import WooAlgoOrder
from woo.api_types import AlgoOrderResponseData, AlgoOrderStatus


def handle_market_order(data: dict):
    if data.get('reduceOnly') is True:
        handle_reduce_only_market_order(data)
    elif data.get('reduceOnly') is False:
        handle_non_reduce_only_market_order(data)


def handle_reduce_only_market_order(data: dict):
    # get active order group
    # does group have stop?
    # if yes, does quantity match?
    # if yes, update stop
    # if no, does quantity match?
    # if yes, create stop
    # is stop filled?
    # cancel all pending stop orders for side
    active_group = OrderGroup.objects.get_current_active_group()

    if active_group is None:
        return

    stop = active_group.stop

    if stop is None:
        return


def handle_non_reduce_only_market_order(data: dict):
    pass


def handle_algo_order_update(data: AlgoOrderResponseData):

    status = get_new_status(data)

    if status is None:
        return

    order_id = data.get('algoOrderId')

    if status == AlgoOrderStatus.FILLED:
        handle_filled_order(order_id, data)
    elif status == AlgoOrderStatus.CANCELLED:
        handle_cancelled_order(order_id, data)
    elif status == AlgoOrderStatus.REJECTED:
        handle_rejected_order(order_id, data)


def get_new_status(data: AlgoOrderResponseData) -> Optional[AlgoOrderStatus]:
    order_id = data.get('algoOrderId')

    if order_id is None:
        return None

    status = data.get('algoStatus')

    # dirty fix for missing woo ws status updates ###############
    if data.get('isTriggered') and status == AlgoOrderStatus.NEW:
        data['algoStatus'] = AlgoOrderStatus.FILLED.value
    if status == AlgoOrderStatus.PARTIAL_FILLED:
        data['algoStatus'] = AlgoOrderStatus.FILLED.value
    ##############################################################

    if status == AlgoOrderStatus.REPLACED:
        data['algoStatus'] = AlgoOrderStatus.NEW.value

    new_status = data.get('algoStatus')

    try:
        algo_order = WooAlgoOrder.objects.get(order_id=order_id)
        current_status = algo_order.status
    except WooAlgoOrder.DoesNotExist:
        return None

    WooAlgoOrder.objects.update_or_create(
        order_id=order_id,
        defaults=map_woo_algo_order_data(data)
    )

    if current_status is None or current_status == new_status:
        return None

    return new_status


def handle_filled_order(order_id: int, data: AlgoOrderResponseData):
    reduce_only = data.get('reduceOnly')
    if reduce_only is True:
        handle_filled_reduce_only_order_update(order_id)
    elif reduce_only is False:
        handle_filled_non_reduce_only_order_update(order_id)


def handle_cancelled_order(order_id: int, data: AlgoOrderResponseData):
    pass


def handle_rejected_order(order_id: int, data: AlgoOrderResponseData):
    pass


def handle_filled_reduce_only_order_update(order_id: int):
    order = Order.objects.get_order_by_order_id(order_id)
    if order:
        handle_filled_stop_for_individual_order(order)
        return
    order_group = OrderGroup.objects.get_group_by_stop_order_id(order_id)
    if order_group is None:
        return
    handle_filled_stop_for_order_group(order_group)


def handle_filled_non_reduce_only_order_update(order_id: int):
    order = Order.objects.get_order_by_order_id(order_id)
    if order is None:
        return
    side = get_opposite_side_to_order(order)
    cancel_all_pending_orders_for_side(side)
    cancel_pending_order_group_stop(order.order_groups.first())
    create_stop_for_order(order)


def handle_filled_stop_for_individual_order(order: Order):
    order_group = OrderGroup.objects.get_group_by_order(order)
    if order_group is None:
        return
    if order_group.has_reached_max_consecutive_order_stops_limit:
        # TODO - handle reverse
        return
    if order_group.has_stop and (order_group.is_active or order_group.is_closed):
        update_or_cancel_order_group_stop(order_group)


def handle_filled_stop_for_order_group(order_group: OrderGroup):
    stop = order_group.stop
    cancel_all_pending_stop_orders_for_side(stop.side)
