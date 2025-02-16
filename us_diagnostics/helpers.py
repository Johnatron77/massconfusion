from __future__ import annotations

import json
import csv
from typing import Type, Optional, TypedDict, Callable

from typing_extensions import NotRequired

from us.helpers import get_symbol, get_timeframe_of, get_klines_for_timeframe, calculate_timeframe_kline_values
from us.models import Kline, WsKline, Timeframe, convert_epoch_timestamp_to_readable_datetime, TimeframeKline, \
    get_default_symbol, TimeframeKlineStats, BaseKline, KlineTypes
from us.utilities import clear_timeframe_klines_from_for, create_timeframe_klines_for, create_timeframe_kline_stats_for
from us_diagnostics.models import KlineDiagnosticsResult
from woo.api_rest import request_historical_klines as woo_request_historical_klines, KlineData, HistoricalKlineResponseMetaData
from binance_api.api_rest import request_historical_klines as binance_request_historical_klines


class TradingViewKlineData(KlineData):
    open_time: str
    rsi: float


class KlineComparisonStatValue(TypedDict):
    saved: float
    actual: float


class KlineComparisonStats(TypedDict):
    id: int
    start_timestamp: int
    open: NotRequired[KlineComparisonStatValue]
    close: NotRequired[KlineComparisonStatValue]
    high: NotRequired[KlineComparisonStatValue]
    low: NotRequired[KlineComparisonStatValue]
    volume: NotRequired[KlineComparisonStatValue]
    amount: NotRequired[KlineComparisonStatValue]
    rsi: NotRequired[KlineComparisonStatValue]


def compare_saved_klines_with_historical_data(
    symbol_type: str,
    start_time: int,
    kline_cls: Type[Kline | WsKline],
    exchange: Optional[str] = 'woo'
) -> tuple[None, None] | tuple[list[KlineComparisonStats], HistoricalKlineResponseMetaData]:

    request_func: Callable = woo_request_historical_klines if exchange == 'woo' else binance_request_historical_klines
    rows, meta = request_func(symbol_type, start_time)
    if rows is None:
        print(f'ERROR: raw_klines_data is None')
        return None, None
    symbol = get_symbol(symbol_type)
    incorrect_klines: list[KlineComparisonStats] = []

    for row in rows:
        try:
            kline = kline_cls.objects.get(symbol=symbol, start_timestamp=row.get('start_timestamp') / 1000)
            comp_stats = compare_klines(kline, row)

            if len(comp_stats) == 2 or (len(comp_stats) == 3 and comp_stats.get('amount') is not None):
                continue

            incorrect_klines.append(comp_stats)

        except kline_cls.DoesNotExist:
            pass

    return incorrect_klines, meta


def compare_klines(kline: BaseKline, kline_data: KlineData) -> KlineComparisonStats:
    open = float(kline.open)
    close = float(kline.close)
    high = float(kline.high)
    low = float(kline.low)
    volume = float(kline.volume)
    amount = float(kline.amount)
    comp_stats: KlineComparisonStats = {
        'id': kline.id,
        'start_timestamp': int(kline.start_timestamp)
    }
    if open != kline_data.get('open') or close != kline_data.get('close') or high != kline_data.get('high') or low != \
            kline_data.get(
        'low') or volume != kline_data.get('volume') or amount != kline_data.get('amount'):

        if open != kline_data.get('open'):
            comp_stats['open'] = {'saved': open, 'actual': kline_data.get('open')}
        if close != kline_data.get('close'):
            comp_stats['close'] = {'saved': close, 'actual': kline_data.get('close')}
        if high != kline_data.get('high'):
            comp_stats['high'] = {'saved': high, 'actual': kline_data.get('high')}
        if low != kline_data.get('low'):
            comp_stats['low'] = {'saved': low, 'actual': kline_data.get('low')}
        if volume != kline_data.get('volume'):
            comp_stats['volume'] = {'saved': volume, 'actual': kline_data.get('volume')}
        if amount != kline_data.get('amount'):
            comp_stats['amount'] = {'saved': amount, 'actual': kline_data.get('amount')}

    return comp_stats


