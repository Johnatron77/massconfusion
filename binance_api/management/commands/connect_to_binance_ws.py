from typing import TypedDict

from django.core.management.base import BaseCommand, CommandError

from binance_api.api_ws import MessageTypes
from us.helpers import get_symbol
from us.models import WsKline


class BinanceKlineData(TypedDict):
    t: int # Kline start time in milliseconds
    T: int # Kline close time in milliseconds
    i: str # Interval
    f: int # First trade ID
    L: int # Last trade ID
    o: str # Open price
    c: str # Close price
    h: str # High price
    l: str # Low price
    v: str # Base asset volume
    n: int # Number of trades
    x: bool # Is this kline closed?
    q: str # Quote asset volume
    V: str # Taker buy base asset volume
    Q: str # Taker buy quote asset volume
    B: str # Ignore


class BinanceKlineResponse(TypedDict):
    e: str # Event type
    E: int # Event time
    ps: str # Pair i.e. "BTCUSDT"
    ct: str # Contract type i.e. "PERPETUAL"
    k: BinanceKlineData


class Command(BaseCommand):
    help = 'Sync 1m kline data and connect to binance ws API'
    kline_closed = False

    def handle(self, *args, **options):
        from binance_api.api_ws import BinanceWS
        ws = BinanceWS(debug=False)
        ws.register_message_callback(MessageTypes.CONTINUOUS_KLINE, self._process_msg)
        ws.connect()

    def _process_msg(self, message: BinanceKlineResponse):
        data = message['k']
        start_timestamp = int(data['t'] / 1000)
        end_timestamp = int((data['T'] + 1 )/ 1000)
        symbol = get_symbol('PERP_BTC_USDT')

        kline, created = WsKline.objects.update_or_create(
            symbol=symbol,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            defaults={
                'open': data['o'],
                'close': data['c'],
                'low': data['l'],
                'high': data['h'],
                'volume': data['v'],
                'amount': data['q'],
            }
        )

        if created and not self.kline_closed:
            print('kline created before previous closed')

        self.kline_closed = data['x']