from datetime import datetime, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils.timezone import make_aware

from us.tests.factory.timeframe_group_factory import TimeframeGroupFactory
from us.tests.factory.timeframe_kline_signal_factory import TimeframeKlineSignalFactory
from us_orders.flows.new_order_flow import create_or_update_stop_order_for_group, handle_new_signal, \
    create_or_update_order
from us_orders.models.order import Order
from us_orders.models.order_group import OrderGroup
from us_orders.tests.factory.order_factory import OrderFactory
from us_orders.tests.factory.order_group_factory import OrderGroupFactory
from us_orders.tests.helpers import MockResponse, create_order_for_test
from us_orders.tests.mock_data.send_algo_order_return_mock import send_algo_order_return_mock
from woo.api_types import OrderSide, AlgoOrderStatus
from woo.tests.factory.woo_algo_order_factory import WooAlgoOrderFactory
from woo.tests.mock_data.algo_order_mock import edit_sent_success_response


class NewOrderFlowTests(TestCase):

    def setUp(self):
        self.patcher = patch('requests.request')
        self.mock_request = self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_handle_new_signal__when_no_order_groups(self):
        signal = TimeframeKlineSignalFactory(direction=OrderSide.BUY.value)
        tf_group = TimeframeGroupFactory()
        strategy_vars = tf_group.strategy_variables

        self.mock_request.return_value = MockResponse(json_data=send_algo_order_return_mock(
            123
        ))

        handle_new_signal(tf_group.id, signal, strategy_vars)

        self.assertEqual(OrderGroup.objects.count(), 1)
        self.assertEqual(Order.objects.count(), 1)

        order_group = OrderGroup.objects.first()

        self.assertFalse(order_group.is_active)
        self.assertEqual(order_group.group.id, tf_group.id)
        self.assertEqual(order_group.side, OrderSide.BUY.value)

    def test_handle_new_signal__when_new_order_is_added_to_active_group(self):
        side = OrderSide.BUY.value
        minimum_minutes_since_last_order = 5
        created_at = make_aware(
            datetime.today() - timedelta(minutes=minimum_minutes_since_last_order + 1)
        )
        with patch('django.utils.timezone.now', return_value=created_at):
            order_group = OrderGroupFactory(
                side=side,
                orders__order__status=AlgoOrderStatus.FILLED,
                orders__with_matching_stop=True,
                group__strategy_variables__minimum_minutes_since_last_order=minimum_minutes_since_last_order,
            )
            signal = TimeframeKlineSignalFactory(direction=side)
            tf_group = order_group.group
            strategy_vars = tf_group.strategy_variables

            self.mock_request.return_value = MockResponse(json_data=send_algo_order_return_mock(
                123
            ))

            handle_new_signal(tf_group.id, signal, strategy_vars)

            self.assertEqual(OrderGroup.objects.count(), 1)
            self.assertEqual(Order.objects.count(), 2)
            self.assertTrue(order_group.is_active)
            self.assertEqual(order_group.group.id, tf_group.id)
            self.assertEqual(order_group.side, OrderSide.BUY.value)

    def test_handle_new_signal__when_no_order_group_exists_for_side(self):
        quantity = 90
        order_group = OrderGroupFactory(
            side=OrderSide.BUY.value,
            orders__order__status=AlgoOrderStatus.FILLED,
            orders__order__quantity=quantity,
        )
        signal = TimeframeKlineSignalFactory(direction=OrderSide.SELL.value)
        tf_group = order_group.group
        strategy_vars = tf_group.strategy_variables

        self.mock_request.side_effect = [
            MockResponse(json_data=send_algo_order_return_mock(456, quantity=order_group.quantity)),
            MockResponse(json_data=send_algo_order_return_mock(123))
        ]

        self.assertEqual(OrderGroup.objects.count(), 1)
        self.assertEqual(Order.objects.count(), 1)
        self.assertIsNone(OrderGroup.objects.get_latest_group_for_side(OrderSide.SELL.value))
        self.assertIsNone(order_group.stop)
        self.assertEqual(order_group.quantity, quantity)

        handle_new_signal(tf_group.id, signal, strategy_vars)

        order_group.refresh_from_db()

        sell_order_group = OrderGroup.objects.get_latest_group_for_side(OrderSide.SELL.value)
        sell_order = sell_order_group.orders.first()

        self.assertEqual(OrderGroup.objects.count(), 2)
        self.assertEqual(Order.objects.count(), 2)
        self.assertIsNotNone(order_group.stop)
        self.assertIsNotNone(sell_order_group)
        self.assertIsNone(sell_order_group.stop)
        self.assertIsNotNone(sell_order)
        self.assertEqual(sell_order.status, AlgoOrderStatus.NEW)

    def test_create_or_update_order__when_the_group_has_an_existing_pending_order(self):
        trigger_price = 23000.0
        order_group = OrderGroupFactory(
            side=OrderSide.BUY.value,
            orders__order__trigger_price=trigger_price
        )
        order = order_group.orders.first()
        group = order_group.group
        signal = order.indicator

        self.assertTrue(order_group.current_pending_order, order)
        self.assertEqual(order.order.trigger_price, trigger_price)

        self.mock_request.return_value = MockResponse(json_data=edit_sent_success_response)

        pending_order, created = create_or_update_order(
            signal,
            group.strategy_variables,
            order_group.id,
            order_group.current_pending_order
        )

        order.refresh_from_db()
        self.assertTrue(self.mock_request.called)
        self.assertNotEquals(order.order.trigger_price, trigger_price)
        self.assertIsNotNone(pending_order)
        self.assertFalse(created)

    def test_create_or_update_order__when_the_group_has_no_existing_pending_order(self):
        side = OrderSide.BUY.value
        signal = TimeframeKlineSignalFactory(direction=side)
        order_group = OrderGroupFactory(
            side=OrderSide.BUY.value,
            orders=[]
        )
        group = order_group.group

        self.assertIsNone(order_group.current_pending_order)

        self.mock_request.return_value = MockResponse(
            json_data=send_algo_order_return_mock(
                quantity=order_group.quantity
            )
        )

        pending_order, created = create_or_update_order(
            signal,
            group.strategy_variables,
            order_group.id,
            order_group.current_pending_order
        )

        self.assertIsNotNone(pending_order)
        self.assertTrue(created)

    def test_create_or_update_stop_order_for_group__when_group_does_not_contain_order(self):
        order_group = OrderGroupFactory(side=OrderSide.BUY.value)
        order = OrderFactory(indicator__type=OrderSide.BUY.value)
        try:
            create_or_update_stop_order_for_group(order_group, order.indicator, order_group.group.strategy_variables)
            self.fail('Should have raised an exception')
        except Exception as e:
            self.assertEqual(str(e), 'Order must be on the opposite side to the group')

    def test_create_or_update_stop_order_for_group__when_order_group_has_stop(self):
        trigger_price = 10000.0
        stop_loss_difference = 200.0
        quantity = 0.3
        order, order_group = create_order_for_test(
            OrderSide.BUY,
            trigger_price,
            stop_loss_difference,
            quantity=quantity,
            status=AlgoOrderStatus.FILLED
        )
        order_group.set_stop(WooAlgoOrderFactory(
            side=OrderSide.SELL.value,
            reduce_only=True,
            quantity=quantity,
            trigger_price=trigger_price
        ))

        order2 = OrderFactory(indicator__type=OrderSide.SELL.value)

        self.assertTrue(order_group.has_stop)
        self.assertEqual(order_group.stop.trigger_price, trigger_price)

        self.mock_request.return_value = MockResponse(json_data=edit_sent_success_response)

        stop, created = create_or_update_stop_order_for_group(
            order_group,
            order2.indicator,
            order_group.group.strategy_variables
        )

        self.assertTrue(self.mock_request.called)
        self.assertIsNotNone(stop)
        self.assertFalse(created)

    def test_create_or_update_stop_order_for_group__when_order_group_does_not_have_stop(self):
        trigger_price = 10000.0
        stop_loss_difference = 200.0
        quantity = 0.3
        order, order_group = create_order_for_test(
            OrderSide.BUY,
            trigger_price,
            stop_loss_difference,
            quantity=quantity,
            status=AlgoOrderStatus.FILLED
        )

        new_trigger_price = 9000.0
        order2 = OrderFactory(
            indicator__type=OrderSide.SELL.value,
            order__trigger_price=new_trigger_price
        )

        self.assertFalse(order_group.has_stop)
        self.assertEqual(order_group.quantity, quantity)

        self.mock_request.return_value = MockResponse(json_data=send_algo_order_return_mock(quantity=order_group.quantity))

        stop, created = create_or_update_stop_order_for_group(
            order_group,
            order2.indicator,
            order_group.group.strategy_variables
        )

        self.assertTrue(self.mock_request.called)
        self.assertIsNotNone(stop)
        self.assertTrue(created)
        self.assertEqual(stop.quantity, quantity)
