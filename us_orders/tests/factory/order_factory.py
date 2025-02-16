import time
from typing import Optional, Literal

from factory import SubFactory, LazyAttribute, SelfAttribute, Maybe
from factory.django import DjangoModelFactory

from us.tests.factory.timeframe_kline_signal_factory import TimeframeKlineSignalFactory
from woo.tests.factory.woo_algo_order_factory import WooAlgoOrderFactory


class OrderFactory(DjangoModelFactory):
    indicator = SubFactory(
        TimeframeKlineSignalFactory,
        direction=LazyAttribute(lambda o: o.factory_parent.direction)
    )
    order = SubFactory(
        WooAlgoOrderFactory,
        side=SelfAttribute('..indicator.type'),
        reduce_only=False,
        trigger_time=LazyAttribute(lambda o: time.time() if o.status == 'FILLED' else None),
    )
    stop = Maybe(
        LazyAttribute(lambda o: o.order.status == 'FILLED'),
        SubFactory(
            WooAlgoOrderFactory,
            side=LazyAttribute(lambda o: ['SELL', 'BUY'][o.factory_parent.order.side == 'SELL']),
            reduce_only=True,
            quantity=LazyAttribute(lambda o: o.factory_parent.order.quantity),
        ),
        None,
    )

    direction: Optional[Literal["BUY", "SELL"]] = None

    class Meta:
        model = 'us_orders.Order'
        django_get_or_create = ('order', 'stop', 'indicator')
        exclude = ('direction',)
