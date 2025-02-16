from typing import TypedDict
from dateutil import parser
from django.core.exceptions import ValidationError

from us.helpers import get_symbol, get_timeframe_of, get_signal_variables_for
from us.models import TimeframeKline, TimeframeKlineSignalType, get_default_timeframe_group_signal_variables


class TradingViewSignalRSIData(TypedDict):
    period: int
    upper: int
    lower: int


class TradingViewSignalKlineData(TypedDict):
    interval: str
    start_time: str
    open: str
    low: str
    high: str
    close: str
    volume: str


class TradingViewSignalData(TypedDict):
    pf: str
    side: str
    time: str
    symbol: str
    exchange: str
    kline: TradingViewSignalKlineData
    rsi: TradingViewSignalRSIData


def transform_signal_data(data: TradingViewSignalData):
    kline = data.get('kline')
    rsi = data.get('rsi')
    symbol_type = data.get('symbol')
    interval = kline.get('interval')

    symbol = get_symbol(symbol_type) if symbol_type else None
    timeframe = get_timeframe_of(int(interval)) if interval else None
    sig_vars = get_signal_variables_for(rsi['period'], rsi['upper'], rsi['lower']) if rsi else get_default_timeframe_group_signal_variables()
    tfk = None

    if kline and symbol and timeframe:
        start_time = int(parser.parse(kline.get('start_time')).timestamp())

        try:
            tfk, _ = TimeframeKline.objects.get_or_create(
                symbol=symbol,
                timeframe=timeframe,
                start_timestamp=start_time,
                end_timestamp=start_time + timeframe.seconds,
                open=kline['open'],
                low=kline['low'],
                high=kline['high'],
                close=kline['close'],
                volume=kline['volume'],
                amount=0,
            )
        except ValidationError as e:
            print(f'Validation error: {e}')

    try:
        type = TimeframeKlineSignalType((data.get('side') or '').upper())
    except ValueError:
        type = None

    return {
        'type': type.value if type else None,
        'timeframe_kline': tfk.id if tfk else None,
        'signal_variables': sig_vars.id if sig_vars else None,
    }
