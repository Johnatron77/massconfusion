from __future__ import annotations

import _thread
import json
from enum import Enum
from typing import Callable, TypedDict, Optional

import websocket
import rel
import time

from common.util.logging import log
from woo.api_helpers import get_timestamp_unix, generate_signature

MARKET_DATA_WS = 'wss://wss.woo.org/ws/stream/'
PRIVATE_WS = 'wss://wss.woo.org/v2/ws/private/stream/'


class MessageTypes(str, Enum):
    SUBSCRIBE = 'subscribe'
    PING = 'ping'
    PONG = 'pong'
    KLINE_1M = 'PERP_BTC_USDT@kline_1m'
    AUTH = 'auth'
    EXECUTION_REPORT = 'executionreport'
    ALGO_EXECUTION_REPORT_V2 = 'algoexecutionreportv2'
    POSITION = 'position'
    ORDER_BOOK_UPDATE = '{symbol}@orderbookupdate'
    TRADE = '{symbol}@trade'
    BALANCE = 'balance'


class WSKlineData(TypedDict):
    startTime: int
    endTime: int
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float
    

class WooWSKwargs(TypedDict):
    connect_callback: Optional[Callable]
    error_callback: Optional[Callable]
    close_callback: Optional[Callable]


class WooWSClient:

    _app_id: str
    _app_key: str
    _app_secret: Optional[str]

    _ws: Optional[websocket.WebSocketApp]
    _connect_callback: Optional[Callable]
    _error_callback: Optional[Callable]
    _close_callback: Optional[Callable]
    _message_callback_map: dict[str, list[Callable]]

    def __init__(
        self,
        app_id: str,
        app_key: str,
        app_secret: Optional[str] = None,
        private: bool = False,
        debug: bool = False,
        **kwargs: WooWSKwargs
    ):
        if private and app_secret is None:
            raise Exception('Cannot create private WS without app_secret')

        self._app_id = app_id
        self._app_key = app_key
        self._app_secret = app_secret

        self._ws = None
        self._private = private
        self._debug = debug
        self._connect_callback = kwargs.get('connect_callback')
        self._error_callback = kwargs.get('error_callback')
        self._close_callback = kwargs.get('close_callback')
        self._message_callback_map = {}

    def connect(self):
        url = f'{PRIVATE_WS if self._private else MARKET_DATA_WS}{self._app_id}'
        try:
            self._ws = websocket.WebSocketApp(
                url,
                on_open=lambda ws: self._on_open(ws),
                on_message=lambda ws, msg: self._on_message(ws, msg),
                on_error=lambda ws, error: self._on_error(ws, error),
                on_close=lambda ws, close_status_code, close_msg: self._on_close(ws, close_status_code, close_msg)
            )

            self._ws.run_forever(dispatcher=rel, reconnect=5)
            rel.signal(2, rel.abort)
            rel.dispatch()
        except ConnectionResetError as e:
            log('ConnectionResetError', e)
            time.sleep(1)
            self.connect()
        
    def subscribe_to_1m_kline(self, handler: Optional[Callable] = None):
        self._subscribe(MessageTypes.KLINE_1M, handler)

    def subscribe_to_execution_report(self, handler: Optional[Callable] = None):
        self._subscribe(MessageTypes.EXECUTION_REPORT, handler)

    def subscribe_to_algo_execution_report_v2(self, handler: Optional[Callable] = None):
        self._subscribe(MessageTypes.ALGO_EXECUTION_REPORT_V2, handler)

    def subscribe_to_position(self, handler: Optional[Callable] = None):
        self._subscribe(MessageTypes.POSITION, handler)

    def subscribe_to_order_book_update(self, symbol: str, handler: Optional[Callable] = None):
        self._subscribe(MessageTypes.ORDER_BOOK_UPDATE, handler, [('symbol', symbol)])

    def subscribe_to_trade(self, symbol: str, handler: Optional[Callable] = None):
        self._subscribe(MessageTypes.TRADE, handler, [('symbol', symbol)])

    def subscribe_to_balance(self, handler: Optional[Callable] = None):
        self._subscribe(MessageTypes.BALANCE, handler)

    def _subscribe(
        self,
        msg_type: MessageTypes,
        handler: Optional[Callable] = None,
        params: list[tuple[str, str]] = None
    ):
        if self._ws is None:
            raise Exception('Cannot subscribe before connecting')

        topic = msg_type.value

        if params is not None:
            topic = topic.format(**dict(params))

        if handler is not None:
            self._register_message_callback(topic, handler)

        self._ws.send(json.dumps({
            "id": self._get_private_app_id(),
            "topic": topic,
            "event": "subscribe"
        }))

    def _register_message_callback(self, type: str, callback: Callable):
        cb_list = self._message_callback_map.get(type) or []
        if callback in cb_list:
            return
        cb_list.append(callback)
        self._message_callback_map[type] = cb_list

    def _deregister_message_callback(self, type: str, callback: Callable):
        cb_list = self._message_callback_map.get(type)
        if cb_list is None:
            return
        try:
            cb_list.remove(callback)
        except ValueError:
            pass

    def _on_open(self, ws: websocket.WebSocketApp):
        if self._debug:
            print("Opened connection")
        if self._private:
            self._authenticate_private(self._app_secret)
        elif self._connect_callback is not None:
            self._connect_callback()

    def _on_message(self, ws: websocket.WebSocketApp, message: str):
        msg = json.loads(message)
        type = msg.get('event') or msg.get('topic')

        try:
            m_type = MessageTypes(type)
        except ValueError:
            if self._debug:
                log('ERROR: no type for message', message)
            return

        if m_type == MessageTypes.AUTH:
            auth_success = msg.get('success')
            if auth_success and self._connect_callback is not None:
                self._connect_callback()

        if m_type == MessageTypes.PING:
            self._pong()

        cb_list = self._message_callback_map.get(m_type.value) or []

        if cb_list is not None:
            for cb in cb_list:
                cb(msg.get('data'))

        if self._debug:
            log(m_type.value, message)

    def _on_error(self, ws: websocket.WebSocketApp, error):
        if self._debug:
            log('error', error)
        if self._error_callback is not None:
            self._error_callback(error)

    def _on_close(self, ws, close_status_code, close_msg):
        if self._debug:
            log('closed', f'close_status_code: {close_status_code} - close_msg: {close_msg}')
        if self._close_callback is not None:
            self._close_callback(close_status_code, close_msg)

    def _pong(self):
        self._ws.send(json.dumps({
            "ts": str(get_timestamp_unix()),
            "event": MessageTypes.PONG.value
        }))

    def _authenticate_private(self, secret: str):
        timestamp_unix = get_timestamp_unix()

        self._ws.send(json.dumps({
            "id": self._get_private_app_id(),
            "event": MessageTypes.AUTH.value,
            "params": {
                "apikey": self._app_key,
                "sign": generate_signature(timestamp_unix, secret),
                "timestamp": str(timestamp_unix)
            }
        }))

    def _get_private_app_id(self):
        return self._app_id.replace('-', '')
