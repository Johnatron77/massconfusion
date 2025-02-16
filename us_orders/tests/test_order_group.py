import time
from datetime import datetime, timedelta
from unittest.mock import patch

import pytz
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils.timezone import make_aware

from us_orders.models.order import OrderValidationErrors
from us_orders.models.order_group import OrderGroupValidationErrors, OrderGroup
from us_orders.tests.factory.order_factory import OrderFactory
from us_orders.tests.factory.order_group_factory import OrderGroupFactory
from woo.tests.factory.woo_algo_order_factory import WooAlgoOrderFactory


class OrderGroupModelTests(TestCase):

    def test_quantity__when_the_group_has_no_orders(self):
        group = OrderGroupFactory(orders=[])
        self.assertEquals(group.quantity, 0)

    def test_quantity__when_the_group_only_has_pending_orders(self):
        group = OrderGroupFactory()
        self.assertTrue(group.is_pending)
        self.assertEqual(group.quantity, 0)

    def test_quantity__when_the_group_has_mixed_status_orders(self):
        side = 'SELL'
        order1 = OrderFactory(indicator__type=side, order__quantity=3)
        order2 = OrderFactory(indicator__type=side, order__quantity=2, order__status='FILLED')
        order3 = OrderFactory(indicator__type=side, order__quantity=10, order__status='FILLED')
        order_group = OrderGroupFactory(side=side, orders=[order1, order2, order3])
        self.assertEqual(order_group.quantity, 12)

    def test_quantity__when_the_group_only_has_completed_orders(self):
        side = 'SELL'
        order1 = OrderFactory(indicator__type=side, order__quantity=3, order__status='FILLED')
        order2 = OrderFactory(indicator__type=side, order__quantity=2, order__status='FILLED')
        order3 = OrderFactory(indicator__type=side, order__quantity=10, order__status='FILLED')
        order_group = OrderGroupFactory(side=side, orders=[order1, order2, order3])
        self.assertEqual(order_group.quantity, 15)

    def test_quantity__when_the_group_has_stopped_out_orders(self):
        side = 'SELL'
        order1 = OrderFactory(indicator__type=side, order__quantity=3, order__status='FILLED')
        order2 = OrderFactory(indicator__type=side, order__quantity=2, order__status='FILLED')
        order3 = OrderFactory(indicator__type=side, order__quantity=10, order__status='FILLED')
        order_group = OrderGroupFactory(side=side, orders=[order1, order2, order3])
        self.assertEqual(order_group.quantity, 15)
        order1.stop.status = 'FILLED'
        order1.stop.realized_pnl = -5.0
        order1.stop.save()
        self.assertEqual(order_group.quantity, 12)

    def test_is_empty__when_group_has_no_orders(self):
        group = OrderGroupFactory(orders=[])
        self.assertTrue(group.is_empty)

    def test_is_empty__when_group_is_not_empty(self):
        group = OrderGroupFactory()
        self.assertFalse(group.is_empty)

    def test_is_pending__when_group_has_no_orders(self):
        group = OrderGroupFactory(orders=[])
        self.assertFalse(group.is_pending)

    def test_is_pending__when_group_has_orders_but_none_are_pending(self):
        group = OrderGroupFactory(orders__order__status='FILLED')
        self.assertFalse(group.is_pending)

    def test_is_pending__when_group_only_has_cancelled_orders(self):
        group = OrderGroupFactory(orders__order__status='CANCELLED')
        self.assertFalse(group.is_pending)

    def test_is_pending__when_group_contains_completed_orders(self):
        group = OrderGroupFactory()
        self.assertTrue(group.is_pending)
        group.orders.add(OrderFactory(
            order__status='CANCELLED',
            direction=group.side
        ))
        self.assertTrue(group.is_pending)
        group.orders.add(OrderFactory(
            order__status='FILLED',
            direction=group.side
        ))
        self.assertFalse(group.is_pending)

    def test_is_pending__when_group_has_only_pending_orders(self):
        group = OrderGroupFactory()
        self.assertTrue(group.is_pending)

    def test_is_active__when_group_has_no_orders(self):
        group = OrderGroupFactory(orders=[])
        self.assertFalse(group.is_active)

    def test_is_active__when_group_only_has_non_completed_orders(self):
        group = OrderGroupFactory(orders__order__status='NEW')
        self.assertFalse(group.is_active)
        group.orders.add(OrderFactory(
            order__status='CANCELLED',
            direction=group.side
        ))
        self.assertFalse(group.is_active)
        group.orders.add(OrderFactory(
            order__status='REJECTED',
            direction=group.side
        ))
        self.assertFalse(group.is_active)

    def test_is_active__when_group_has_completed_orders(self):
        group = OrderGroupFactory()
        self.assertFalse(group.is_active)
        group.orders.add(OrderFactory(
            order__status='CANCELLED',
            direction=group.side
        ))
        self.assertFalse(group.is_active)
        group.orders.add(OrderFactory(
            order__status='FILLED',
            direction=group.side
        ))
        self.assertTrue(group.is_active)

    def test_is_closed__when_group_has_no_orders(self):
        group = OrderGroupFactory(orders=[])
        self.assertFalse(group.is_closed)

    def test_is_closed__when_group_has_orders_but_none_are_canceled(self):
        group = OrderGroupFactory(orders__order__status='FILLED')
        self.assertFalse(group.is_closed)

    def test_is_closed__when_group_only_has_canceled_orders(self):
        group = OrderGroupFactory(orders__order__status='NEW')
        self.assertFalse(group.is_closed)
        group.orders.add(OrderFactory(
            order__status='CANCELLED',
            direction=group.side
        ))
        self.assertFalse(group.is_closed)
        for ordr in group.orders.all():
            ordr.order.status = 'CANCELLED'
            ordr.order.save()
        self.assertTrue(group.is_closed)

    def test_is_closed__when_stop_is_not_null_but_realized_pnl_is_none(self):
        group = OrderGroupFactory(orders__order__status='NEW')
        self.assertTrue(group.is_pending)
        self.assertFalse(group.is_closed)
        for ordr in group.orders.all():
            ordr.order.status = 'FILLED'
            ordr.order.save()
        group.stop = WooAlgoOrderFactory(
            side=['SELL', 'BUY'][group.side == 'SELL'],
            reduce_only=True,
            quantity=group.quantity
        )
        group.save()
        self.assertIsNone(group.stop.realized_pnl)
        self.assertFalse(group.is_closed)

    def test_is_closed__when_stop_is_not_null_and_realized_pnl_is_not_null(self):
        group = OrderGroupFactory(orders__order__status='NEW')
        self.assertTrue(group.is_pending)
        self.assertFalse(group.is_closed)
        for ordr in group.orders.all():
            ordr.order.status = 'FILLED'
            ordr.order.save()
        group.stop = WooAlgoOrderFactory(
            side=['SELL', 'BUY'][group.side == 'SELL'],
            reduce_only=True,
            quantity=group.quantity
        )
        group.save()
        self.assertFalse(group.is_closed)
        group.stop.status = 'FILLED'
        group.stop.save()
        self.assertTrue(group.is_closed)

    def test_is_closed__when_max_consecutive_order_stops_limit_is_reached(self):
        side = 'SELL'
        max_consective_stops = 2
        order1 = OrderFactory(indicator__type=side, order__status='FILLED')
        order2 = OrderFactory(indicator__type=side, order__status='FILLED')
        group = OrderGroupFactory(
            group__strategy_variables__max_consecutive_stops=max_consective_stops,
            side=side,
            orders=[order1, order2]
        )
        self.assertFalse(group.is_closed)

        self.assertFalse(order1.is_stopped_out)
        order1.stop.status = 'FILLED'
        order1.stop.realized_pnl = 5.0
        order1.stop.save()
        self.assertTrue(order1.is_stopped_out)

        self.assertFalse(group.is_closed)

        self.assertFalse(order2.is_stopped_out)
        order2.stop.status = 'FILLED'
        order2.stop.realized_pnl = 5.0
        order2.stop.save()
        self.assertTrue(order2.is_stopped_out)

        self.assertTrue(group.is_closed)

    def test_is_stopped_out__when_group_has_no_orders(self):
        group = OrderGroupFactory(orders=[])
        self.assertFalse(group.is_stopped_out)

    def test_is_stopped_out__when_group_has_orders_but_no_stop(self):
        group = OrderGroupFactory(orders__order__status='FILLED')
        self.assertFalse(group.is_stopped_out)

    def test_is_stopped_out__when_group_has_stop_but_it_is_not_filled(self):
        group = OrderGroupFactory(orders__order__status='FILLED')
        self.assertFalse(group.is_stopped_out)
        group.set_stop(WooAlgoOrderFactory(
            side=['SELL', 'BUY'][group.side == 'SELL'],
            status='NEW',
            reduce_only=True,
            quantity=group.quantity
        ))
        self.assertFalse(group.is_stopped_out)

    def test_is_stopped_out__when_group_has_stop_and_it_is_filled(self):
        group = OrderGroupFactory(orders__order__status='FILLED')
        self.assertFalse(group.is_stopped_out)
        group.set_stop(WooAlgoOrderFactory(
            side=['SELL', 'BUY'][group.side == 'SELL'],
            status='FILLED',
            reduce_only=True,
            quantity=group.quantity,
            realized_pnl=5.0
        ))
        self.assertTrue(group.is_stopped_out)

    def test_has_reached_max_consecutive_order_stops_limit__when_there_are_no_orders(self):
        group = OrderGroupFactory()
        self.assertFalse(group.has_reached_max_consecutive_order_stops_limit)

    def test_has_reached_max_consecutive_order_stops_limit__when_there_are_orders_but_none_have_stopped_out(self):
        group = OrderGroupFactory(orders__order__status='FILLED')
        self.assertFalse(group.has_reached_max_consecutive_order_stops_limit)

    def test_has_reached_max_consecutive_order_stops_limit__when_there_are_orders_and_some_have_stopped_out(self):
        side = 'SELL'
        max_consective_stops = 2
        order1 = OrderFactory(indicator__type=side, order__status='FILLED')
        order2 = OrderFactory(indicator__type=side, order__status='FILLED')
        group = OrderGroupFactory(
            group__strategy_variables__max_consecutive_stops=max_consective_stops,
            side=side,
            orders=[order1, order2]
        )
        self.assertFalse(group.has_reached_max_consecutive_order_stops_limit)

        self.assertFalse(order1.is_stopped_out)
        order1.stop.status = 'FILLED'
        order1.stop.realized_pnl = 5.0
        order1.stop.save()
        self.assertTrue(order1.is_stopped_out)

        self.assertFalse(group.has_reached_max_consecutive_order_stops_limit)

        self.assertFalse(order2.is_stopped_out)
        order2.stop.status = 'FILLED'
        order2.stop.realized_pnl = 5.0
        order2.stop.save()
        self.assertTrue(order2.is_stopped_out)

        self.assertTrue(group.has_reached_max_consecutive_order_stops_limit)

    def test_has_reached_max_order_limit__when_there_are_no_orders(self):
        group = OrderGroupFactory(orders=[])
        self.assertFalse(group.has_reached_max_order_limit)

    def test_has_reached_max_order_limit__when_there_are_orders_but_none_are_FILLED(self):
        group = OrderGroupFactory(orders__order__status='NEW')
        self.assertFalse(group.has_reached_max_order_limit)

    def test_has_reached_max_order_limit__when_order_count_equal_max_but_not_all_are_FILLED(self):
        side = 'SELL'
        max_active_orders = 3
        order1 = OrderFactory(indicator__type=side, order__status='FILLED')
        order2 = OrderFactory(indicator__type=side, order__status='FILLED')
        order3 = OrderFactory(indicator__type=side, order__status='NEW')
        group = OrderGroupFactory(
            group__strategy_variables__max_active_orders=max_active_orders,
            side=side,
            orders=[order1, order2, order3]
        )
        self.assertFalse(group.has_reached_max_order_limit)

    def test_has_reached_max_order_limit__when_max_orders_are_FILLED(self):
        side = 'SELL'
        max_active_orders = 3
        order1 = OrderFactory(indicator__type=side, order__status='FILLED')
        order2 = OrderFactory(indicator__type=side, order__status='FILLED')
        order3 = OrderFactory(indicator__type=side, order__status='FILLED')
        group = OrderGroupFactory(
            group__strategy_variables__max_active_orders=max_active_orders,
            side=side,
            orders=[order1, order2, order3]
        )
        self.assertTrue(group.has_reached_max_order_limit)

    def test_has_exceeded_allowed_minutes_since_last_filled_order__when_there_are_no_orders(self):
        group = OrderGroupFactory(orders=[])
        self.assertTrue(group.has_exceeded_allowed_minutes_since_last_filled_order)

    def test_has_exceeded_allowed_minutes_since_last_filled_order__when_there_are_orders_but_none_are_filled(self):
        group = OrderGroupFactory(orders__order__status='NEW')
        self.assertTrue(group.has_exceeded_allowed_minutes_since_last_filled_order)

    def test_has_exceeded_allowed_minutes_since_last_filled_order__when_the_last_FILLED_order_is_older_than_allowed_exceeded(self):
        side = 'SELL'
        minimum_minutes_since_last_order = 5
        order1 = OrderFactory(direction=side)
        order2 = OrderFactory(
            direction=side,
            order__status='FILLED',
            order__trigger_time=time.time() - ((minimum_minutes_since_last_order + 1) * 60)
        )
        order3 = OrderFactory(
            direction=side,
            order__status='FILLED',
            order__trigger_time=time.time() - ((minimum_minutes_since_last_order + 5) * 60)
        )
        group = OrderGroupFactory(
            group__strategy_variables__minimum_minutes_since_last_order=minimum_minutes_since_last_order,
            side=side,
            orders=[order1, order2, order3]
        )
        self.assertTrue(group.has_exceeded_allowed_minutes_since_last_filled_order)

    def test_has_exceeded_allowed_minutes_since_last_filled_order__when_the_last_FILLED_order_is_younger_than_allowed_exceeded(self):
        side = 'SELL'
        minimum_minutes_since_last_order = 5
        created_at = make_aware(
            datetime.today() - timedelta(minutes=minimum_minutes_since_last_order - 1)
        )
        with patch('django.utils.timezone.now', return_value=created_at):
            order1 = OrderFactory(indicator__type=side)
            order2 = OrderFactory(
                indicator__type=side,
                order__status='FILLED',
                created_at=created_at
            )
            group = OrderGroupFactory(
                group__strategy_variables__minimum_minutes_since_last_order=minimum_minutes_since_last_order,
                side=side,
                orders=[order1, order2]
            )
            self.assertFalse(group.has_exceeded_allowed_minutes_since_last_filled_order)

    def test_current_pending_order__when_there_are_no_orders(self):
        group = OrderGroupFactory(orders=[])
        self.assertIsNone(group.current_pending_order)

    def test_current_pending_order__when_there_are_orders_but_none_are_pending(self):
        group = OrderGroupFactory(orders__order__status='FILLED')
        self.assertIsNone(group.current_pending_order)

    def test_test_current_pending_order__when_there_are_orders_and_some_are_pending(self):
        side = 'SELL'
        order1 = OrderFactory(indicator__type=side, order__status='FILLED')
        order2 = OrderFactory(indicator__type=side, order__status='FILLED')
        order3 = OrderFactory(indicator__type=side, order__status='NEW')
        group = OrderGroupFactory(side=side, orders=[order1, order2, order3])
        self.assertIsNotNone(group.current_pending_order)
        self.assertEqual(group.current_pending_order, order3)

    def test_has_stop__when_group_has_no_stop(self):
        group = OrderGroupFactory()
        self.assertFalse(group.has_stop)

    def test_has_stop__when_group_has_stop(self):
        group = OrderGroupFactory(orders__order__status='FILLED')
        self.assertFalse(group.has_stop)
        group.set_stop(WooAlgoOrderFactory(
            side=['SELL', 'BUY'][group.side == 'SELL'],
            status='FILLED',
            reduce_only=True,
            quantity=group.quantity
        ))
        self.assertTrue(group.has_stop)

    def test_set_stop(self):
        group = OrderGroupFactory(orders__order__status='FILLED')
        self.assertFalse(group.has_stop)
        group.set_stop(WooAlgoOrderFactory(
            side=['SELL', 'BUY'][group.side == 'SELL'],
            status='FILLED',
            reduce_only=True,
            quantity=group.quantity
        ))
        self.assertIsNotNone(group.stop)


