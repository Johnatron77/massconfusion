from typing import Optional

from common.util.cls import map_data_to_class

from woo.api_rest import send_algo_order, edit_algo_order, cancel_algo_order as cancel_algo_order_api
from woo.api_types import AlgoOrderRequestParams, AlgoOrderUpdateRequestParams, OrderSide, OrderType, AlgoType
from woo.models import WooAlgoOrder


def _value_converter(k, v):
    if k == 'trigger_time':
        return v / 1000
    if k == 'trigger_price':
        return float(v)
    return v


def map_woo_algo_order_data(data: dict) -> dict:
    return map_data_to_class(
        WooAlgoOrder,
        data,
        {'algoStatus': 'status', 'createdTime': 'create_time'},
        _value_converter
    )


def create_algo_order(
    symbol: str,
    side: OrderSide,
    quantity: str,
    reduce_only: bool,
    trigger_price: str,
    order_tag: Optional[str] = None
) -> Optional[WooAlgoOrder]:

    params = create_algo_order_params(
        symbol,
        side,
        quantity,
        reduce_only,
        trigger_price,
        order_tag
    )

    order = send_algo_order(params)

    if order is None:
        print(f'There was an issue making the order for {params}')
        return None

    rows = order.get('rows', [])

    if len(rows) == 0:
        return None

    order_data = rows[0]

    return WooAlgoOrder.objects.create(
        **map_woo_algo_order_data({**params, **order_data})
    )


def create_algo_order_params(
    symbol: str,
    side: OrderSide,
    quantity: str,
    reduce_only: bool,
    trigger_price: str,
    order_tag: Optional[str] = None
) -> AlgoOrderRequestParams:

    params: AlgoOrderRequestParams = {
        "symbol": symbol,
        "side": side,
        "reduceOnly": reduce_only,
        "type": OrderType.MARKET.value,
        "quantity": quantity,
        "algoType": AlgoType.STOP.value,
        "triggerPrice": str(trigger_price),
        "orderCombinationType": "STOP_MARKET",
    }

    if order_tag is not None:
        params['orderTag'] = order_tag

    return params


def update_algo_order(algo_order: WooAlgoOrder, params: AlgoOrderUpdateRequestParams) -> Optional[WooAlgoOrder]:
    order_data = edit_algo_order(algo_order.order_id, params)

    if order_data is None or order_data.get('status') != 'EDIT_SENT':
        return None

    algo_order.update(**params)

    return algo_order


def cancel_algo_order(algo_order: WooAlgoOrder) -> Optional[WooAlgoOrder]:
    res = cancel_algo_order_api(algo_order.order_id)
    if res is None or not res.get('success'):
        return
    algo_order.update(status='CANCELLED', quantity=0)
    return algo_order
