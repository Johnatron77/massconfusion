from __future__ import annotations

import datetime
import hashlib
import hmac
import json
from enum import Enum
from typing import Optional


MINIMUM_ORDER_QUANTITY = 0.0001


class RequestTypes(str, Enum):
    GET = 'GET'
    POST = 'POST'
    PUT = 'PUT'
    DELETE = 'DELETE'


def get_timestamp_unix() -> str:
    return str(round(datetime.datetime.now().timestamp() * 1000))


def get_headers(
    path: str,
    request_type: RequestTypes,
    api_key: str,
    secret: str,
    data: Optional[dict] = None,
) -> dict:

    time_stamp = get_timestamp_unix()
    request_method_and_path = None

    if path.startswith('/v3') and request_type != RequestTypes.GET:
        request_method_and_path = f'{request_type.value}{path}'

    signature = generate_signature(time_stamp, secret, data, request_method_and_path)

    return {
        'x-api-timestamp': time_stamp,
        'x-api-key': api_key,
        'x-api-signature': signature,
        'Content-Type': 'application/x-www-form-urlencoded' if request_method_and_path is None else 'application/json',
        'Cache-Control':'no-cache'
    }


def generate_signature(time_stamp: str, secret: str, data: Optional[dict] = None, request_method_and_path: Optional[str] = None) -> hmac.HMAC.hexdigest:
    data = data or {}

    if request_method_and_path:
        data_str = f'{time_stamp}{request_method_and_path}'
        if len(data) > 0:
            data_str += json.dumps(data)
    else:
        data_str = _create_ordered_query_string(data)
        data_str += f'|{time_stamp}'

    return _generate_signature(secret, data_str)


def _generate_signature(secret: str, data: str) -> hmac.HMAC.hexdigest:
    key_bytes= bytes(secret , 'utf-8')
    data_bytes = bytes(data, 'utf-8')
    return hmac.new(key_bytes, data_bytes , hashlib.sha256).hexdigest()


def _create_ordered_query_string(params: dict) -> str:
    return '&'.join([f'{key}={params[key]}' for key in dict(sorted(params.items()))])
