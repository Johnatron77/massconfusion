import time
from typing import Optional

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from us.models import TimeframeGroup
from us_orders.models.order import Order, OrderValidationErrors
from woo.models import WooAlgoOrder


class OrderGroupValidationErrors:
    IS_PENDING_BUT_STOP_IS_NOT_NULL = 'Order group status is pending but stop is not null'
    IS_CLOSED = 'Order group status is closed'

    ORDER_SIDE_DOES_NOT_MATCH_GROUP_SIDE = 'Order side is not the same as group side'
    ORDER_IS_ALREADY_IN_A_GROUP = 'Order is already in a group'
    ONLY_ONE_PENDING_ORDER_ALLOWED = 'Only one pending order is allowed'
    ORDER_IS_CLOSED = 'Order is closed'

    STOP_IS_NOT_REDUCE_ONLY = 'Stop is not reduce only'
    STOP_SIDE_IS_THE_SAME_AS_ORDER_SIDE = 'Stop side is the same as order side'
    STOP_QUANTITY_IS_NOT_SUM_OF_ORDER_QUANTITY = 'Stop quantity is not sum of order quantity'


class OrderGroupQuerySet(models.QuerySet):
    def current_active(self):
        # TODO Should this get the latest FILLED order and then use reverse to get its group instead?
        try:
            order_group = self.filter(orders__order__status='FILLED').latest('created_at')
            return [order_group, None][order_group.is_closed]
        except self.model.DoesNotExist:
            return None

    def current_pending(self):
        # TODO Should this get the latest NEW order and then use reverse to get its group instead?
        try:
            return self.filter(~models.Q(orders__order__status='FILLED') & models.Q(orders__order__status='NEW')).latest('created_at')
        except self.model.DoesNotExist:
            return None

    def current_pending_by_side(self, side):
        # TODO Should this get the latest NEW order and then use reverse to get its group instead?
        try:
            return self.filter(side=side).filter(~models.Q(orders__order__status='FILLED') & models.Q(orders__order__status='NEW')).latest('created_at')
        except self.model.DoesNotExist:
            return None

    def current_group_for_side(self, side):
        try:
            return self.filter(side=side).latest('created_at')
        except self.model.DoesNotExist:
            return None

    def by_stop_order_id(self, stop_order_id):
        return self.filter(stop__order_id=stop_order_id).first()


class OrderGroupManager(models.Manager):

    def get_queryset(self) -> OrderGroupQuerySet:
        return OrderGroupQuerySet(self.model, using=self._db, hints=self._hints)

    def get_current_active_group(self) -> Optional['OrderGroup']:
        return self.get_queryset().current_active()

    def get_latest_pending_group(self) -> Optional['OrderGroup']:
        return self.get_queryset().current_pending()

    def get_latest_pending_group_for_side(self, side: str) -> Optional['OrderGroup']:
        return self.get_queryset().current_pending_by_side(side)

    def get_latest_group_for_side(self, side: str) -> Optional['OrderGroup']:
        return self.get_queryset().current_group_for_side(side)

    def get_group_by_order_id(self, order_id: int) -> Optional['OrderGroup']:
        order = Order.objects.get_order_by_order_id(order_id)
        if order is None:
            return None
        return self.get_group_by_order(order)

    def get_group_by_order(self, order: Order) -> Optional['OrderGroup']:
        return order.order_groups.first()

    def get_group_by_stop_order_id(self, stop_order_id: int) -> Optional['OrderGroup']:
        return self.get_queryset().by_stop_order_id(stop_order_id)

    def get_group_by_stop_order(self, stop_order: Order) -> Optional['OrderGroup']:
        return self.get_queryset().by_stop_order_id(stop_order.order_id)


