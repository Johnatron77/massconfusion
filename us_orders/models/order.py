from typing import Optional

from django.core.exceptions import ValidationError
from django.db import models

from us.models import TimeframeKlineSignal

from woo.models import WooAlgoOrder


class OrderValidationErrors:
    IS_PENDING_BUT_STOP_IS_NOT_NULL = 'Order status is pending but stop is not null'
    IS_ACTIVE_BUT_STOP_IS_NULL = 'Order status is active but stop is null'

    ORDER_IS_REDUCE_ONLY = 'Order is reduce only'
    ORDER_SIDE_DOES_NOT_MATCH_INDICATOR_SIDE = 'Order side is not the same as indicator side'

    STOP_IS_NOT_REDUCE_ONLY = 'Stop is not reduce only'
    STOP_SIDE_IS_THE_SAME_AS_ORDER_SIDE = 'Stop side is the same as order side'


class OrderQuerySet(models.QuerySet):

    def all_orders_for_side(self, side) -> models.QuerySet:
        return self.filter(order__side=side)

    def pending_orders(self) -> models.QuerySet:
        return self.filter(order__status='NEW')

    def last_pending_order(self) -> Optional['Order']:
        try:
            return self.pending_orders().latest('created_at')
        except self.model.DoesNotExist:
            return None

    def last_pending_order_for_side(self, side) -> Optional['Order']:
        try:
            return self.pending_orders().filter(order__side=side).latest('created_at')
        except self.model.DoesNotExist:
            return None

    def active_orders(self) -> models.QuerySet:
        return self.filter(order__status='FILLED')

    def last_active_order(self) -> Optional['Order']:
        try:
            return self.active_orders().latest('created_at')
        except self.model.DoesNotExist:
            return None

    def last_active_order_for_side(self, side) -> Optional['Order']:
        try:
            return self.active_orders().filter(order__side=side).latest('created_at')
        except self.model.DoesNotExist:
            return None

    def last_order(self) -> Optional['Order']:
        try:
            return self.latest('created_at')
        except self.model.DoesNotExist:
            return None

    def last_order_for_side(self, side) -> Optional['Order']:
        try:
            return self.filter(order__side=side).latest('created_at')
        except self.model.DoesNotExist:
            return None

    def order_by_order_id(self, order_id) -> Optional['Order']:
        order = self.filter(order__order_id=order_id).first()
        if order:
            return order
        return self.filter(stop__order_id=order_id).first()

    def all_pending_reduce_only_orders_for_side(self, side) -> models.QuerySet:
        return self.filter(stop__status='NEW', stop__reduce_only=True, stop__side=side)

    def all_pending_non_reduce_only_orders_for_side(self, side) -> models.QuerySet:
        return self.filter(order__status='NEW', order__reduce_only=False, order__side=side)


class OrderManager(models.Manager):

    def get_queryset(self) -> OrderQuerySet:
        return OrderQuerySet(self.model, using=self._db, hints=self._hints)

    def get_all_orders_for_side(self, side) -> models.QuerySet:
        return self.get_queryset().all_orders_for_side(side)

    def get_pending_orders(self) -> models.QuerySet:
        return self.get_queryset().pending_orders()

    def get_last_pending_order(self) -> Optional['Order']:
        return self.get_queryset().last_pending_order()

    def get_last_pending_order_for_side(self, side) -> Optional['Order']:
        return self.get_queryset().last_pending_order_for_side(side)

    def get_active_orders(self) -> models.QuerySet:
        return self.get_queryset().active_orders()

    def get_last_active_order(self) -> Optional['Order']:
        return self.get_queryset().last_active_order()

    def get_last_active_order_for_side(self, side) -> Optional['Order']:
        return self.get_queryset().last_active_order_for_side(side)

    def get_last_order(self) -> Optional['Order']:
        return self.get_queryset().last_order()

    def get_last_order_for_side(self, side) -> Optional['Order']:
        return self.get_queryset().last_order_for_side(side)

    def get_order_by_order_id(self, order_id) -> Optional['Order']:
        return self.get_queryset().order_by_order_id(order_id)

    def get_all_pending_reduce_only_orders_for_side(self, side) -> models.QuerySet:
        return self.get_queryset().all_pending_reduce_only_orders_for_side(side)

    def get_all_pending_non_reduce_only_orders_for_side(self, side) -> models.QuerySet:
        return self.get_queryset().all_pending_non_reduce_only_orders_for_side(side)


class Order(models.Model):
    order = models.OneToOneField(WooAlgoOrder, on_delete=models.CASCADE)
    stop = models.OneToOneField(WooAlgoOrder, on_delete=models.CASCADE, related_name='order_stop', null=True, blank=True)
    previous_indicators = models.ManyToManyField(TimeframeKlineSignal, related_name='previous_indicators', blank=True)
    indicator = models.ForeignKey(TimeframeKlineSignal, on_delete=models.CASCADE)
    force_close = models.BooleanField(default=False)
    note = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = OrderManager()

    @property
    def status(self):
        return 'CLOSED' if self.is_closed else self.order.status

    @property
    def is_pending(self):
        return self.status == 'NEW'

    @property
    def is_active(self):
        return self.status == 'FILLED'

    @property
    def is_cancelled(self):
        return self.status == 'CANCELLED'

    @property
    def is_closed(self):
        if self.force_close:
            return True
        if self.pk is None:
            return False
        if self.is_stopped_out:
            return True
        order_group = self.order_groups.first()
        if order_group is None:
            return False
        return order_group.is_stopped_out

    @property
    def order_id(self):
        return self.order.order_id

    @property
    def side(self):
        return self.order.side

    @property
    def quantity(self):
        if self.is_cancelled or self.is_stopped_out:
            return 0
        return self.order.quantity

    @property
    def trigger_price(self):
        return self.order.trigger_price

    @property
    def trigger_time(self):
        return self.order.trigger_time

    @property
    def is_stopped_out(self):
        return self.stop is not None and self.stop.status == 'FILLED'

    def update_indicator(self, indicator: TimeframeKlineSignal):
        self.previous_indicators.add(self.indicator)
        self.indicator = indicator
        self.save()

    def set_stop(self, stop: WooAlgoOrder):
        self.stop = stop
        self.save()

    def clean(self):
        if self.order.side != self.indicator.type:
            raise ValidationError(OrderValidationErrors.ORDER_SIDE_DOES_NOT_MATCH_INDICATOR_SIDE)
        if self.status == 'NEW' and self.stop:
            raise ValidationError(OrderValidationErrors.IS_PENDING_BUT_STOP_IS_NOT_NULL)
        if self.status == 'FILLED' and not self.stop:
            raise ValidationError(OrderValidationErrors.IS_ACTIVE_BUT_STOP_IS_NULL)
        if self.order.reduce_only:
            raise ValidationError(OrderValidationErrors.ORDER_IS_REDUCE_ONLY)
        if self.stop and not self.stop.reduce_only:
            raise ValidationError(OrderValidationErrors.STOP_IS_NOT_REDUCE_ONLY)
        if self.stop and self.stop.side == self.side:
            raise ValidationError(OrderValidationErrors.STOP_SIDE_IS_THE_SAME_AS_ORDER_SIDE)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name_plural = 'Orders'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                check=~models.Q(order=models.F('stop')),
                name='order_is_not_the_same_as_stop_constraint',
            ),
            models.UniqueConstraint(
                fields=['order', 'indicator'],
                name='order_unique_constraint',
            ),
        ]
