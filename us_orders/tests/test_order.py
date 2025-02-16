from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from us.tests.factory.timeframe_kline_signal_factory import TimeframeKlineSignalFactory
from us_orders.models.order import OrderValidationErrors, Order
from us_orders.tests.factory.order_factory import OrderFactory
from us_orders.tests.factory.order_group_factory import OrderGroupFactory
from woo.tests.factory.woo_algo_order_factory import WooAlgoOrderFactory


class OrderModelTests(TestCase):

    def test_status_is_pending__when_order_is_new(self):
        order = OrderFactory(order__status='NEW')
        self.assertEqual(order.status, 'NEW')
        self.assertTrue(order.is_pending)
        self.assertFalse(order.is_active)
        self.assertFalse(order.is_cancelled)

    def test_status_is_active__when_order_is_filled(self):
        order = OrderFactory(order__status='FILLED')
        self.assertEqual(order.status, 'FILLED')
        self.assertFalse(order.is_pending)
        self.assertTrue(order.is_active)
        self.assertFalse(order.is_cancelled)

    def test_status_is_cancelled__when_order_is_cancelled(self):
        order = OrderFactory(order__status='CANCELLED')
        self.assertEqual(order.status, 'CANCELLED')
        self.assertFalse(order.is_pending)
        self.assertFalse(order.is_active)
        self.assertTrue(order.is_cancelled)

    def test_status_is_closed__when_order_is_filled_and_stop_is_filled(self):
        order = OrderFactory(order__status='FILLED', stop__status='FILLED')
        self.assertEqual(order.status, 'CLOSED')
        self.assertFalse(order.is_pending)
        self.assertFalse(order.is_active)
        self.assertFalse(order.is_cancelled)
        self.assertTrue(order.is_stopped_out)

    def test_status_is_closed__when_order_group_has_stopped_out(self):
        side = 'SELL'
        order1 = OrderFactory(indicator__type=side, order__status='FILLED')
        order2 = OrderFactory(indicator__type=side, order__status='FILLED')
        group = OrderGroupFactory(
            side=side,
            orders__with_matching_stop=True,
            orders=[order1, order2]
        )
        group.stop = WooAlgoOrderFactory(
            side=['SELL', 'BUY'][group.side == 'SELL'],
            reduce_only=True,
            quantity=group.quantity
        )
        group.save()
        self.assertIsNone(group.stop.realized_pnl)
        self.assertFalse(group.is_closed)
        group.stop.status = 'FILLED'
        group.stop.save()
        self.assertTrue(group.is_closed)
        self.assertTrue(order1.is_closed)
        self.assertTrue(order2.is_closed)

    def test_is_closed_when_order_is_force_closed(self):
        order = OrderFactory(order__status='CANCELLED')
        self.assertFalse(order.is_closed)
        order.force_close = True
        order.save()
        self.assertTrue(order.is_closed)

    def test_status_matches_order_status(self):
        indicator = TimeframeKlineSignalFactory(type='BUY')
        algo_order = WooAlgoOrderFactory(side='BUY')
        order = Order.objects.create(order_id=algo_order.id, indicator_id=indicator.id)
        self.assertEqual(order.status, 'NEW')
        self.assertEqual(order.status, algo_order.status)
        algo_order.status = 'CANCELLED'
        algo_order.save()
        order.refresh_from_db(fields=['order'])
        self.assertEqual(order.status, 'CANCELLED')

    def test_side__when_order_is_buy(self):
        order = OrderFactory(indicator__type='BUY')
        self.assertEqual(order.side, 'BUY')

    def test_side__when_order_is_sell(self):
        order = OrderFactory(indicator__type='SELL')
        self.assertEqual(order.side, 'SELL')

    def test_side_matches_order_side(self):
        indicator = TimeframeKlineSignalFactory(type='BUY')
        algo_order = WooAlgoOrderFactory(side='BUY', status='FILLED')
        stop_order = WooAlgoOrderFactory(side='SELL', reduce_only=True)
        order = Order.objects.create(order_id=algo_order.id, indicator_id=indicator.id, stop_id=stop_order.id)
        self.assertEqual(order.side, algo_order.side)
        self.assertEqual(order.side, 'BUY')
        algo_order.side = 'SELL'
        algo_order.save()
        order.refresh_from_db(fields=['order'])
        self.assertEqual(order.side, 'SELL')

    def test_quantity(self):
        order = OrderFactory(order__quantity=0.1)
        self.assertEqual(order.quantity, 0.1)

    def test_trigger_price(self):
        order = OrderFactory(order__trigger_price=8.0)
        self.assertEqual(order.trigger_price, 8.0)

    def test_quantity__when_order_is_stopped_out(self):
        order = OrderFactory(order__status='FILLED', order__quantity=0.1, stop__status='FILLED')
        self.assertIsNotNone(order.stop)
        self.assertTrue(order.is_stopped_out)
        self.assertEqual(order.quantity, 0)

    def test_is_stopped_out__when_order_has_no_stop(self):
        order = OrderFactory(stop=None)
        self.assertFalse(order.is_stopped_out)

    def test_is_stopped_out__when_stop_is_not_filled(self):
        order = OrderFactory(stop__status='FILLED')
        self.assertFalse(order.is_stopped_out)

    def test_is_stopped_out__when_order_is_filled_and_stop_is_filled(self):
        order = OrderFactory(order__status='FILLED', stop__status='FILLED')
        self.assertTrue(order.is_stopped_out)

    def test_set_stop(self):
        order = OrderFactory(stop=None)
        self.assertIsNone(order.stop)
        order.order.status = 'FILLED'
        order.order.save()
        stop_order = WooAlgoOrderFactory(side=['SELL', 'BUY'][order.side == 'SELL'], reduce_only=True)
        order.set_stop(stop_order)
        self.assertEqual(order.stop, stop_order)