class OrderGroupModelValidationTests(TestCase):

    def test_when_group_side_is_the_same_as_stop_side_validation_error(self):
        side = 'SELL'
        group = OrderGroupFactory(side=side)
        self.assertEqual(group.side, side)
        stop_order = WooAlgoOrderFactory(side=side, reduce_only=True)
        self.assertEqual(stop_order.side, side)
        try:
            group.stop = stop_order
            group.save()
            self.fail('Should have raised ValidationError')
        except ValidationError as e:
            self.assertEqual(e.message, OrderValidationErrors.STOP_SIDE_IS_THE_SAME_AS_ORDER_SIDE)

    def test_when_stop_is_not_reduce_only_validation_error(self):
        group = OrderGroupFactory(side='SELL')
        self.assertEqual(group.side, 'SELL')
        stop_order = WooAlgoOrderFactory(side='BUY')
        self.assertEqual(stop_order.side, 'BUY')
        self.assertFalse(stop_order.reduce_only)
        try:
            group.stop = stop_order
            group.save()
            self.fail('Should have raised ValidationError')
        except ValidationError as e:
            self.assertEqual(e.message, OrderValidationErrors.STOP_IS_NOT_REDUCE_ONLY)

    def test_when_stop_quantity_is_not_sum_of_order_quantity_validation_error(self):
        order_count = 3
        quantity = 2
        total_quantity = order_count * quantity
        group = OrderGroupFactory(
            side='SELL',
            orders__count=order_count,
            orders__order__status='FILLED',
            orders__order__quantity=quantity
        )
        self.assertEqual(group.orders.count(), order_count)
        self.assertEqual(group.quantity, total_quantity)
        stop_order = WooAlgoOrderFactory(side='BUY', reduce_only=True, quantity=total_quantity - 1)
        try:
            group.stop = stop_order
            group.save()
            self.fail('Should have raised ValidationError')
        except ValidationError as e:
            self.assertEqual(e.message, OrderGroupValidationErrors.STOP_QUANTITY_IS_NOT_SUM_OF_ORDER_QUANTITY)

    def test_when_order_status_is_pending_but_stop_is_not_null_validation_error(self):
        group = OrderGroupFactory(side='SELL')
        self.assertIsNotNone(group.quantity)
        self.assertTrue(group.is_pending)
        stop_order = WooAlgoOrderFactory(side='BUY', reduce_only=True, quantity=group.quantity)
        try:
            group.stop = stop_order
            group.save()
            self.fail('Should have raised ValidationError')
        except ValidationError as e:
            self.assertEqual(e.message, OrderGroupValidationErrors.IS_PENDING_BUT_STOP_IS_NOT_NULL)

    def test_when_order_already_belongs_to_a_group_validation_error(self):
        order = OrderFactory(indicator__type='SELL')
        OrderGroupFactory(side='SELL', orders=[order])
        try:
            OrderGroupFactory(side='SELL', orders=[order])
            self.fail('Should have raised ValidationError')
        except ValidationError as e:
            self.assertEqual(e.message, f'{OrderGroupValidationErrors.ORDER_IS_ALREADY_IN_A_GROUP} - {str(order.id)}')

    def test_when_order_side_does_not_match_group_side_validation_error(self):
        order1 = OrderFactory(indicator__type='SELL')
        order2 = OrderFactory(indicator__type='BUY')
        try:
            OrderGroupFactory(side='SELL', orders=[order1, order2])
            self.fail('Should have raised ValidationError')
        except ValidationError as e:
            self.assertEqual(e.message, f'{OrderGroupValidationErrors.ORDER_SIDE_DOES_NOT_MATCH_GROUP_SIDE} - {str(order2.id)}')

    def test_when_a_group_is_closed_it_no_longer_excepts_orders(self):
        group = OrderGroupFactory(orders__order__status='FILLED', orders__with_matching_stop=True)
        self.assertTrue(group.is_active)
        self.assertFalse(group.is_closed)
        group.stop.status = 'FILLED'
        group.stop.save()
        self.assertTrue(group.is_closed)
        order = OrderFactory(indicator__type=group.side)
        try:
            group.orders.add(order)
            self.fail('Should have raised ValidationError')
        except ValidationError as e:
            self.assertEqual(e.message, OrderGroupValidationErrors.IS_CLOSED)

    def test_when_a_group_has_an_existing_pending_order_no_other_pending_orders_can_be_added(self):
        group = OrderGroupFactory(orders__order__status='NEW')
        self.assertTrue(group.is_pending)
        order = OrderFactory(indicator__type=group.side)
        try:
            group.orders.add(order)
            self.fail('Should have raised ValidationError')
        except ValidationError as e:
            self.assertEqual(e.message, f'{OrderGroupValidationErrors.ONLY_ONE_PENDING_ORDER_ALLOWED} - {str(order.id)}')

    def test_when_order_being_added_is_already_closed(self):
        order = OrderFactory(order__status='FILLED', stop__status='FILLED')
        self.assertEqual(order.status, 'CLOSED')
        group = OrderGroupFactory(orders=[])
        try:
            group.orders.add(order)
            self.fail('Should have raised ValidationError')
        except ValidationError as e:
            self.assertEqual(e.message, f'{OrderGroupValidationErrors.ORDER_IS_CLOSED} - {str(order.id)}')


