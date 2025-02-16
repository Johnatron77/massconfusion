import time
import json
from enum import Enum
from typing import Optional

from celery import shared_task, signals

from common.util.periodic_tasks import get_task_by_name
from us.helpers import get_symbol, historical_start_time
from us.models import Kline, TestKline, WsKline
from us_diagnostics.helpers import create_or_update_diagnostics_file, KlineComparisonStats, \
    compare_saved_klines_with_historical_data
from us_diagnostics.models import KlineDiagnosticsResult
from woo.api_rest import HistoricalKlineResponseMetaData


class Tasks(Enum):
    GET_KLINE_DIAGNOSTICS_FOR = 'us.tasks.get_kline_diagnostics_for'


@shared_task(ignore_result=True)
def kline_diagnostics(
    symbol_type: str,
    start_time: int = historical_start_time,
    current_time: Optional[int] = None,
    kline_type: Optional[str] = None,
    exchange: str = 'woo',
    **kwargs
):
    current_time = [current_time, start_time][current_time is None]
    kline_cls = get_kline_cls(kline_type)
    return compare_saved_klines_with_historical_data(symbol_type, current_time, kline_cls, exchange)


@signals.task_success.connect(sender=kline_diagnostics)
def kline_diagnostic_success(**kwargs):

    incorrect_klines: list[KlineComparisonStats]
    meta: HistoricalKlineResponseMetaData

    incorrect_klines, meta = kwargs['result']
    print('==========================================')
    print(incorrect_klines)
    sender = kwargs['sender']
    name = sender.request.properties.get('periodic_task_name')
    task = get_task_by_name(name)
    kwargs_dict = json.loads(task.kwargs)
    symbol_type = kwargs_dict.get('symbol_type')
    kline_type = kwargs_dict.get('kline_type')
    start_time = kwargs_dict.get('start_time') or historical_start_time
    current_time = kwargs_dict.get('current_time') or start_time
    end_time = kwargs_dict.get('end_time')
    incorrect_total = kwargs_dict.get('incorrect_total') or 0
    exchange = kwargs_dict.get('exchange') or 'woo'

    print('==========================================')
    print(f'meta: {meta}')
    print(f'current_time: {current_time}')
    print(f'incorrect_total: {incorrect_total}')
    print('==========================================')

    if incorrect_klines is None or meta is None:
        task.enabled = True
        task.save()
        return

    enabled = True

    if len(incorrect_klines) > 0:
        print(f'incorrect_klines: {len(incorrect_klines)}')
        file_path = f'diagnostics/{"" if kline_type is None else kline_type}kline_diagnostics-{time.strftime("%Y-%m-%d")}-{start_time}.json'
        incorrect_klines = create_or_update_diagnostics_file(file_path, incorrect_klines)
        incorrect_total = len(incorrect_klines)

    current_time += int(meta['records_per_page']) * 60
    kline_cls = get_kline_cls(kline_type)
    symbol = get_symbol(symbol_type)
    last_kline = kline_cls.objects.filter(symbol=symbol).order_by('-end_timestamp').first()
    finished = False

    if int(meta['records_per_page']) >= int(meta['total']):
        finished = True
    elif last_kline is not None and current_time > last_kline.end_timestamp:
        finished = True
    elif end_time is not None and current_time > end_time:
        finished = True

    if finished:
        kdr = KlineDiagnosticsResult.objects.create(
            symbol=symbol,
            kline_type=kline_type,
            start_time=start_time,
            end_time=last_kline.end_timestamp,
            report=json.dumps(incorrect_klines),
        )
        if exchange == 'woo':
            kdr.incorrect_klines.add(*[kline.get('id') for kline in incorrect_klines])

        print('==========================================')
        print('completed diagnostics')
        print(f'meta - {meta}')
        print(f'current_time - {current_time}')
        print(f'incorrect klines - {incorrect_total}')
        print('==========================================')
        if kwargs_dict.get('current_time') is not None:
            del kwargs_dict['current_time']
        if kwargs_dict.get('incorrect_total') is not None:
            del kwargs_dict['incorrect_total']
        if incorrect_total == 0:
            kwargs_dict['start_time'] = last_kline.end_timestamp
        enabled = False
    else:
        kwargs_dict['current_time'] = current_time
        kwargs_dict['incorrect_total'] = incorrect_total

    task.kwargs = json.dumps(kwargs_dict)
    task.enabled = enabled
    task.save()


def get_kline_cls(kline_type: str = None):
    if kline_type == 'test':
        return TestKline
    elif kline_type == 'ws':
        return WsKline
    return Kline