class OrderModelValidationTests(TestCase):

    def test_when_order_side_does_not_match_indicator_side_validation_error(self):
        try:
            OrderFactory(order__side='BUY', indicator__type='SELL')
            self.fail(f'Should have raised ValidationError - {OrderValidationErrors.ORDER_SIDE_DOES_NOT_MATCH_INDICATOR_SIDE}')
        except ValidationError as e:
            self.assertEqual(e.message, OrderValidationErrors.ORDER_SIDE_DOES_NOT_MATCH_INDICATOR_SIDE)

    def test_when_order_is_new_and_stop_is_not_null_validation_error(self):
        try:
            OrderFactory(order__status='NEW', stop=WooAlgoOrderFactory(side='SELL', reduce_only=True))
            self.fail(f'Should have raised ValidationError - {OrderValidationErrors.IS_PENDING_BUT_STOP_IS_NOT_NULL}')
        except ValidationError as e:
            self.assertEqual(e.message, OrderValidationErrors.IS_PENDING_BUT_STOP_IS_NOT_NULL)

    def test_when_order_is_filled_and_stop_is_null_validation_error(self):
        try:
            OrderFactory(order__status='FILLED', stop=None)
            self.fail(f'Should have raised ValidationError - {OrderValidationErrors.IS_ACTIVE_BUT_STOP_IS_NULL}')
        except ValidationError as e:
            self.assertEqual(e.message, OrderValidationErrors.IS_ACTIVE_BUT_STOP_IS_NULL)

    def test_when_order_is_reduce_only_validation_error(self):
        try:
            OrderFactory(order__reduce_only=True)
            self.fail(f'Should have raised ValidationError - {OrderValidationErrors.ORDER_IS_REDUCE_ONLY}')
        except ValidationError as e:
            self.assertEqual(e.message, OrderValidationErrors.ORDER_IS_REDUCE_ONLY)

    def test_when_stop_is_not_reduce_only_validation_error(self):
        try:
            OrderFactory(order__status='FILLED', stop__reduce_only=False)
            self.fail(f'Should have raised ValidationError - {OrderValidationErrors.STOP_IS_NOT_REDUCE_ONLY}')
        except ValidationError as e:
            self.assertEqual(e.message, OrderValidationErrors.STOP_IS_NOT_REDUCE_ONLY)

    def test_when_stop_side_is_the_same_as_order_side_validation_error(self):
        try:
            side = 'BUY'
            OrderFactory(indicator__type=side, order__status='FILLED', stop__side=side)
            self.fail(f'Should have raised ValidationError - {OrderValidationErrors.STOP_SIDE_IS_THE_SAME_AS_ORDER_SIDE}')
        except ValidationError as e:
            self.assertEqual(e.message, OrderValidationErrors.STOP_SIDE_IS_THE_SAME_AS_ORDER_SIDE)

    def test_order_algo_order_unique_enforced(self):
        indicator = TimeframeKlineSignalFactory(type='BUY')
        algo_order = WooAlgoOrderFactory(side='BUY')
        order = OrderFactory(indicator=indicator, order=algo_order, stop=None)
        self.assertEqual(order.order, algo_order)
        self.assertEqual(order.indicator, indicator)
        try:
            order2 = OrderFactory.build(indicator=indicator, order=algo_order, stop=None)
            order2.save()
            self.fail('Should have raised IntegrityError')
        except IntegrityError as e:
            self.assertNotEqual(e.args[0].find('duplicate key value violates unique constraint'), -1)

    def test_order_stop_order_unique_enforced(self):
        indicator = TimeframeKlineSignalFactory(type='BUY')
        algo_order = WooAlgoOrderFactory(side='BUY', status='FILLED')
        stop_order = WooAlgoOrderFactory(side='SELL', reduce_only=True)
        order = OrderFactory(indicator=indicator, order=algo_order, stop=stop_order)
        self.assertEqual(order.order, algo_order)
        self.assertEqual(order.stop, stop_order)
        self.assertEqual(order.indicator, indicator)
        try:
            algo_order2 = WooAlgoOrderFactory(side='BUY', status='FILLED')
            order2 = OrderFactory.build(indicator=indicator, order=algo_order2, stop=stop_order)
            order2.save()
            self.fail('Should have raised IntegrityError')
        except IntegrityError as e:
            self.assertNotEqual(e.args[0].find('duplicate key value violates unique constraint'), -1)


