import time
from datetime import datetime, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils.timezone import make_aware

from common.util.cls import map_data_to_class
from us.tests.factory.timeframe_group_factory import TimeframeGroupFactory
from us.tests.factory.timeframe_kline_signal_factory import TimeframeKlineSignalFactory
from us_orders.models.order import Order
from us_orders.models.order_group import OrderGroup
from us_orders.tests.factory.order_factory import OrderFactory
from us_orders.tests.factory.order_group_factory import OrderGroupFactory
from us_orders.tests.helpers import create_order_for_test, get_expected_params_for_reduce_only_order, MockResponse, \
    get_count_of_stop_orders_on_side_with_status, get_count_of_orders_on_side_with_status
from us_orders.helpers import get_opposite_side_to_order, get_trigger_price_for_stop_order, \
    get_or_create_latest_order_group_for_side, is_order_group_allowing_orders, remove_none_values_from_dict, create_order, \
    create_stop_for_order, \
    cancel_all_pending_stop_orders_for_side, cancel_all_pending_orders_for_side, cancel_pending_order_group_stop, \
    update_or_cancel_order_group_stop
from us_orders.tests.mock_data.algo_order_mock import get_mock_algo_order_data
from us_orders.tests.mock_data.send_algo_order_return_mock import send_algo_order_return_mock

from woo.api_types import OrderSide, AlgoOrderStatus
from woo.models import WooAlgoOrder
from woo.tests.factory.woo_algo_order_factory import WooAlgoOrderFactory
from woo.tests.mock_data.algo_order_mock import cancel_sent_success_response, edit_sent_success_response


