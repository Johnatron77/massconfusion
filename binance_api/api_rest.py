from __future__ import annotations

import time

import requests

from woo.api_rest import KlineData, HistoricalKlineResponseMetaData

BASE_URL = 'https://fapi.binance.com'
HISTORICAL_KLINES = '/fapi/v1/continuousKlines'


def request_historical_klines(
    symbol_type: str,
    start_time: int,
    type: str | None = '1m'
) -> tuple[None, None] | tuple[list[KlineData], HistoricalKlineResponseMetaData]:
    response = requests.get(
        f'{BASE_URL}{HISTORICAL_KLINES}',
        params={
            "pair": "BTCUSDT",
            "contractType": "PERPETUAL",
            "interval": type,
            'startTime': start_time * 1000,
        }
    )

    data = response.json()

    if data is None:
        print(f'ERROR: with response: {data}')
        return None, None

    total = int((int(time.time()) - (data[0][0]/1000) if len(data) > 0 else 0) / 60)

    return [_convert_to_kline_data(row) for row in data], {'total': total, 'records_per_page': 500, 'current_page': 1}


def _convert_to_kline_data(data: list) -> KlineData:
    return {
        'start_timestamp': int(data[0]),
        'open': float(data[1]),
        'high': float(data[2]),
        'low': float(data[3]),
        'close': float(data[4]),
        'volume': float(data[5]),
        'end_timestamp': int(data[6]),
        'amount': float(data[7]),
        'symbol': 'PERP_BTC_USDT'
    }