class OrderManagerTests(TestCase):

    def test_get_pending_orders(self):
        self.assertEqual(Order.objects.get_pending_orders().count(), 0)
        OrderFactory(order__status='NEW')
        self.assertEqual(Order.objects.get_pending_orders().count(), 1)
        OrderFactory(order__status='NEW')
        self.assertEqual(Order.objects.get_pending_orders().count(), 2)
        OrderFactory(order__status='FILLED')
        self.assertEqual(Order.objects.get_pending_orders().count(), 2)
        OrderFactory(order__status='NEW')
        self.assertEqual(Order.objects.get_pending_orders().count(), 3)
        OrderFactory(order__status='CANCELLED')
        self.assertEqual(Order.objects.get_pending_orders().count(), 3)

    def test_get_last_pending_order(self):
        self.assertIsNone(Order.objects.get_last_pending_order())
        order = OrderFactory(order__status='NEW')
        self.assertEqual(Order.objects.get_last_pending_order(), order)
        order2 = OrderFactory(order__status='FILLED')
        order3 = OrderFactory(order__status='NEW')
        self.assertEqual(Order.objects.get_last_pending_order(), order3)
        order4 = OrderFactory(order__status='NEW')
        self.assertEqual(Order.objects.get_last_pending_order(), order4)
        order3.delete()
        self.assertEqual(Order.objects.get_last_pending_order(), order4)
        order4.delete()
        self.assertEqual(Order.objects.get_last_pending_order(), order)
        order.delete()
        self.assertIsNone(Order.objects.get_last_pending_order())

    def test_get_last_pending_order_for_side(self):
        self.assertIsNone(Order.objects.get_last_pending_order_for_side('BUY'))
        order = OrderFactory(order__status='NEW', indicator__type='BUY')
        self.assertEqual(Order.objects.get_last_pending_order_for_side('BUY'), order)
        self.assertIsNone(Order.objects.get_last_pending_order_for_side('SELL'))
        order2 = OrderFactory(order__status='FILLED', indicator__type='BUY')
        order3 = OrderFactory(order__status='NEW', indicator__type='SELL')
        self.assertEqual(Order.objects.get_last_pending_order_for_side('SELL'), order3)
        self.assertEqual(Order.objects.get_last_pending_order_for_side('BUY'), order)
        order4 = OrderFactory(order__status='NEW', indicator__type='BUY')
        self.assertNotEquals(Order.objects.get_last_pending_order_for_side('BUY'), order)
        self.assertEqual(Order.objects.get_last_pending_order_for_side('BUY'), order4)
        order4.delete()
        self.assertEqual(Order.objects.get_last_pending_order_for_side('BUY'), order)

    def test_get_active_orders(self):
        self.assertEqual(Order.objects.get_active_orders().count(), 0)
        OrderFactory(order__status='NEW')
        self.assertEqual(Order.objects.get_active_orders().count(), 0)
        OrderFactory(order__status='NEW')
        self.assertEqual(Order.objects.get_active_orders().count(), 0)
        OrderFactory(order__status='FILLED')
        self.assertEqual(Order.objects.get_active_orders().count(), 1)
        OrderFactory(order__status='NEW')
        self.assertEqual(Order.objects.get_active_orders().count(), 1)
        OrderFactory(order__status='CANCELLED')
        self.assertEqual(Order.objects.get_active_orders().count(), 1)

    def test_get_last_active_order(self):
        self.assertIsNone(Order.objects.get_last_active_order())
        order = OrderFactory(order__status='FILLED')
        self.assertEqual(Order.objects.get_last_active_order(), order)
        order2 = OrderFactory(order__status='NEW')
        order3 = OrderFactory(order__status='FILLED')
        self.assertEqual(Order.objects.get_last_active_order(), order3)
        order4 = OrderFactory(order__status='FILLED')
        self.assertEqual(Order.objects.get_last_active_order(), order4)
        order3.delete()
        self.assertEqual(Order.objects.get_last_active_order(), order4)
        order4.delete()
        self.assertEqual(Order.objects.get_last_active_order(), order)
        order.delete()
        self.assertIsNone(Order.objects.get_last_active_order())

    def test_get_last_active_order_by_side(self):
        self.assertIsNone(Order.objects.get_last_active_order_for_side('BUY'))
        order = OrderFactory(order__status='FILLED', indicator__type='BUY')
        self.assertEqual(Order.objects.get_last_active_order_for_side('BUY'), order)
        self.assertIsNone(Order.objects.get_last_active_order_for_side('SELL'))
        order2 = OrderFactory(order__status='NEW', indicator__type='BUY')
        order3 = OrderFactory(order__status='FILLED', indicator__type='SELL')
        self.assertEqual(Order.objects.get_last_active_order_for_side('SELL'), order3)
        self.assertEqual(Order.objects.get_last_active_order_for_side('BUY'), order)
        order4 = OrderFactory(order__status='FILLED', indicator__type='BUY')
        self.assertNotEquals(Order.objects.get_last_active_order_for_side('BUY'), order)
        self.assertEqual(Order.objects.get_last_active_order_for_side('BUY'), order4)
        order4.delete()
        self.assertEqual(Order.objects.get_last_active_order_for_side('BUY'), order)

    def test_get_last_order(self):
        self.assertIsNone(Order.objects.get_last_order())
        order = OrderFactory()
        self.assertEqual(Order.objects.get_last_order(), order)
        order2 = OrderFactory()
        self.assertEqual(Order.objects.get_last_order(), order2)
        order3 = OrderFactory()
        self.assertEqual(Order.objects.get_last_order(), order3)
        order2.delete()
        self.assertEqual(Order.objects.get_last_order(), order3)
        order3.delete()
        self.assertEqual(Order.objects.get_last_order(), order)
        order.delete()
        self.assertIsNone(Order.objects.get_last_order())

    def test_get_last_order_for_side(self):
        self.assertIsNone(Order.objects.get_last_order_for_side('BUY'))
        order = OrderFactory(indicator__type='BUY')
        self.assertEqual(Order.objects.get_last_order_for_side('BUY'), order)
        self.assertIsNone(Order.objects.get_last_order_for_side('SELL'))
        order2 = OrderFactory(indicator__type='SELL')
        self.assertEqual(Order.objects.get_last_order_for_side('SELL'), order2)
        self.assertEqual(Order.objects.get_last_order_for_side('BUY'), order)
        order3 = OrderFactory(indicator__type='BUY')
        self.assertNotEquals(Order.objects.get_last_order_for_side('BUY'), order)
        self.assertEqual(Order.objects.get_last_order_for_side('BUY'), order3)
        order3.delete()
        self.assertEqual(Order.objects.get_last_order_for_side('BUY'), order)

    def test_get_order_by_order_id(self):
        order_id = 7654321
        self.assertIsNone(Order.objects.get_order_by_order_id(order_id))
        order = OrderFactory(order__order_id=order_id)
        self.assertEqual(Order.objects.get_order_by_order_id(order_id), order)
        stop_order_id = 1234567
        stop_order = WooAlgoOrderFactory(order_id=stop_order_id, side=['BUY', 'SELL'][order.side == 'BUY'], reduce_only=True)
        self.assertEqual(stop_order.order_id, stop_order_id)
        self.assertIsNone(Order.objects.get_order_by_order_id(stop_order_id))
        order.order.status = 'FILLED'
        order.order.save()
        order.stop = stop_order
        order.save()
        self.assertEqual(Order.objects.get_order_by_order_id(stop_order_id), order)

    def test_get_all_pending_reduce_only_orders_for_side(self):
        OrderFactory.create_batch(3, order__status='NEW', indicator__type='BUY')
        OrderFactory.create_batch(2, order__status='NEW', indicator__type='SELL')
        OrderFactory.create_batch(4, order__status='FILLED', indicator__type='BUY')
        OrderFactory.create_batch(5, order__status='FILLED', indicator__type='SELL')
        OrderFactory.create_batch(6, order__status='CANCELLED', indicator__type='BUY')
        OrderFactory.create_batch(7, order__status='CANCELLED', indicator__type='SELL')
        self.assertEqual(Order.objects.count(), 27)
        self.assertEqual(Order.objects.get_all_pending_reduce_only_orders_for_side('BUY').count(), 5)
        self.assertEqual(Order.objects.get_all_pending_reduce_only_orders_for_side('SELL').count(), 4)

    def test_get_all_pending_non_reduce_only_orders_for_side(self):
        OrderFactory.create_batch(3, order__status='NEW', indicator__type='BUY')
        OrderFactory.create_batch(2, order__status='NEW', indicator__type='SELL')
        OrderFactory.create_batch(4, order__status='FILLED', indicator__type='BUY')
        OrderFactory.create_batch(5, order__status='FILLED', indicator__type='SELL')
        OrderFactory.create_batch(6, order__status='CANCELLED', indicator__type='BUY')
        OrderFactory.create_batch(7, order__status='CANCELLED', indicator__type='SELL')
        self.assertEqual(Order.objects.count(), 27)
        self.assertEqual(Order.objects.get_all_pending_non_reduce_only_orders_for_side('BUY').count(), 3)
        self.assertEqual(Order.objects.get_all_pending_non_reduce_only_orders_for_side('SELL').count(), 2)
