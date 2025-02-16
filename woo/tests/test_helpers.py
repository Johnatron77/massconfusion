from unittest.mock import patch

from django.test import TestCase

from woo.api_types import AlgoOrderUpdateRequestParams, AlgoOrderRequestParams, OrderSide, OrderType, AlgoType, \
    AlgoOrderStatus
from woo.helpers import update_algo_order, create_algo_order, cancel_algo_order, create_algo_order_params
from woo.tests.factory.woo_algo_order_factory import WooAlgoOrderFactory
from woo.tests.helpers import WooMockResponse
from woo.tests.mock_data.algo_order_mock import edit_sent_success_response, cancel_sent_success_response
from woo.tests.mock_data.send_algo_order_return_mock import send_algo_order_return_mock


class TestHelpers(TestCase):

    def setUp(self):
        self.patcher = patch('requests.request')
        self.mock_request = self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_create_algo_order(self):
        params: AlgoOrderRequestParams = {
            'symbol': 'BTCUSDT',
            'side': OrderSide.BUY,
            'quantity': '0.1',
            'triggerPrice': '10000.0',
            'reduceOnly': False,
            'type': OrderType.MARKET,
            'algoType': AlgoType.STOP,
            'orderTag': 'test_tag',
        }

        self.mock_request.return_value = WooMockResponse(json_data=send_algo_order_return_mock(
            123,
            quantity=0.1,
        ))

        order = create_algo_order(
            params['symbol'],
            params['side'],
            params['quantity'],
            params['reduceOnly'],
            params['triggerPrice'],
            params['orderTag'],
        )

        self.assertEqual(self.mock_request.call_count, 1)
        self.assertEqual(order.order_id, 123)
        self.assertEqual(order.symbol, params['symbol'])
        self.assertEqual(order.side, params['side'])
        self.assertEqual(order.quantity, float(params['quantity']))
        self.assertEqual(order.trigger_price, float(params['triggerPrice']))
        self.assertEqual(order.reduce_only, params['reduceOnly'])
        self.assertEqual(order.type, params['type'])
        self.assertEqual(order.algo_type, params['algoType'])
        self.assertEqual(order.order_tag, params['orderTag'])

    def test_create_algo_order_params(self):
        symbol = 'BTCUSDT'
        side = OrderSide.BUY
        quantity = '0.1'
        reduce_only = False
        trigger_price = '10000.0'

        params = create_algo_order_params(symbol, side, quantity, reduce_only, trigger_price)

        self.assertEqual(params['symbol'], symbol)
        self.assertEqual(params['side'], side.value)
        self.assertEqual(params['quantity'], str(quantity))
        self.assertEqual(params['reduceOnly'], reduce_only)
        self.assertEqual(params['triggerPrice'], str(trigger_price))
        self.assertEqual(params['type'], 'MARKET')
        self.assertEqual(params['algoType'], 'STOP')

    def test_update_algo_order(self):
        order = WooAlgoOrderFactory()
        params: AlgoOrderUpdateRequestParams = {
            'quantity': '0.2',
            'triggerPrice': '10000.0',
        }

        self.mock_request.return_value = WooMockResponse(json_data=edit_sent_success_response)

        update_algo_order(order, params)

        self.assertEqual(order.quantity, params['quantity'])
        self.assertEqual(order.trigger_price, params['triggerPrice'])
        self.assertEqual(self.mock_request.call_count, 1)

    def test_handle_cancel_algo_order(self):
        order = WooAlgoOrderFactory()
        self.mock_request.return_value = WooMockResponse(json_data=cancel_sent_success_response)
        self.assertEqual(order.status, AlgoOrderStatus.NEW)
        cancel_algo_order(order)
        self.assertEqual(self.mock_request.call_count, 1)
        self.assertEqual(order.status, AlgoOrderStatus.CANCELLED)