class OrderGroup(models.Model):
    group = models.ForeignKey(TimeframeGroup, on_delete=models.CASCADE)
    side = models.CharField(max_length=4, choices=(('BUY', 'BUY'), ('SELL', 'SELL')), default='BUY')
    orders = models.ManyToManyField(Order, related_name='order_groups')
    stop = models.OneToOneField(WooAlgoOrder, on_delete=models.SET_NULL, related_name='order_group_stop', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = OrderGroupManager()

    @property
    def quantity(self):
        if self._has_no_orders:
            return 0
        filled = self.orders.filter(order__status='FILLED')
        return round(sum(float(ordr.quantity) for ordr in filled.all()), 6)

    @property
    def is_empty(self):
        return self._has_no_orders

    @property
    def _is_pending(self):
        if self._has_no_orders:
            return False
        return all(ordr.status in ['NEW', 'CANCELLED'] for ordr in self.orders.all())

    @property
    def is_pending(self):
        return not self.is_closed and self._is_pending

    @property
    def _is_active(self):
        if self._has_no_orders:
            return False
        return any(ordr.status == 'FILLED' for ordr in self.orders.all())

    @property
    def is_active(self):
        return not self.is_closed and self._is_active

    @property
    def _is_canceled(self):
        if self._has_no_orders:
            return False
        return all(ordr.status in ['CANCELLED', 'REJECTED'] for ordr in self.orders.all())

    @property
    def is_closed(self):
        if self._is_canceled:
            return True
        if self.has_reached_max_consecutive_order_stops_limit:
            return True
        if self.is_stopped_out:
            return True
        return self._all_orders_closed

    @property
    def _all_orders_closed(self):
        if self._has_no_orders:
            return False
        return all(ordr.status == 'CLOSED' for ordr in self.orders.all())

    @property
    def is_stopped_out(self):
        return self.stop is not None and self.stop.status in ['FILLED', 'CANCELLED', 'REJECTED']

    @property
    def has_reached_max_consecutive_order_stops_limit(self):
        if self._has_no_orders:
            return False
        count = sum(1 for ordr in self.orders.all() if ordr.is_stopped_out)
        return count >= self.group.strategy_variables.max_consecutive_stops

    @property
    def has_reached_max_order_limit(self):
        if self._has_no_orders:
            return False
        count = sum(1 for ordr in self.orders.all() if ordr.status == 'FILLED')
        return count >= self.group.strategy_variables.max_active_orders

    @property
    def has_exceeded_allowed_minutes_since_last_filled_order(self):

        if self._has_no_orders:
            return True

        last_filled_order = self.orders.filter(
            order__status='FILLED',
            order__trigger_time__isnull=False
        ).order_by('-order__trigger_time').first()

        if last_filled_order is None:
            return True

        minutes_passed = (time.time() - float(last_filled_order.trigger_time))/ 60

        return minutes_passed > self.group.strategy_variables.minimum_minutes_since_last_order

    @property
    def current_pending_order(self) -> Optional[Order]:
        if self._has_no_orders:
            return None
        return self.orders.filter(order__status='NEW').order_by('-created_at').first()

    @property
    def has_stop(self):
        return self.stop is not None

    @property
    def _has_no_orders(self):
        return self.pk is None or len(self.orders.all()) == 0

    def set_stop(self, stop: Optional[WooAlgoOrder]):
        self.stop = stop
        self.save()

    def clean(self):
        if self.has_stop:
            if self.stop.side == self.side:
                raise ValidationError(OrderValidationErrors.STOP_SIDE_IS_THE_SAME_AS_ORDER_SIDE)
            if not self.stop.reduce_only:
                raise ValidationError(OrderValidationErrors.STOP_IS_NOT_REDUCE_ONLY)
            if self.quantity != 0 and self.quantity != self.stop.quantity:
                raise ValidationError(OrderGroupValidationErrors.STOP_QUANTITY_IS_NOT_SUM_OF_ORDER_QUANTITY)
            if self._is_pending:
                raise ValidationError(OrderGroupValidationErrors.IS_PENDING_BUT_STOP_IS_NOT_NULL)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name_plural = 'Order Groups'
        ordering = ['-created_at']


@receiver(m2m_changed, sender=OrderGroup.orders.through)
def verify_order_validity(sender, action, instance, pk_set, **kwargs):
    if action != 'pre_add':
        return
    order_group = instance
    for order_id in pk_set:
        order = Order.objects.get(pk=order_id)
        if len(order.order_groups.all()) > 0:
            raise ValidationError(f'{OrderGroupValidationErrors.ORDER_IS_ALREADY_IN_A_GROUP} - {str(order.id)}')
        if order.is_closed:
            raise ValidationError(f'{OrderGroupValidationErrors.ORDER_IS_CLOSED} - {str(order.id)}')
        if order_group.is_closed:
            raise ValidationError(f'{OrderGroupValidationErrors.IS_CLOSED}')
        if order.side != order_group.side:
            raise ValidationError(f'{OrderGroupValidationErrors.ORDER_SIDE_DOES_NOT_MATCH_GROUP_SIDE} - {str(order.id)}')
        if order.is_pending and order_group.current_pending_order is not None:
            raise ValidationError(f'{OrderGroupValidationErrors.ONLY_ONE_PENDING_ORDER_ALLOWED} - {str(order.id)}')
