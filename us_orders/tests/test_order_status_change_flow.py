from unittest.mock import patch

from django.test import TestCase

from us_orders.flows.order_status_change_flow import get_new_status, handle_algo_order_update, create_stop_for_order, \
    handle_filled_reduce_only_order_update, handle_filled_non_reduce_only_order_update, \
    handle_filled_stop_for_order_group, handle_filled_stop_for_individual_order

from us_orders.tests.factory.order_factory import OrderFactory
from us_orders.tests.factory.order_group_factory import OrderGroupFactory
from us_orders.tests.helpers import MockResponse
from us_orders.tests.mock_data.algo_order_mock import get_mock_algo_order_data
from us_orders.tests.mock_data.send_algo_order_return_mock import send_algo_order_return_mock
from woo.api_types import AlgoOrderStatus, OrderSide
from woo.tests.factory.woo_algo_order_factory import WooAlgoOrderFactory
from woo.tests.mock_data.algo_order_mock import cancel_sent_success_response, edit_sent_success_response


class OrderStatusChangeFlowTests(TestCase):

    def test_get_new_status__when_no_algoOrderId_in_data(self):
        self.assertIsNone(get_new_status({}))

    def test_get_new_status__when_no_order_in_db_with_matching_order_id(self):
        data = get_mock_algo_order_data()
        self.assertIsNone(get_new_status(data))

    def test_get_new_status__when_order_status_has_not_changed(self):
        data = get_mock_algo_order_data(status=AlgoOrderStatus.NEW)
        order = WooAlgoOrderFactory(order_id=data.get('algoOrderId'))
        self.assertEqual(order.status, AlgoOrderStatus.NEW)
        self.assertIsNone(get_new_status(data))

    def test_get_new_status__when_order_status_has_changed_to_FILLED(self):
        data = get_mock_algo_order_data(status=AlgoOrderStatus.FILLED)
        order = WooAlgoOrderFactory(order_id=data.get('algoOrderId'))
        self.assertEqual(order.status, AlgoOrderStatus.NEW)
        self.assertEqual(get_new_status(data), AlgoOrderStatus.FILLED)
        order.refresh_from_db()
        self.assertEqual(order.status, AlgoOrderStatus.FILLED)

    def test_get_new_status__when_order_status_has_changed_to_CANCELLED(self):
        data = get_mock_algo_order_data(status=AlgoOrderStatus.CANCELLED)
        order = WooAlgoOrderFactory(order_id=data.get('algoOrderId'))
        self.assertEqual(order.status, AlgoOrderStatus.NEW)
        self.assertEqual(get_new_status(data), AlgoOrderStatus.CANCELLED)
        order.refresh_from_db()
        self.assertEqual(order.status, AlgoOrderStatus.CANCELLED)

    def test_get_new_status__when_order_status_has_changed_to_REJECTED(self):
        data = get_mock_algo_order_data(status=AlgoOrderStatus.REJECTED)
        order = WooAlgoOrderFactory(order_id=data.get('algoOrderId'))
        self.assertEqual(order.status, AlgoOrderStatus.NEW)
        self.assertEqual(get_new_status(data), AlgoOrderStatus.REJECTED)
        order.refresh_from_db()
        self.assertEqual(order.status, AlgoOrderStatus.REJECTED)

    def test_get_new_status__when_order_status_has_changed_to_REPLACED(self):
        data = get_mock_algo_order_data(status=AlgoOrderStatus.REPLACED)
        order = WooAlgoOrderFactory(order_id=data.get('algoOrderId'))
        self.assertEqual(order.status, AlgoOrderStatus.NEW)
        self.assertEqual(get_new_status(data), None)
        order.refresh_from_db()
        self.assertEqual(order.status, AlgoOrderStatus.NEW)

    def test_get_new_status__when_order_status_is_the_same_but_order_values_have_changed(self):
        data = get_mock_algo_order_data(status=AlgoOrderStatus.NEW)
        order = WooAlgoOrderFactory(order_id=data.get('algoOrderId'))
        self.assertEqual(order.status, AlgoOrderStatus.NEW)
        self.assertNotEqual(order.quantity, data.get('quantity'))
        self.assertEqual(get_new_status(data), None)
        order.refresh_from_db()
        self.assertEqual(str(order.quantity), data.get('quantity'))

    ''' 3 tests to cover missing WOO status updated to FILLED fix '''
    def test_get_new_status__when_order_is_triggered_and_status_is_NEW(self):
        data = get_mock_algo_order_data(status=AlgoOrderStatus.NEW, is_triggered=True)
        order = WooAlgoOrderFactory(order_id=data.get('algoOrderId'))
        self.assertEqual(order.status, AlgoOrderStatus.NEW)
        self.assertEqual(get_new_status(data), AlgoOrderStatus.FILLED)
        order.refresh_from_db()
        self.assertEqual(order.status, AlgoOrderStatus.FILLED)

    def test_get_new_status__when_order_is_NEW_and_status_is_PARTIALLY_FILLED(self):
        data = get_mock_algo_order_data(status=AlgoOrderStatus.PARTIAL_FILLED, is_triggered=True)
        order = WooAlgoOrderFactory(order_id=data.get('algoOrderId'))
        self.assertEqual(order.status, AlgoOrderStatus.NEW)
        self.assertEqual(get_new_status(data), AlgoOrderStatus.FILLED)
        order.refresh_from_db()
        self.assertEqual(order.status, AlgoOrderStatus.FILLED)

    def test_get_new_status__when_order_is_FILLED_and_status_is_PARTIALLY_FILLED(self):
        data = get_mock_algo_order_data(status=AlgoOrderStatus.PARTIAL_FILLED, is_triggered=True)
        order = WooAlgoOrderFactory(order_id=data.get('algoOrderId'), status=AlgoOrderStatus.FILLED)
        self.assertEqual(order.status, AlgoOrderStatus.FILLED)
        self.assertEqual(get_new_status(data), None)
        order.refresh_from_db()
        self.assertEqual(order.status, AlgoOrderStatus.FILLED)

    def test_get_new_status__when_order_is_changed_to_FILLED_to_fix_issue(self):
        data = get_mock_algo_order_data(status=AlgoOrderStatus.NEW, is_triggered=True)
        order_id = data.get('algoOrderId')
        order = WooAlgoOrderFactory(order_id=order_id)
        self.assertEqual(order.status, AlgoOrderStatus.NEW)
        self.assertEqual(get_new_status(data), AlgoOrderStatus.FILLED)
        order.refresh_from_db()
        self.assertEqual(order.status, AlgoOrderStatus.FILLED)
        data = get_mock_algo_order_data(order_id=order_id, status=AlgoOrderStatus.PARTIAL_FILLED, is_triggered=True)
        self.assertEqual(get_new_status(data), None)
        order.refresh_from_db()
        self.assertEqual(order.status, AlgoOrderStatus.FILLED)
        data = get_mock_algo_order_data(order_id=order_id, status=AlgoOrderStatus.FILLED, is_triggered=True)
        self.assertEqual(get_new_status(data), None)
        order.refresh_from_db()
        self.assertEqual(order.status, AlgoOrderStatus.FILLED)

    #######################################################################################################

    def test_handle_algo_order_update__when_no_algoOrderId_in_data(self):
        self.assertIsNone(handle_algo_order_update({}))

    def test_handle_algo_order_update__when_no_status_change(self):
        data = get_mock_algo_order_data(status=AlgoOrderStatus.NEW)
        order = WooAlgoOrderFactory(order_id=data.get('algoOrderId'))
        self.assertEqual(order.status, AlgoOrderStatus.NEW)
        handle_algo_order_update(data)
        order.refresh_from_db()
        self.assertEqual(order.status, AlgoOrderStatus.NEW)

    def test_handle_algo_order_update__when_status_has_changed_to_filled(self):
        pass

    def test_handle_algo_order_update__when_status_has_changed_to_cancelled(self):
        pass

    def test_handle_algo_order_update__when_status_has_changed_to_rejected(self):
        pass

    def test_handle_filled_order__when_reduce_only_is_true(self):
        pass

    def test_handle_filled_order__when_reduce_only_is_false(self):
        pass

    def test_handle_cancelled_order(self):
        pass

    def test_handle_rejected_order(self):
        pass

    @patch('requests.request', return_value=None)
    def test_handle_filled_reduce_only_order_update__when_no_matching_order_exists(self, mock_request):
        order_id = 123
        handle_filled_reduce_only_order_update(order_id)
        self.assertFalse(mock_request.called)

    def test_handle_filled_reduce_only_order_update__when_order_id_matches_a_stop_for_an_individual_order(self):
        pass

    def test_handle_filled_reduce_only_order_update__when_order_id_matches_a_stop_for_a_group(self):
        pass

    @patch('requests.request', return_value=None)
    def test_handle_filled_non_reduce_only_order_update__when_no_matching_order_exists(self, mock_request):
        order_id = 123
        handle_filled_non_reduce_only_order_update(order_id)
        self.assertFalse(mock_request.called)

    @patch('requests.request', return_value=MockResponse(json_data=send_algo_order_return_mock(123)))
    def test_handle_filled_non_reduce_only_order_update(self, mock_requests):
        # HAPPY PATH
        # 1. Supplied order Id is for an individual order
        # OUTCOME
        # 1. a stop order is created for the order
        # - mock request to ensure it's been called
        # - check that the order has been updated with the stop order
        # 2. all pending orders are cancelled
        # - mock request to ensure it's been called
        # - this flow is completed by WS callback that cancels orders so no need to check for outcome
        pass

    def test_handle_stop_for_order(self):
        pass

    @patch('requests.request', return_value=None)
    def test_handle_filled_stop_for_individual_order__when_order_has_no_group(self, mock_request):
        order = OrderFactory()
        handle_filled_stop_for_individual_order(order)
        self.assertFalse(mock_request.called)

    def test_handle_filled_stop_for_individual_order__when_group_has_reached_max_consecutive_order_stops_limit(self):
        # test reverse logic once implemented
        pass

    @patch('requests.request', return_value=MockResponse(json_data=edit_sent_success_response))
    def test_handle_filled_stop_for_individual_order__when_group_quantity_is_greater_than_zero(self, mock_request):
        side = OrderSide.BUY
        quantity = 100.0
        orders = OrderFactory.create_batch(
            3,
            order__status=AlgoOrderStatus.FILLED,
            order__quantity=quantity,
            indicator__type=side
        )
        order_group = OrderGroupFactory(
            side=side,
            orders=orders,
            orders__with_matching_stop=True
        )
        self.assertEqual(order_group.quantity, 300)
        self.assertEqual(order_group.stop.quantity, 300)

        order = orders[0]
        order.stop.update(status=AlgoOrderStatus.FILLED)

        self.assertEqual(order_group.quantity, 200)
        self.assertEqual(order_group.stop.quantity, 300)

        handle_filled_stop_for_individual_order(order)

        self.assertTrue(mock_request.called)
        order_group.refresh_from_db()
        self.assertEqual(order_group.stop.quantity, 200)

    @patch('requests.request', return_value=MockResponse(json_data=edit_sent_success_response))
    def test_handle_filled_stop_for_individual_order__when_group_quantity_is_zero(self, mock_request):
        side = OrderSide.BUY
        quantity = 100.0
        order = OrderFactory(
            order__status=AlgoOrderStatus.FILLED,
            order__quantity=quantity,
            indicator__type=side
        )
        order_group = OrderGroupFactory(
            side=side,
            orders=[order],
            orders__with_matching_stop=True
        )
        group_stop = order_group.stop

        self.assertEqual(order.status, AlgoOrderStatus.FILLED)
        self.assertEqual(order.stop.status, AlgoOrderStatus.NEW)
        self.assertEqual(order_group.quantity, 100)
        self.assertEqual(group_stop.quantity, 100)

        order.stop.update(status=AlgoOrderStatus.FILLED)

        self.assertEqual(order_group.quantity, 0)
        self.assertEqual(order_group.stop.quantity, 100)

        handle_filled_stop_for_individual_order(order)

        self.assertTrue(mock_request.called)

        order_group.refresh_from_db()
        group_stop.refresh_from_db()

        self.assertEqual(group_stop.status, 'CANCELLED')
        self.assertEqual(group_stop.quantity, 0)
        self.assertIsNone(order_group.stop)

    @patch('requests.request', return_value=MockResponse(json_data=cancel_sent_success_response))
    def test_handle_filled_stop_for_order_group(self, mock_request):
        side = OrderSide.BUY
        order_batch = OrderFactory.create_batch(3,
            indicator__type=side,
            order__status=AlgoOrderStatus.FILLED
        )
        order_group = OrderGroupFactory(
            side=side,
            orders=order_batch,
            orders__with_matching_stop=True
        )

        for order in order_group.orders.all():
            self.assertEqual(order.status, AlgoOrderStatus.FILLED)
            self.assertEqual(order.stop.status, AlgoOrderStatus.NEW)

        order_group.stop.update(status=AlgoOrderStatus.FILLED)

        handle_filled_stop_for_order_group(order_group)
        self.assertEqual(mock_request.call_count, 3)

        for order in order_group.orders.all():
            self.assertEqual(order.stop.status, AlgoOrderStatus.CANCELLED)
