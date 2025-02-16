from factory import LazyFunction
from factory.django import DjangoModelFactory
from faker import Faker

faker = Faker()


class WooAlgoOrderFactory(DjangoModelFactory):
    order_id = LazyFunction(lambda: faker.unique.random_int(min=1111111, max=9999999))
    symbol = 'PERP_BTC_USDT'
    side = 'BUY'
    status = 'NEW'
    reduce_only = False
    quantity = 0.1
    trigger_price = 100

    class Meta:
        model = 'woo.WooAlgoOrder'
        django_get_or_create = ('order_id',)
