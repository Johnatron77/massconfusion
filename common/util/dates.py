from __future__ import annotations

from datetime import datetime


def get_date_time_from_timestamp(timestamp: float) -> datetime | float:
    try:
        return datetime.fromtimestamp(float(timestamp))
    except ValueError:
        pass
    return timestamp
