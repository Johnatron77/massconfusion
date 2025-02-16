import json
from enum import Enum
from typing import Callable

import websocket
import rel

MARKET_DATA_WS = 'wss://fstream.binance.com/ws/btcusdt_perpetual@continuousKline_1m'


class MessageTypes(Enum):
    SUBSCRIBE = 'subscribe'
    PING = 'ping'
    PONG = 'pong'
    KLINE = 'kline'
    CONTINUOUS_KLINE = 'continuous_kline'


class BinanceWS():
    def __init__(self, debug: bool = False, enable_trace: bool = False):
        self.ws = None
        self.debug = debug
        self.enable_trace = enable_trace
        self.message_callback_map = {}

    def connect(self, on_error: Callable = None, on_close: Callable = None):
        websocket.enableTrace(self.enable_trace)
        url = MARKET_DATA_WS
        self.ws = websocket.WebSocketApp(url,
             on_open=self._on_open,
             on_message=self._on_message,
             on_error=self._on_error if on_error is None else on_error,
             on_close=self._on_close if on_close is None else on_close)

        self.ws.run_forever(dispatcher=rel, reconnect=5)
        rel.signal(2, rel.abort)
        rel.dispatch()

    def register_message_callback(self, type: MessageTypes, callback: Callable):
        cb_list = self.message_callback_map.get(type) or []
        cb_list.append(callback)
        self.message_callback_map[type] = cb_list

    def deregister_message_callback(self, type: MessageTypes, callback: Callable):
        cb_list = self.message_callback_map.get(type)
        if cb_list is None:
            return
        try:
            cb_list.remove(callback)
        except ValueError:
            pass

    def _on_open(self, ws: websocket.WebSocketApp):
        if self.debug:
            print("Opened connection")

    def _on_message(self, ws: websocket.WebSocketApp, message: str):
        msg: dict = json.loads(message)
        msg_type: str = msg.get('e')

        if self.debug:
            print(f'message type: {msg_type}')

        try:
            m_type = MessageTypes(msg_type)
        except ValueError:
            if self.debug:
                print(f'ERROR: no type for message: {message}')
            return

        cb_list = self.message_callback_map.get(m_type)

        if cb_list is None:
            return

        for cb in cb_list:
            cb(msg)

    def _on_error(self, ws: websocket.WebSocketApp, error):
        if self.debug:
            print(error)

    def _on_close(self, ws, close_status_code, close_msg):
        if self.debug:
            print("### closed ###")
            print(f'close_status_code: {close_status_code}')
            print(f'close_msg: {close_msg}')
