

def get_mock_algo_order_data(
   order_id: int = 2650645,
   reduce_only: bool = False,
   status: str = 'FILLED',
   side: str = 'BUY',
   is_triggered: bool = False,
   quantity: str = '0.0001'
):
    return {
       "symbol": "PERP_BTC_USDT",
       "type": "MARKET",
       "algoType": "STOP_LOSS",
       "side": side,
       "quantity": quantity,
       "reduceOnly": reduce_only,

       "isTriggered": is_triggered,
       "triggerPrice": 35800,
       "triggerPriceType": "MARKET_PRICE",
       "triggerTradePrice": 35800,
       "triggerStatus": "USELESS",
       "triggerTime": 1699477397398,

       "orderTag": "default",
       "tradeId": 448004279,
       "totalExecutedQuantity": 0.0002,
       "averageExecutedPrice": 35810.4,
       "createdTime": "1676277825.917",
       "updatedTime": "1676280901.229",

       "rootAlgoOrderId": order_id,
       "parentAlgoOrderId": 0,
       "algoOrderId": order_id,
       "clientOrderId": 0,
       "price": 0,
       "executedPrice": 35810.4,
       "executedQuantity": 0.0002,
       "fee": 0.00179052,
       "reason": "",
       "feeAsset": "USDT",
       "totalFee": 0.00179052,
       "timestamp": 1699477397556,
       "visibleQuantity": 0.0002,
       "triggered": is_triggered,
       "maker": False,
       "activated": False,
       "isMaker": False,
       "isActivated": False,
       "rootAlgoStatus": status,
       "algoStatus": status
    }