class HelpersTests(TestCase):

    def setUp(self):
        self.patcher = patch('requests.request')
        self.mock_request = self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_remove_none_values_from_dict(self):
        d = {
            'a': 1,
            'b': None,
            'c': 2,
            'd': None,
            'e': 3,
            'f': None,
        }
        expected = {
            'a': 1,
            'c': 2,
            'e': 3,
        }
        self.assertEqual(remove_none_values_from_dict(d), expected)

    def test_get_opposite_side_to_order(self):
        buy_order = OrderFactory(direction=OrderSide.BUY.value)
        self.assertEqual(get_opposite_side_to_order(buy_order), OrderSide.SELL)
        sell_order = OrderFactory(direction=OrderSide.SELL.value)
        self.assertEqual(get_opposite_side_to_order(sell_order), OrderSide.BUY)

    def test_get_trigger_price_for_stop_order__when_order_is_BUY(self):
        trigger_price = 10000.0
        stop_loss_difference = 200.0
        quantity = 0.3
        order, _ = create_order_for_test(OrderSide.BUY, trigger_price, stop_loss_difference, quantity=quantity)
        self.assertEqual(get_trigger_price_for_stop_order(order), trigger_price - stop_loss_difference)

    def test_get_trigger_price_for_stop_order__when_order_is_BUY_and_has_trigger_trade_price_set(self):
        trigger_price = 10000.0
        trigger_trade_price = 10050.0
        stop_loss_difference = 200.0
        quantity = 0.3
        order, _ = create_order_for_test(
            OrderSide.BUY,
            trigger_price,
            stop_loss_difference,
            quantity=quantity,
            trigger_trade_price=trigger_trade_price
        )
        self.assertEqual(get_trigger_price_for_stop_order(order), trigger_trade_price - stop_loss_difference)

    def test_get_trigger_price_for_stop_order__when_order_is_SELL(self):
        trigger_price = 10000.0
        stop_loss_difference = 200.0
        quantity = 0.3
        order, _ = create_order_for_test(OrderSide.SELL, trigger_price, stop_loss_difference, quantity=quantity)
        self.assertEqual(get_trigger_price_for_stop_order(order), trigger_price + stop_loss_difference)

    def test_get_trigger_price_for_stop_order__when_order_is_SELL_and_has_trigger_trade_price_set(self):
        trigger_price = 10000.0
        trigger_trade_price = 10050.0
        stop_loss_difference = 200.0
        quantity = 0.3
        order, _ = create_order_for_test(
            OrderSide.SELL,
            trigger_price,
            stop_loss_difference,
            quantity=quantity,
            trigger_trade_price=trigger_trade_price
        )
        self.assertEqual(get_trigger_price_for_stop_order(order), trigger_trade_price + stop_loss_difference)

    def test_get_or_create_latest_order_group_for_side__when_order_group_does_not_exist_should_create_new_group(self):
        tf_group = TimeframeGroupFactory()
        self.assertEqual(len(OrderGroup.objects.all()), 0)
        order_group = get_or_create_latest_order_group_for_side(OrderSide.BUY.value, tf_group.pk)
        self.assertEqual(len(OrderGroup.objects.all()), 1)
        self.assertEqual(order_group.group_id, tf_group.pk)
        self.assertEqual(order_group.side, OrderSide.BUY.value)

    def test_get_or_create_latest_order_group_for_side__when_lasted_order_group_for_side_is_closed(self):
        quantity = 0.1
        order_count = 2
        tf_group = TimeframeGroupFactory()
        stop_order = WooAlgoOrderFactory(side='SELL', reduce_only=True, quantity=quantity * order_count)
        closed_order_group = OrderGroupFactory(
            group=tf_group,
            side='BUY',
            orders__count=order_count,
            orders__order__status='FILLED',
            orders__order__quantity=quantity,
            stop=stop_order
        )
        stop_order.status = AlgoOrderStatus.FILLED.value
        stop_order.save()
        self.assertTrue(closed_order_group.is_closed)
        self.assertEqual(len(OrderGroup.objects.all()), 1)
        order_group = get_or_create_latest_order_group_for_side(OrderSide.BUY.value, tf_group.pk)
        self.assertEqual(len(OrderGroup.objects.all()), 2)
        self.assertEqual(order_group.group_id, tf_group.pk)
        self.assertEqual(order_group.side, OrderSide.BUY.value)
        self.assertNotEquals(order_group.pk, closed_order_group.pk)

    def test_get_or_create_latest_order_group_for_side__when_order_group_exists(self):
        side = OrderSide.BUY.value
        order_group = OrderGroupFactory(side=side)
        self.assertEqual(len(OrderGroup.objects.all()), 1)
        res = get_or_create_latest_order_group_for_side(OrderSide.BUY.value, order_group.group.pk)
        self.assertEqual(order_group, res)

    def test_is_order_group_allowing_orders__when_order_group_has_not_exceeded_allowed_minutes_since_last_filled_order(self):
        minimum_minutes_since_last_order = 5
        order_group = OrderGroupFactory(
            group__strategy_variables__minimum_minutes_since_last_order=minimum_minutes_since_last_order,
            orders__order__status='FILLED',
            orders__order__trigger_time=time.time()
        )
        self.assertIsNotNone(order_group.orders.first().order.trigger_time)
        self.assertFalse(order_group.has_exceeded_allowed_minutes_since_last_filled_order)
        self.assertFalse(is_order_group_allowing_orders(order_group))

    def test_is_order_group_allowing_orders__when_order_group_has_exceeded_allowed_minutes_since_last_filled_order(self):
        minimum_minutes_since_last_order = 5
        order_group = OrderGroupFactory(
            group__strategy_variables__minimum_minutes_since_last_order=minimum_minutes_since_last_order,
            orders__order__status='FILLED',
            orders__order__trigger_time=time.time() - ((minimum_minutes_since_last_order + 5) * 60)
        )
        self.assertIsNotNone(order_group.orders.first().order.trigger_time)
        self.assertTrue(order_group.has_exceeded_allowed_minutes_since_last_filled_order)
        self.assertFalse(order_group.has_reached_max_order_limit)
        self.assertTrue(is_order_group_allowing_orders(order_group))

    def test_is_order_group_allowing_orders__when_order_group_has_not_reached_max_order_limit(self):
        minimum_minutes_since_last_order = 5
        created_at = make_aware(
            datetime.today() - timedelta(minutes=minimum_minutes_since_last_order + 1)
        )
        with patch('django.utils.timezone.now', return_value=created_at):
            order_group = OrderGroupFactory(
                group__strategy_variables__minimum_minutes_since_last_order=minimum_minutes_since_last_order,
            )
            self.assertFalse(order_group.has_reached_max_order_limit)
            self.assertTrue(order_group.has_exceeded_allowed_minutes_since_last_filled_order)
            self.assertTrue(is_order_group_allowing_orders(order_group))

    def test_is_order_group_allowing_orders__when_order_group_has_reached_max_order_limit(self):
        minimum_minutes_since_last_order = 5
        max_active_orders = 2
        order_group = OrderGroupFactory(
            orders__count=max_active_orders,
            orders__order__status='FILLED',
            orders__order__trigger_time=time.time() - ((minimum_minutes_since_last_order + 5) * 60),
            group__strategy_variables__minimum_minutes_since_last_order=minimum_minutes_since_last_order,
            group__strategy_variables__max_active_orders=max_active_orders,
        )
        self.assertTrue(order_group.has_reached_max_order_limit)
        self.assertTrue(order_group.has_exceeded_allowed_minutes_since_last_filled_order)
        self.assertFalse(is_order_group_allowing_orders(order_group))

    def test_create_order(self):
        side = OrderSide.BUY
        signal = TimeframeKlineSignalFactory(direction=side.value)
        symbol = 'BTCUSDT'
        quantity = 0.1
        trigger_price = 10000.0

        self.mock_request.return_value = MockResponse(json_data=send_algo_order_return_mock(quantity=quantity))

        order = create_order(signal, symbol, side, quantity, trigger_price, 'meh')
        algo_order = order.order

        self.assertEqual(self.mock_request.call_count, 1)

        self.assertEqual(order.indicator, signal)
        self.assertEqual(algo_order.symbol, symbol)
        self.assertEqual(algo_order.side, side.value)
        self.assertEqual(algo_order.quantity, quantity)
        self.assertEqual(algo_order.trigger_price, trigger_price)
        self.assertEqual(algo_order.reduce_only, False)
        self.assertEqual(algo_order.order_tag, 'meh')

    def test_create_stop_for_order__with_buy_order(self):
        trigger_price = 10000.0
        stop_loss_difference = 200.0
        stop_side = OrderSide.SELL

        order, _ = create_order_for_test(OrderSide.BUY, trigger_price, stop_loss_difference, AlgoOrderStatus.FILLED)
        expected_params = get_expected_params_for_reduce_only_order(
            order.order.symbol,
            stop_side,
            order.quantity,
            '9800.0',
            f'stop-for-{order.order_id}'
        )

        self.mock_request.return_value = MockResponse(json_data=send_algo_order_return_mock(123))

        create_stop_for_order(order)

        request_json = self.mock_request.call_args.kwargs.get('json')
        stop_order = Order.objects.get_order_by_order_id(123)

        self.assertEqual(self.mock_request.call_count, 1)
        self.assertEqual(expected_params, request_json)
        self.assertEqual(stop_order, order)
        self.assertEqual(stop_order.stop, order.stop)

    def test_create_stop_for_order__with_sell_order(self):
        trigger_price = 10000.0
        stop_loss_difference = 200.0
        stop_side = OrderSide.BUY

        order, _ = create_order_for_test(OrderSide.SELL, trigger_price, stop_loss_difference, AlgoOrderStatus.FILLED)
        expected_params = get_expected_params_for_reduce_only_order(
            order.order.symbol,
            stop_side,
            order.quantity,
            '10200.0',
            f'stop-for-{order.order_id}'
        )

        self.mock_request.return_value = MockResponse(json_data=send_algo_order_return_mock(123))

        create_stop_for_order(order)

        request_json = self.mock_request.call_args.kwargs.get('json')
        stop_order = Order.objects.get_order_by_order_id(123)

        self.assertEqual(self.mock_request.call_count, 1)
        self.assertEqual(expected_params, request_json)
        self.assertEqual(stop_order, order)
        self.assertEqual(stop_order.stop, order.stop)

    def test_map_data_to_class__when_there_are_no_key_mappings(self):
        data = get_mock_algo_order_data()
        result_dict = map_data_to_class(WooAlgoOrder, data)
        self.assertIsNotNone(result_dict)
        self.assertEqual(len(result_dict), 17)

    def test_map_data_to_class__when_there_are_key_mappings(self):
        data = get_mock_algo_order_data()
        result_dict = map_data_to_class(WooAlgoOrder, data, {'algoStatus': 'status', 'createdTime': 'create_time'})

        self.assertIsNotNone(data.get('algoStatus'))
        self.assertIsNone(data.get('status'))
        self.assertIsNotNone(data.get('createdTime'))
        self.assertIsNone(data.get('create_time'))

        self.assertIsNotNone(result_dict)
        self.assertEqual(len(result_dict), 19)

        self.assertIsNone(result_dict.get('algoStatus'))
        self.assertIsNotNone(result_dict.get('status'))
        self.assertIsNone(result_dict.get('createdTime'))
        self.assertIsNotNone(result_dict.get('create_time'))

    def test_map_data_to_class__when_there_is_a_value_converter(self):

        def value_converter(key, value):
            if key == 'trigger_time':
                return value / 1000
            return value

        data = get_mock_algo_order_data()
        result_dict = map_data_to_class(
            WooAlgoOrder,
            data,
            value_converter=value_converter
        )

        self.assertEqual(data['triggerTime'], 1699477397398)

        self.assertIsNotNone(result_dict)
        self.assertEqual(len(result_dict), 17)

        self.assertEqual(result_dict['trigger_time'], 1699477397.398)

    def test_cancel_all_pending_stop_orders_for_side(self):
        OrderFactory.create_batch(4, indicator__type='BUY', order__status='FILLED')
        OrderFactory.create_batch(3, indicator__type='SELL', order__status='FILLED')

        self.assertEqual(len(Order.objects.all()), 7)

        self.mock_request.return_value = MockResponse(json_data=cancel_sent_success_response)

        self.assertEqual(get_count_of_stop_orders_on_side_with_status(OrderSide.SELL, AlgoOrderStatus.CANCELLED), 0)

        cancel_all_pending_stop_orders_for_side('SELL')

        self.assertEqual(self.mock_request.call_count, 4)
        self.assertEqual(get_count_of_stop_orders_on_side_with_status(OrderSide.SELL, AlgoOrderStatus.CANCELLED), 4)

        self.assertEqual(get_count_of_stop_orders_on_side_with_status(OrderSide.BUY, AlgoOrderStatus.CANCELLED), 0)

        cancel_all_pending_stop_orders_for_side('BUY')

        self.assertEqual(self.mock_request.call_count, 7)
        self.assertEqual(get_count_of_stop_orders_on_side_with_status(OrderSide.BUY, AlgoOrderStatus.CANCELLED), 3)

    def test_cancel_all_pending_orders_for_side(self):
        OrderFactory.create_batch(4, indicator__type='BUY')
        OrderFactory.create_batch(3, indicator__type='SELL')

        self.assertEqual(len(Order.objects.all()), 7)

        self.mock_request.return_value = MockResponse(json_data=cancel_sent_success_response)

        self.assertEqual(get_count_of_orders_on_side_with_status(OrderSide.BUY, AlgoOrderStatus.CANCELLED), 0)

        cancel_all_pending_orders_for_side('BUY')

        self.assertEqual(self.mock_request.call_count, 4)
        self.assertEqual(get_count_of_orders_on_side_with_status(OrderSide.BUY, AlgoOrderStatus.CANCELLED), 4)

        self.assertEqual(get_count_of_orders_on_side_with_status(OrderSide.SELL, AlgoOrderStatus.CANCELLED), 0)

        cancel_all_pending_orders_for_side('SELL')

        self.assertEqual(self.mock_request.call_count, 7)
        self.assertEqual(get_count_of_orders_on_side_with_status(OrderSide.SELL, AlgoOrderStatus.CANCELLED), 3)

    def test_cancel_pending_order_group_stop(self):
        order_group = OrderGroupFactory(orders__order__status='FILLED')
        stop = WooAlgoOrderFactory(side=['SELL', 'BUY'][order_group.side == 'SELL'], reduce_only=True)
        order_group.set_stop(stop)
        self.assertEqual(order_group.stop, stop)
        self.mock_request.return_value = MockResponse(json_data=cancel_sent_success_response)
        cancel_pending_order_group_stop(order_group)
        self.assertEqual(self.mock_request.call_count, 1)
        self.assertEqual(order_group.stop.status, AlgoOrderStatus.CANCELLED)

    def test_update_or_cancel_order_group_stop(self):
        count = 2
        quantity = 2
        order_group = OrderGroupFactory(
            orders__with_matching_stop=True,
            orders__order__status='FILLED',
            orders__count=count,
            orders__order__quantity=quantity
        )
        stop = WooAlgoOrderFactory(
            side=['SELL', 'BUY'][order_group.side == 'SELL'],
            reduce_only=True,
            quantity=quantity * count
        )
        order_group.set_stop(stop)
        self.assertEqual(order_group.stop, stop)
        self.assertEqual(stop.quantity, order_group.quantity)
        self.assertEqual(order_group.quantity, 4)
        self.mock_request.side_effect = [
            MockResponse(json_data=edit_sent_success_response),
            MockResponse(json_data=cancel_sent_success_response)
        ]
        order = order_group.orders.first()
        order.stop.update(status=AlgoOrderStatus.FILLED.value)
        self.assertEqual(order_group.quantity, 2)
        update_or_cancel_order_group_stop(order_group)
        self.assertEqual(self.mock_request.call_count, 1)
        self.assertIsNotNone(order_group.stop)

        order2 = order_group.orders.last()
        order2.stop.update(status=AlgoOrderStatus.FILLED.value)
        self.assertEqual(order_group.quantity, 0)
        update_or_cancel_order_group_stop(order_group)
        self.assertEqual(self.mock_request.call_count, 2)
        self.assertIsNone(order_group.stop)
