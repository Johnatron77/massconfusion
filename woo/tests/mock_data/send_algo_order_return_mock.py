def send_algo_order_return_mock(order_id: int = 123456789, quantity: float = 0.001):
    return {
        "rows": [
            {
                "orderId": order_id,
                "clientOrderId": 0,
                "algoType": "STOP",
                "quantity": quantity,
            }
        ]
    }