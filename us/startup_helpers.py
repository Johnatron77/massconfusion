from __future__ import annotations

import time

from celery import chain, group

from woo.api_ws import WooWSClient, MessageTypes

from us.models import get_default_symbol, TimeframeGroup
from us.helpers import fetch_missing_klines, bulk_create_klines, get_symbol, create_ws_kline
from us.tasks import process_group_timeframes, process_timeframe_group, process_timeframe_group_stats, \
    process_timeframe_kline_signal


def start_up(symbol_type: str | None = None):
    if symbol_type is None:
        symbol_type = get_default_symbol().type
    kline_ids = _get_missing_klines_for(symbol_type)
    _process_klines(symbol_type, kline_ids, first_run=True)
    _connect_ws()


def _get_missing_klines_for(symbol_type: str) -> list[int]:
    klines_data = fetch_missing_klines(symbol_type)
    klines = bulk_create_klines(klines_data)

    if isinstance(klines, list) and len(klines) > 0:
        return [kline.id for kline in klines]

    return []


def _process_klines(symbol_type: str, kline_ids: list[int], first_run: bool = False):
    if len(kline_ids) == 0:
        return

    symbol = get_symbol(symbol_type)
    tf_groups = TimeframeGroup.objects.filter(symbol=symbol, enabled=True)

    tasks = group(
        chain(
            process_group_timeframes.s(kline_ids, tf_group.id),
            process_timeframe_group.s(tf_group.id),
            process_timeframe_group_stats.s(),
            process_timeframe_kline_signal.s(tf_group.id)
        ) for tf_group in tf_groups
    ).apply_async(ignore_result=not first_run)

    if first_run:
        while True:
            if tasks.successful():
                break
            time.sleep(.1)


def _connect_ws():
    ws = WooWSClient()
    ws.register_message_callback(MessageTypes.KLINE_1M, _process_ws_kline)
    ws.connect()


def _process_ws_kline(message: dict):
    kline = create_ws_kline(message)
    if kline is None:
        return
    kline = kline.previous
    _process_klines(kline.symbol.type, [kline.id])
