from django.db import models

from us.models import Symbol, get_default_symbol_id, Kline


class KlineDiagnosticsResult(models.Model):
    symbol = models.ForeignKey(Symbol, on_delete=models.CASCADE, default=get_default_symbol_id)
    start_time = models.PositiveBigIntegerField()
    end_time = models.PositiveBigIntegerField()
    kline_type = models.CharField(max_length=20, blank=True, null=True, editable=False, default='Kline')
    created_at = models.DateTimeField(auto_now_add=True)
    incorrect_klines = models.ManyToManyField(Kline)
    report = models.JSONField(blank=True, null=True)

    class Meta:
        verbose_name_plural = 'Kline diagnostics results'
