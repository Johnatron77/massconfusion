from __future__ import annotations

from typing import Optional

from django.contrib import admin
from datetime import datetime

from common.util.dates import get_date_time_from_timestamp
from .models import WooAlgoOrder, WooAPIError


def get_trigger_time(obj: Optional[WooAlgoOrder] = None) -> datetime | float:
    if obj is None or obj.trigger_time is None or obj.trigger_time == 0:
        return None
    return get_date_time_from_timestamp(obj.trigger_time)


@admin.register(WooAlgoOrder)
class WooAlgoOrderAdmin(admin.ModelAdmin):
    list_filter = ['side', 'status', 'reduce_only', 'created_at']
    readonly_fields = ['id']
    list_display = [
        'id',
        'order_id',
        'order_tag',
        'side',
        'quantity',
        'reduce_only',
        'trigger_price',
        'trigger_status',
        'get_trigger_time',
        'status',
        'created_at',
    ]

    class Media:
        js = [
            'js/toggle_filter_panel.js',
        ]

    @admin.display(description='Filled at')
    def get_trigger_time(self, obj):
        return get_trigger_time(obj)


@admin.register(WooAPIError)
class WooAPIErrorAdmin(admin.ModelAdmin):
    readonly_fields = ('type', 'url', 'params', 'error', 'created_at',)
