from woo.api_ws import WooWSClient
from us_orders.flows.order_status_change_flow import handle_algo_order_update, handle_market_order


class PrivateWooWSHandler:

    app_id: str
    app_key: str
    app_secret: str
    debug: bool

    ws: WooWSClient

    def __init__(
        self,
        app_id: str,
        app_key: str,
        app_secret: str,
        debug: bool = False
    ):
        self.app_id = app_id
        self.app_key = app_key
        self.app_secret = app_secret
        self.debug = debug

    def connect(self):
        self.ws = WooWSClient(
            app_id=self.app_id,
            app_key=self.app_key,
            app_secret=self.app_secret,
            debug=self.debug,
            private=True,
            connect_callback=self._connected
        )
        self.ws.connect()

    def _connected(self):
        self.ws.subscribe_to_execution_report(
            lambda order: handle_market_order(order)
        )
        self.ws.subscribe_to_algo_execution_report_v2(
            lambda message: handle_algo_order_update(message[0])
        )
        # subscribe so debug will print
        self.ws.subscribe_to_position(lambda message: message)
        # subscribe so debug will print
        self.ws.subscribe_to_balance(lambda message: message)