class OrderGroupManagerTests(TestCase):

    def test_get_current_active_group__when_there_are_no_active_groups(self):
        OrderGroupFactory(
            orders__count=1,
            orders__order__status='CANCELLED',
        )
        OrderGroupFactory.create_batch(
            3,
            orders__order__status='NEW',
        )
        self.assertIsNone(OrderGroup.objects.get_current_active_group())

    def test_get_current_active_group__when_there_are_active_groups(self):
        active_groups = OrderGroupFactory.create_batch(
            3,
            orders__order__status='FILLED',
            orders__with_matching_stop=True,
        )
        OrderGroupFactory.create_batch(
            3,
            orders__order__status='NEW',
        )
        latest_active_group = OrderGroupFactory.create(
            orders__order__status='FILLED',
            orders__with_matching_stop=True,
        )
        OrderGroupFactory(
            orders__count=1,
            orders__order__status='CANCELLED',
        )
        self.assertEqual(OrderGroup.objects.get_current_active_group(), latest_active_group)
        latest_active_group.delete()
        self.assertEqual(OrderGroup.objects.get_current_active_group(), active_groups[-1])

    def test_get_current_active_group__when_all_previous_active_groups_are_closed(self):
        active_group = OrderGroupFactory(
            orders__order__status='FILLED',
            orders__with_matching_stop=True,
        )
        self.assertTrue(active_group.is_active)
        self.assertEqual(OrderGroup.objects.get_current_active_group(), active_group)
        active_group.stop.status = 'FILLED'
        active_group.stop.save()
        self.assertFalse(active_group.is_active)
        self.assertTrue(active_group.is_closed)
        self.assertIsNone(OrderGroup.objects.get_current_active_group())

    def test_get_latest_pending_group(self):
        self.assertIsNone(OrderGroup.objects.get_latest_pending_group())
        group = OrderGroupFactory(
            orders__order__status='NEW',
        )
        self.assertEqual(OrderGroup.objects.get_latest_pending_group(), group)
        OrderGroupFactory.create(
            orders__count=3,
            orders__order__status='FILLED',
            orders__with_matching_stop=True,
        )
        self.assertEqual(OrderGroup.objects.get_latest_pending_group(), group)
        group2 = OrderGroupFactory(
            orders__order__status='NEW',
        )
        self.assertNotEquals(OrderGroup.objects.get_latest_pending_group(), group)
        self.assertEqual(OrderGroup.objects.get_latest_pending_group(), group2)
        group2.delete()
        self.assertEqual(OrderGroup.objects.get_latest_pending_group(), group)

    def test_get_latest_pending_group_for_side(self):
        self.assertIsNone(OrderGroup.objects.get_latest_pending_group_for_side('BUY'))
        group = OrderGroupFactory(side='BUY', orders__order__status='NEW')
        self.assertEqual(OrderGroup.objects.get_latest_pending_group_for_side('BUY'), group)
        OrderGroupFactory(side='SELL', orders__order__status='NEW')
        self.assertEqual(OrderGroup.objects.get_latest_pending_group_for_side('BUY'), group)
        group2 = OrderGroupFactory(side='BUY', orders__order__status='NEW')
        self.assertNotEquals(OrderGroup.objects.get_latest_pending_group_for_side('BUY'), group)
        self.assertEqual(OrderGroup.objects.get_latest_pending_group_for_side('BUY'), group2)
        group2.delete()
        self.assertEqual(OrderGroup.objects.get_latest_pending_group_for_side('BUY'), group)

    def test_get_latest_group_for_side(self):
        self.assertIsNone(OrderGroup.objects.get_latest_group_for_side('BUY'))
        group = OrderGroupFactory(side='BUY')
        self.assertEqual(OrderGroup.objects.get_latest_group_for_side('BUY'), group)
        OrderGroupFactory(side='SELL')
        self.assertEqual(OrderGroup.objects.get_latest_group_for_side('BUY'), group)
        group2 = OrderGroupFactory(side='BUY')
        self.assertNotEquals(OrderGroup.objects.get_latest_group_for_side('BUY'), group)
        self.assertEqual(OrderGroup.objects.get_latest_group_for_side('BUY'), group2)
        group2.delete()
        self.assertEqual(OrderGroup.objects.get_latest_group_for_side('BUY'), group)

    def test_get_group_by_order_id(self):
        order_id = 7654321
        order = OrderFactory(order__order_id=order_id)
        self.assertEqual(order.order.order_id, order_id)
        group = OrderGroupFactory(orders=[order], side=order.indicator.type)
        self.assertEqual(OrderGroup.objects.get_group_by_order_id(order_id), group)
        self.assertIsNone(OrderGroup.objects.get_group_by_order_id(order_id + 1))

    def test_get_group_by_order(self):
        order = OrderFactory()
        group = OrderGroupFactory(orders=[order], side=order.indicator.type)
        self.assertEqual(OrderGroup.objects.get_group_by_order(order), group)
        self.assertIsNone(OrderGroup.objects.get_group_by_order(OrderFactory()))

    def test_get_group_by_stop_order_id(self):
        quantity = 0.1
        order_count = 2
        stop_order = WooAlgoOrderFactory(side='SELL', reduce_only=True, quantity=quantity*order_count)
        group = OrderGroupFactory(
            side='BUY',
            orders__count=order_count,
            orders__order__status='FILLED',
            orders__order__quantity=quantity,
            stop=stop_order
        )
        self.assertEqual(OrderGroup.objects.get_group_by_stop_order_id(stop_order.order_id), group)
        self.assertIsNone(OrderGroup.objects.get_group_by_stop_order_id(stop_order.order_id + 1))

    def test_get_group_by_stop_order(self):
        quantity = 0.1
        order_count = 2
        stop_order = WooAlgoOrderFactory(side='SELL', reduce_only=True, quantity=quantity*order_count)
        group = OrderGroupFactory(
            side='BUY',
            orders__count=order_count,
            orders__order__status='FILLED',
            orders__order__quantity=quantity,
            stop=stop_order
        )
        self.assertEqual(OrderGroup.objects.get_group_by_stop_order(stop_order), group)
        self.assertIsNone(OrderGroup.objects.get_group_by_stop_order(WooAlgoOrderFactory()))