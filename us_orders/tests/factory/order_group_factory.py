from factory import SubFactory, post_generation
from factory.django import DjangoModelFactory

from us.tests.factory.timeframe_group_factory import TimeframeGroupFactory
from us_orders.tests.factory.order_factory import OrderFactory
from woo.tests.factory.woo_algo_order_factory import WooAlgoOrderFactory


class OrderGroupFactory(DjangoModelFactory):
    group = SubFactory(TimeframeGroupFactory)
    side = 'BUY'
    stop = None

    orders__count = 1 # required to prevent error
    orders__with_matching_stop = False # required to prevent error
    orders__stop_status = 'NEW' # required to prevent error

    @post_generation
    def orders(obj, create, extracted, **kwargs):
        if not create:
            return

        count = kwargs.get('count')
        with_matching_stop = kwargs.get('with_matching_stop')
        stop_status = kwargs.get('stop_status')
        quantity = kwargs.get('order__quantity', 0.1)
        status = kwargs.get('order__status', 'NEW')
        trigger_price = kwargs.get('order__trigger_price', 100.00)
        trigger_time = kwargs.get('order__trigger_time', None)

        if extracted is not None:
            obj.orders.set(extracted)
        else:
            for i in range(count):
                obj.orders.add(OrderFactory(
                    direction=obj.side,
                    order__status=status,
                    order__quantity=quantity,
                    order__trigger_price=trigger_price,
                    order__trigger_time=trigger_time
                ))

        if not with_matching_stop:
            return

        obj.set_stop(WooAlgoOrderFactory(
            side=['SELL', 'BUY'][obj.side == 'SELL'],
            status=stop_status,
            reduce_only=True,
            quantity=obj.quantity
        ))

    class Meta:
        model = 'us_orders.OrderGroup'