def create_or_update_diagnostics_file(file_path: str, incorrect_klines: list[dict]) -> list[KlineComparisonStats]:
    contents: list[KlineComparisonStats] = []
    with open(file_path, mode='a+', encoding='utf-8') as file:
        try:
            file.seek(0)
            contents = json.load(file)
            file.truncate(0)
        except json.decoder.JSONDecodeError as e:
            print(e)
            pass

        for kline in incorrect_klines:
            contents.append(kline)
        contents.sort(key=lambda k: k.get('start_timestamp'), reverse=True)
        json.dump(contents, file, ensure_ascii=False, indent=2)

    return contents


def process_diagnostics(pk: Optional[int] = None, only_update_klines: bool = True):

    if pk is None:
        kdr = KlineDiagnosticsResult.objects.latest('created_at')
    else:
        try:
            kdr = KlineDiagnosticsResult.objects.get(id=pk)
        except KlineDiagnosticsResult.DoesNotExist:
            print(f'ERROR: KlineDiagnosticsResult with id {pk} does not exist')
            return

    if kdr is None:
        print(f'ERROR: KlineDiagnosticsResult with id {pk} does not exist')
        return

    report: list[KlineComparisonStats] = json.loads(kdr.report)
    _process_diagnostics_report(report, only_update_klines)


def process_diagnostics_file(file_path: str, only_update_klines: bool = True):
    with open(file_path) as file:
        file.seek(0)
        contents = json.load(file)
        _process_diagnostics_report(contents, only_update_klines)


def _process_diagnostics_report(report: list[KlineComparisonStats], only_update_klines: bool = True):
    start_time = None
    for kline_data in report:
        kline = Kline.objects.get(id=kline_data['id'], start_timestamp=kline_data['start_timestamp'])
        start_time = int(min(kline.start_timestamp, start_time)) if start_time is not None else kline.start_timestamp
        has_changes = False
        for key in kline_data:
            if key in ['id', 'start_timestamp']:
                continue
            has_changes = True
            setattr(kline, key, kline_data[key]["actual"])
        if has_changes:
            kline.save()

    if only_update_klines:
        return

    if start_time is not None:
        for tf in Timeframe.objects.all():
            if tf.minutes == 1:
                continue
            clear_timeframe_klines_from_for(tf.minutes, start_time)
            create_timeframe_klines_for(tf.minutes, start_time)
            create_timeframe_kline_stats_for(tf.minutes, start_time)


def compare_rsi_with_trading_view(csv_file_path: str, timeframe_mins: int = 1):

    timeframe = get_timeframe_of(timeframe_mins)
    symbol = get_default_symbol()

    if timeframe is None:
        print(f'ERROR: timeframe for {timeframe_mins} minutes does not exist')
        return None, None

    with open(csv_file_path, 'r') as file:
        reader = csv.reader(file)
        header = next(reader)
        data: list[TradingViewKlineData] = [{
            'open_time': convert_epoch_timestamp_to_readable_datetime(int(row[0])),
            'start_timestamp': int(row[0]),
            'end_timestamp': int(row[0]) + timeframe.seconds,
            'open': float(row[1]),
            'high': float(row[2]),
            'low': float(row[3]),
            'close': float(row[4]),
            'volume': float(row[5]),
            'amount': 0.0,
            'symbol': symbol.type,
            'rsi': float(row[7]),
        } for row in list(reader)]

    incorrect_klines = []

    for kline_data in data:
        try:
            tf_kline = TimeframeKline.objects.get(
                start_timestamp=kline_data['start_timestamp'],
                timeframe=timeframe,
                symbol=symbol
            )
        except TimeframeKline.DoesNotExist:
            continue
        comp_stats = compare_klines(tf_kline, kline_data)
        stats = TimeframeKlineStats.objects.get(timeframe_kline=tf_kline)
        stats_rsi = round(float(stats.rsi), 10)
        kline_data_rsi = round(float(kline_data['rsi']), 10)

        if stats_rsi != kline_data_rsi:
            print(stats_rsi)
            print(kline_data_rsi)
            comp_stats['rsi'] = {'saved': float(stats.rsi), 'actual': float(kline_data['rsi'])}

        if len(comp_stats) == 2 or (len(comp_stats) == 3 and comp_stats.get('amount') is not None):
            continue

        incorrect_klines.append(comp_stats)

    if len(incorrect_klines) > 0:
        file_path = csv_file_path.replace('.csv', '_rsi_diagnostics.json')
        create_or_update_diagnostics_file(file_path, incorrect_klines)
        print(f'incorrect_klines: {len(incorrect_klines)}')


