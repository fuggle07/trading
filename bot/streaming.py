import asyncio
import os
import threading
import logging
from alpaca.trading.stream import TradingStream
from alpaca.data.live import StockDataStream
from alpaca.trading.models import TradeUpdate

logger = logging.getLogger("market-streamer")

GLOBAL_PRICES = {}
GLOBAL_AI_SENTIMENT = {}

def start_market_stream(api_key, api_secret):
    """Event-Driven WebSocket Architecture for pricing."""
    try:
        stream = StockDataStream(api_key, api_secret)
        
        async def on_quote(q):
            GLOBAL_PRICES[q.symbol] = q.bid_price # store latest bid price
            
        async def on_trade(t):
            GLOBAL_PRICES[t.symbol] = t.price
            
        # You would subscribe to the watchlist here
        # stream.subscribe_quotes(on_quote, "SPY", "QQQ")
        # stream.subscribe_trades(on_trade, "SPY", "QQQ")
        
        # stream.run() blocks the thread
        stream.run()
    except Exception as e:
        logger.error(f"Market stream failed: {e}")

def start_trade_stream(api_key, api_secret, portfolio_manager):
    """Trade Updates WebSocket for exact fills and status."""
    try:
        paper = os.getenv("ALPACA_PAPER_TRADING", "True").lower() == "true"
        stream = TradingStream(api_key, api_secret, paper=paper)
        
        async def on_trade_update(data: TradeUpdate):
            event = data.event
            order = data.order
            ticker = order.symbol
            
            logger.info(f"Trade Update: {event} for {ticker}")
            
            if event == "fill" or event == "partial_fill":
                price = getattr(data, 'price', float(order.filled_avg_price or 0))
                qty = float(getattr(data, 'qty', order.filled_qty))
                action = "BUY" if order.side == "buy" else "SELL"
                
                # Deduct cost or add revenue
                commission = max(1.00, qty * 0.005) # Simulated IBKR commission
                if action == "BUY":
                    cost = (price * qty) + commission
                    portfolio_manager.update_ledger(ticker, -cost, qty, price, action="BUY")
                elif action == "SELL":
                    revenue = (price * qty) - commission
                    portfolio_manager.update_ledger(ticker, revenue, -qty, price, action="SELL")
                
                logger.info(f"✅ Exact Fill Processed via WS: {action} {qty} {ticker} @ {price}")
                
        stream.subscribe_trade_updates(on_trade_update)
        stream.run()
    except Exception as e:
        logger.error(f"Trade stream failed: {e}")

def launch_streams_in_background(api_key, api_secret, watchlist, portfolio_manager):
    """Spawns streams in daemon threads so they don't block the main Flask loop."""
    if not api_key or not api_secret:
        logger.warning("Missing Alpaca keys, skipping WebSocket streams.")
        return
        
    t1 = threading.Thread(target=start_market_stream, args=(api_key, api_secret), daemon=True)
    t1.start()
    
    if portfolio_manager:
        t2 = threading.Thread(target=start_trade_stream, args=(api_key, api_secret, portfolio_manager), daemon=True)
        t2.start()
    
    logger.info("📡 Event-Driven WebSockets (Prices & Trade Updates) launched in background.")
