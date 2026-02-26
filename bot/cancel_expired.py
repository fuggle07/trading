import os
import requests
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus

client = TradingClient(os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_API_SECRET"), paper=True)
req = GetOrdersRequest(status=QueryOrderStatus.OPEN)
orders = client.get_orders(req)
for order in orders:
    print(f"Cancelling {order.id} {order.symbol} {order.side} {order.qty} {order.time_in_force}")
    client.cancel_order_by_id(order.id)