def check_timeframe_kline_values_against_1m_kline_values(timeframe_mins: int, start_timestamp: int, symbol_type: Optional[str] = None):
    timeframe = get_timeframe_of(timeframe_mins)
    symbol = get_symbol(symbol_type) if symbol_type else get_default_symbol()
    start_timestamp = start_timestamp - (start_timestamp % timeframe.seconds)
    for tfk in TimeframeKline.objects.filter(timeframe=timeframe, symbol=symbol, start_timestamp__gte=start_timestamp):
        klines = get_klines_for_timeframe(timeframe, symbol, tfk.end_timestamp)
        values = calculate_timeframe_kline_values(klines)
        has_changes = False
        for key in values:
            if getattr(tfk, key) == values[key]:
                continue
            has_changes = True
            setattr(tfk, key, values[key]["actual"])
        if has_changes:
            print(f'updating {tfk}')
            tfk.save()


def find_dupes(file_path: str):
    with open(file_path) as file:
        file.seek(0)
        contents = json.load(file)

    data = contents.get('rows')
    dupes = []
    for i, kline in enumerate(data):
        for j, kline2 in enumerate(data):
            if i == j:
                continue
            if kline['start_timestamp'] == kline2['start_timestamp']:
                dupes.append(kline)

    return dupes


def compare_trading_view_exchange_rsi(interval: int):
    dir = 'diagnostics/rsi/'
    csv_path = f'{dir}%EXCHANGE%_BTCUSDT.P, {interval}.csv'
    with open(csv_path.replace('%EXCHANGE%', 'WOONETWORK'), 'r') as file:
        reader = csv.reader(file)
        header = next(reader)
        woo_data = [[int(row[0]), float(row[1]), float(row[4]), float(row[7])] for row in list(reader)]

    with open(csv_path.replace('%EXCHANGE%', 'BINANCE'), 'r') as file:
        reader = csv.reader(file)
        header = next(reader)
        binance_data = [[int(row[0]), float(row[1]), float(row[4]), float(row[7])] for row in list(reader)]

    output = [['date', 'woo open', 'bin open', 'open diff', 'woo close', 'bin close', 'close diff', 'woo rsi', 'bin rsi', 'rsi diff', 'woo signal', 'bin signal']]

    for kline in woo_data:
        index = woo_data.index(kline)
        binance_kline = binance_data[index]
        output.append([
            convert_epoch_timestamp_to_readable_datetime(kline[0]),
            kline[1],
            binance_kline[1],
            round(kline[1] - binance_kline[1], 3),
            kline[2],
            binance_kline[2],
            round(kline[2] - binance_kline[2], 3),
            kline[3],
            binance_kline[3],
            round(kline[3] - binance_kline[3], 3),
            signal_type(woo_data, index),
            signal_type(binance_data, index)
        ])

    with open(f'{dir}exchange_comparison_results_for_{interval}m.csv', 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerows(output)


def signal_type(data: list, index: int) -> str:
    if index == 0:
        return 'N/A'
    curr = data[index]
    curr_type = KlineTypes.BEARISH if curr[1] > curr[2] else KlineTypes.BULLISH
    prev = data[index - 1]
    prev_type = KlineTypes.BEARISH if prev[1] > prev[2] else KlineTypes.BULLISH

    if curr_type == prev_type:
        return 'N'

    if data[index][3] > 68 and curr[2] >= prev[1]:
        return 'SELL'

    if data[index][3] < 30 and curr[2] <= prev[1]:
        return 'BUY'

    return 'N'


