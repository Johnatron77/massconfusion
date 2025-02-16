from django.db import IntegrityError
from django.test import TestCase

from woo.tests.factory.woo_algo_order_factory import WooAlgoOrderFactory
from woo.tests.mock_data.algo_order_mock import get_mock_algo_order_data


class WooAlgoOrderModelTests(TestCase):

    def test_woo_algo_order_order_id_unique_constraint(self):
        order_id = 1234567
        order = WooAlgoOrderFactory(order_id=order_id)
        self.assertIsNotNone(order.id)
        self.assertEqual(order.order_id, order_id)
        order2 = WooAlgoOrderFactory.build(order_id=order_id)
        try:
            order2.save()
            self.fail('Should have raised IntegrityError')
        except IntegrityError as e:
            self.assertTrue(e.args[0].find('woo_algo_order_order_id_unique_constraint'))

    def test_woo_algo_order_side_is_not_buy_or_sell_constraint(self):
        try:
            WooAlgoOrderFactory(side='MEH')
            self.fail('Should have raised IntegrityError')
        except IntegrityError as e:
            self.assertTrue(e.args[0].find('woo_algo_order_type_is_sell_or_buy_constraint'))

    def test_update(self):
        order_id = 1234567
        order = WooAlgoOrderFactory(order_id=order_id)
        data = get_mock_algo_order_data(order_id=order_id)
        order.update(**data)