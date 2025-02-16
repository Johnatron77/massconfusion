from __future__ import annotations

from django.contrib import admin
from django.urls import resolve

from common.util.admin import linkify
from us_orders.models.order import Order
from us_orders.models.order_group import OrderGroup
from woo.admin import get_trigger_time
from woo.models import WooAlgoOrder


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_filter = ['created_at']
    readonly_fields = ['id']
    list_display = [
        'id', 'status', 'side', 'quantity', 'trigger_price', 'get_trigger_time',
        linkify('order', 'pk'), 'get_stop_status', 'is_stopped_out',
        'get_stop_trigger_time', linkify('stop', 'pk'), 'created_at'
    ]

    @admin.display(description='Filled at')
    def get_trigger_time(self, obj):
        return get_trigger_time(obj.order)

    @admin.display(description='Stop status')
    def get_stop_status(self, obj):
        if obj.stop is None:
            return None
        return obj.stop.status

    @admin.display(description='Stopped at')
    def get_stop_trigger_time(self, obj):
        return get_trigger_time(obj.stop)

    class Media:
        js = [
            'js/toggle_filter_panel.js',
        ]


@admin.register(OrderGroup)
class OrderGroupAdmin(admin.ModelAdmin):
    readonly_fields = ['id']
    list_display = ['id', 'side', 'quantity', 'is_active', 'is_pending', 'is_closed', 'has_stop', 'created_at']

    def get_order_group(self, request):
        resolved = resolve(request.path_info)
        if resolved.kwargs.get('object_id'):
            return OrderGroup.objects.get(id=resolved.kwargs.get('object_id'))
        return None

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'stop':
            order_group = self.get_order_group(request)
            if order_group:
                kwargs['queryset'] = WooAlgoOrder.objects.get_all_reduce_only_orders_for_side(
                    ['SELL', 'BUY'][order_group.side == 'SELL']
                )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == 'orders':
            order_group = self.get_order_group(request)
            if order_group:
                kwargs['queryset'] = Order.objects.get_all_orders_for_side(order_group.side)
        return super().formfield_for_manytomany(db_field, request, **kwargs)
