from django.contrib import admin

from common.util.admin import linkify
from .models import KlineDiagnosticsResult

'''
@admin.register(KlineDiagnosticsResult)
class KlineDiagnosticsResultAdmin(admin.ModelAdmin):
    readonly_fields = ('id', 'report', 'symbol', 'start_time', 'end_time', 'kline_type', 'incorrect_klines', 'created_at',)
    list_display = ('id', 'symbol', 'start_time', 'end_time', 'get_incorrect_klines', 'created_at',)
    sortable_by = ('start_time', 'end_time', 'created_at',)
    ordering = ('-created_at',)

    @admin.display(description='incorrect klines')
    def get_incorrect_klines(self, obj: KlineDiagnosticsResult):
        return linkify(
            field_name='incorrect_klines',
            label_prop='pk'
        )(obj)
'''
