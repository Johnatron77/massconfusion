from django.core.management.base import BaseCommand, CommandError

import environ

env = environ.Env()
environ.Env.read_env()

WOO_KEY = env('WOO_TRADE_KEY')
WOO_SECRET = env('WOO_TRADE_SECRET')
WOO_APP_ID = env('WOO_TRADE_APP_ID')
WOO_WS_DEBUG = env.bool('WOO_WS_DEBUG', False)
WOO_WS_ENABLE_TRACE = env.bool('WOO_WS_ENABLE_TRACE', False)


class Command(BaseCommand):
    help = 'connect to private woo'

    def handle(self, *args, **options):
        try:
            import websocket
            from us_orders.handlers.private_woo_ws_handler import PrivateWooWSHandler

            websocket.enableTrace(WOO_WS_ENABLE_TRACE)

            self.woo_ws_handler = PrivateWooWSHandler(
                app_id=WOO_APP_ID,
                app_key=WOO_KEY,
                app_secret=WOO_SECRET,
                debug=WOO_WS_DEBUG
            )
            self.woo_ws_handler.connect()
        except CommandError as e:
            print(e)
