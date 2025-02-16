import time

from django.db import models
from django.db.models import Q
from inflection import underscore


class StatusChoices(models.TextChoices):
    NEW = 'NEW'
    PARTIAL_FILLED = 'PARTIAL_FILLED'
    FILLED = 'FILLED'
    CANCELLED = 'CANCELLED'
    REJECTED = 'REJECTED'


class TypeChoices(models.TextChoices):
    LIMIT = 'LIMIT'
    MARKET = 'MARKET'


class AlgoTypeChoices(models.TextChoices):
    STOP = 'STOP'
    OCO = 'OCO'
    TRAILING_STOP = 'TRAILING_STOP'
    BRACKET = 'BRACKET'


class SideChoices(models.TextChoices):
    BUY = 'BUY'
    SELL = 'SELL'


class WooAlgoOrderQuerySet(models.QuerySet):

    def all_orders_for_side(self, side) -> models.QuerySet:
        return self.filter(side=side)

    def all_reduce_only_orders_for_side(self, side) -> models.QuerySet:
        return self.filter(reduce_only=True, side=side)

    def all_non_reduce_only_orders_for_side(self, side) -> models.QuerySet:
        return self.filter(reduce_only=False, side=side)


class WooAlgoOrderManager(models.Manager):

    def get_queryset(self) -> WooAlgoOrderQuerySet:
        return WooAlgoOrderQuerySet(self.model, using=self._db, hints=self._hints)

    def get_all_orders_for_side(self, side) -> models.QuerySet:
        return self.get_queryset().all_orders_for_side(side)

    def get_all_reduce_only_orders_for_side(self, side) -> models.QuerySet:
        return self.get_queryset().all_reduce_only_orders_for_side(side)

    def get_all_non_reduce_only_orders_for_side(self, side) -> models.QuerySet:
        return self.get_queryset().all_non_reduce_only_orders_for_side(side)


class WooAlgoOrder(models.Model):
    order_id = models.IntegerField()
    symbol = models.CharField(max_length=20)
    type = models.CharField(max_length=20, choices=TypeChoices.choices, default=TypeChoices.MARKET)
    algo_type = models.CharField(max_length=20, choices=AlgoTypeChoices.choices, default=AlgoTypeChoices.STOP)
    side = models.CharField(max_length=4, choices=SideChoices.choices)
    quantity = models.DecimalField(max_digits=20, decimal_places=4)
    reduce_only = models.BooleanField(default=False)

    is_triggered = models.BooleanField(default=False)
    trigger_price = models.DecimalField(max_digits=20, decimal_places=4)
    trigger_price_type = models.CharField(max_length=20, default='MARKET_PRICE')
    trigger_trade_price = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    trigger_status = models.CharField(max_length=20, null=True, blank=True)
    trigger_time = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)

    status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.NEW)
    order_tag = models.CharField(max_length=20, null=True, blank=True)
    trade_id = models.IntegerField(null=True, blank=True)
    create_time = models.DecimalField(max_digits=20, decimal_places=4, default=time.time)
    updated_time = models.DecimalField(max_digits=20, decimal_places=4, default=time.time)
    total_executed_quantity = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    average_executed_price = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)

    realized_pnl = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    objects = WooAlgoOrderManager()

    def update(self, **kwargs):
        for key, value in kwargs.items():
            ky = key
            try:
                getattr(self, ky)
            except AttributeError as e:
                try:
                    ky = underscore(ky)
                    getattr(self, ky)
                except AttributeError:
                    continue
            setattr(self, ky, value)
        self.save()

    def __str__(self):
        return f'{self.id} - {self.order_id} - {self.side} - {self.status} - {self.reduce_only}'


    class Meta:
        verbose_name_plural = 'Algo Orders'
        constraints = [
            models.CheckConstraint(
                check=Q(side='SELL') | Q(side='BUY'),
                name='woo_algo_order_type_is_sell_or_buy_constraint'
            ),
            models.UniqueConstraint(
                fields=['order_id'],
                name='woo_algo_order_order_id_unique_constraint',
            ),
        ]


class WooAPIError(models.Model):
    type= models.CharField(max_length=30)
    url = models.CharField(max_length=100)
    params = models.CharField(max_length=250, null=True)
    error = models.CharField(max_length=400)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.type} - {self.url} - {self.created_at}'
