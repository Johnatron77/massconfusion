from __future__ import annotations

from typing import TypedDict, Optional

import requests

from woo.api_helpers import get_headers, RequestTypes
from woo.api_types import AlgoOrderRequestParams, AlgoOrderUpdateRequestParams
from woo.models import WooAPIError

import environ

env = environ.Env()
environ.Env.read_env()

WOO_KEY = env('WOO_TRADE_KEY')
WOO_SECRET = env('WOO_TRADE_SECRET')
WOO_APP_ID = env('WOO_TRADE_APP_ID')


BASE_URL = 'https://api.woo.org'
GET_KLINES = '/v1/public/kline'
HISTORICAL_KLINES_BASE_URL = 'https://api-pub.woo.org'
GET_HISTORICAL_KLINES = '/v1/hist/kline'
ALGO = '/v3/algo'
ALGO_ORDERS = f'{ALGO}/orders'
ALGO_ORDER = f'{ALGO}/order'
PENDING_ALGO_ORDERS = f'{ALGO_ORDERS}/pending'
ORDER = '/v1/order/'
ORDERS = '/v1/orders'
ORDER_TRADES = f'{ORDER}/trades'
CLIENT = '/v1/client'
CLIENT_ORDER = f'{CLIENT}/order/'
CLIENT_TRADE = f'{CLIENT}/trade'
CLIENT_TRADES = f'{CLIENT}/trades'
GET_TRANSACTION_HISTORY = f'{CLIENT}/transaction_history'
GET_POSITION_INFO = '/v3/positions'
GET_ACCOUNT_INFO = '/v3/accountinfo'
GET_CREDENTIALS = '/usercenter/api/enabled_credential'
GET_IP_RESTRICTION = '/v1/sub_account/ip_restriction'


class WooAPIResponse(TypedDict):
    success: bool


class KlineData(TypedDict):
    open: float
    close: float
    high: float
    low: float
    volume: float
    amount: float
    start_timestamp: int
    end_timestamp: int
    symbol: str


class KlineResponse(WooAPIResponse):
    rows: list[KlineData]


class HistoricalKlineResponseMetaData(TypedDict):
    total: int
    records_per_page: int
    current_page: int


class HistoricalKlineResponseData(TypedDict):
    rows: list[KlineData]
    meta: HistoricalKlineResponseMetaData


class HistoricalKlineResponse(WooAPIResponse):
    data: HistoricalKlineResponseData


def _api_request(
    path: str,
    request_type: RequestTypes = RequestTypes.GET,
    data: Optional[dict] = None,
    base_url: str = BASE_URL,
    is_signed: bool = False,
    response_data_key: str = 'data',
    connect_timeout: float = 5.0,
    read_timeout: float = 30.0
):
    error = None
    headers = None
    response_data = None
    url = base_url + path

    if is_signed:
        headers = get_headers(path, request_type, WOO_KEY, WOO_SECRET, data)

    try:
        response = requests.request(
            request_type.value.lower(),
            url,
            headers=headers,
            params=data if request_type == RequestTypes.GET else None,
            json=data if request_type != RequestTypes.GET else None,
            timeout=(connect_timeout, read_timeout)
        )

        response_data = response.json()

        if not response_data.get('success'):
            error = {'type': 'API', 'error': response_data}
            response_data = None
        else:
            r_data = response_data.get(response_data_key)
            response_data = r_data if r_data is not None else response_data

    except requests.exceptions.ConnectionError as e:
        error = {'type': 'Connection', 'error': e}
    except requests.exceptions.Timeout as e:
        error = {'type': 'Timeout', 'error': e}
    except requests.exceptions.RequestException as e:
        error = {'type': 'Request', 'error': e}
    except Exception as e:
        error = {'type': 'Unknown', 'error': e}

    if error is not None:
        WooAPIError.objects.create(type=error['type'], url=url, params=data, error=error['error'])

    return response_data


type_default = '1m'
limit_default = 1


def request_klines(symbol: str, type: Optional[str] = type_default, limit: Optional[int] = limit_default) -> Optional[list[KlineData]]:
    limit = [limit, limit_default][limit is None]
    data: Optional[list[KlineData]] = _api_request(
        GET_KLINES,
        RequestTypes.GET,
        data={
            'symbol': symbol,
            'type': [type, type_default][type is None],
            'limit': limit
        },
        response_data_key='rows'
    )

    if data is None:
        print(f'ERROR: with response: {data}')
        return []

    return data


def request_historical_klines(symbol_type: str, start_time: int, type: str | None = type_default) -> tuple[None, None] | \
                                                                                                     tuple[list[
                                                                                                         KlineData], HistoricalKlineResponseMetaData]:
    data: Optional[HistoricalKlineResponseData] = _api_request(
        GET_HISTORICAL_KLINES,
        RequestTypes.GET,
        base_url=HISTORICAL_KLINES_BASE_URL,
        data={
            'symbol': symbol_type,
            'type': [type, type_default][type is None],
            'start_time':start_time * 1000
        }
    )

    if data is None:
        print(f'ERROR: with response: {data}')
        return None, None

    return data.get('rows'), data.get('meta')


def get_algo_order(order_id: int):
    return _api_request(f'{ALGO_ORDER}/{order_id}', data={"realizedPnl": True}, is_signed=True)


def get_algo_orders():
    return _api_request(ALGO_ORDERS, data={"algoType": "STOP", "realizedPnl": True}, is_signed=True)


def send_algo_order(params: AlgoOrderRequestParams):
    return _api_request(ALGO_ORDER, RequestTypes.POST, data=params, is_signed=True)


def edit_algo_order(order_id: int, params: AlgoOrderUpdateRequestParams):
    return _api_request(f'{ALGO_ORDER}/{order_id}', RequestTypes.PUT, data=params, is_signed=True)


def cancel_algo_order(order_id: int):
    return _api_request(f'{ALGO_ORDER}/{order_id}', RequestTypes.DELETE, is_signed=True)


def cancel_all_pending_algo_orders():
    return _api_request(PENDING_ALGO_ORDERS, RequestTypes.DELETE, is_signed=True)


def get_order(order_id: int):
    return _api_request(f'{ORDER}{order_id}', response_data_key='data', is_signed=True)


def get_orders():
    return _api_request(ORDERS, data={"symbol": "PERP_BTC_USDT"}, response_data_key='rows', is_signed=True)


def get_client_order(client_order_id: int):
    return _api_request(f'{CLIENT_ORDER}{client_order_id}', response_data_key='data', is_signed=True)


def get_client_trade(trade_id: int):
    return _api_request(f'{CLIENT_TRADE}/{trade_id}', response_data_key='data', is_signed=True)


def get_client_trades():
    return _api_request(CLIENT_TRADES, data={"symbol": "PERP_BTC_USDT"}, response_data_key='rows', is_signed=True)


def get_account_info():
    return _api_request(GET_ACCOUNT_INFO, is_signed=True)


def get_transaction_history():
    return _api_request(GET_TRANSACTION_HISTORY, data={"size": 100}, is_signed=True)


def get_credentials():
    return _api_request(GET_CREDENTIALS, is_signed=True)


def get_position_info():
    return _api_request(GET_POSITION_INFO, is_signed=True)


def get_ip_restriction():
    return _api_request(GET_IP_RESTRICTION, response_data_key='rows', is_signed=True)
