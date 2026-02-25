import logging
import os
import requests
from google.cloud import bigquery
from datetime import datetime, timezone
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, TakeProfitRequest, StopLossRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass

# Configure logging
logger = logging.getLogger("execution-manager")


class ExecutionManager:
    """
    Handles order execution, validation against portfolio, and logging.
    Integrates with Alpaca for actual paper trading execution.
    """

    def __init__(self, portfolio_manager=None):
        self.project_id = os.getenv("PROJECT_ID")
        self.bq_client = None
        self.table_id = "trading_data.executions"
        self.portfolio_manager = portfolio_manager
        self.discord_webhook = os.getenv("DISCORD_WEBHOOK_URL")

        # Alpaca Setup
        self.alpaca_key = os.getenv("ALPACA_API_KEY")
        self.alpaca_secret = os.getenv("ALPACA_API_SECRET")
        self.paper_trading = os.getenv("ALPACA_PAPER_TRADING", "True").lower() == "true"
        self.trading_client = None

        if self.alpaca_key and self.alpaca_secret:
            try:
                self.trading_client = TradingClient(
                    self.alpaca_key, self.alpaca_secret, paper=self.paper_trading
                )
                mode = "Paper" if self.paper_trading else "LIVE"
                logger.info(f"✅ Alpaca Trading Client Connected ({mode})")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Alpaca Client: {e}")
        else:
            logger.warning("⚠️ Alpaca Keys missing. Execution will be simulated only.")

        if self.project_id:
            try:
                self.bq_client = bigquery.Client(project=self.project_id)
                logger.info(
                    f"ExecutionManager connected to BigQuery project: {self.project_id}"
                )
            except Exception as e:
                logger.error(f"Failed to initialize BigQuery client: {e}")
        else:
            logger.warning("PROJECT_ID not found. BigQuery logging disabled.")

    def place_order(
        self,
        ticker,
        action,
        quantity,
        price,
        cash_available=0.0,
        reason="Strategy Signal",
    ):
        """
        Executes an order if funds/holdings allow, then logs it.
        Now supports Unified Cash Pool via 'cash_available' parameter.
        Executes real paper trades on Alpaca if configured.
        """

        logger.info(
            f"[{ticker}] PROCESSING {action} on {ticker} @ {price} | Cash Alloc: ${cash_available:.2f}"
        )

        if price <= 0:
            logger.warning(f"[{ticker}] ❌ REJECTED: Invalid execution price {price}")
            return {"status": "REJECTED", "reason": "INVALID_PRICE"}

        # 0. Portfolio Validation (The Gatekeeper)
        # We keep the local validation to ensure our internal ledger stays sane
        if self.portfolio_manager:
            try:
                # Get current holdings state for this TICKER
                try:
                    state = self.portfolio_manager.get_state(ticker)
                except ValueError:
                    state = {"holdings": 0.0, "avg_price": 0.0}

                holdings = state["holdings"]

                # Check constraints & Calculate Quantity
                if action == "BUY":
                    # Calculate max quantity based on allocated cash
                    if quantity == 0:
                        # Auto-calculate max shares
                        quantity = int(cash_available // price)

                    cost = price * quantity

                    if quantity <= 0:
                        logger.warning(
                            f"[{ticker}] ❌ REJECTED: Quantity would be 0 (Cash ${cash_available:.2f} / Price ${price:.2f})"
                        )
                        return {"status": "REJECTED", "reason": "ZERO_QUANTITY"}

                    if cash_available < cost:
                        logger.warning(
                            f"[{ticker}] ❌ REJECTED: Insufficient funds (${cash_available:.2f} < ${cost:.2f})"
                        )
                        return {"status": "REJECTED", "reason": "INSUFFICIENT_FUNDS"}

                elif action == "SELL":
                    if quantity == 0:
                        # Auto-sell ALL
                        quantity = holdings

                    if holdings < quantity or quantity <= 0:
                        logger.warning(
                            f"[{ticker}] ❌ REJECTED: Insufficient holdings ({holdings} < {quantity})"
                        )
                        return {"status": "REJECTED", "reason": "INSUFFICIENT_HOLDINGS"}

            except Exception as e:
                logger.error(f"[{ticker}] Portfolio Validation Failed: {e}")
                return {"status": "ERROR", "reason": str(e)}
        else:
            logger.warning(
                "⚠️ PortfolioManager not connected! executing blindly (Sim Mode)"
            )

        # 1. Execute on Alpaca (The Real Execution)
        alpaca_order_id = None
        execution_status = (
            "FILLED"  # Default to filled for local log unless Alpaca fails
        )

        # Calculate IBKR Fixed Commission for Simulation
        commission = max(1.00, quantity * 0.005)

        if self.trading_client:
            try:
                side = OrderSide.BUY if action == "BUY" else OrderSide.SELL

                # Prepare Order to avoid execution slippage
                # BUY uses OTOCO Bracket (Limit entry, Stop Loss, Take Profit)
                # SELL uses standard Limit or Market to exit cleanly
                if action == "BUY":
                    # Buffer entry by +0.1% to guarantee fill while bounding slippage
                    limit_price = round(price * 1.001, 2)
                    # Hard stop at -12% on broker servers
                    stop_price = round(price * 0.88, 2)
                    # Profit target at +10% 
                    profit_price = round(price * 1.10, 2)
                    
                    order_data = LimitOrderRequest(
                        symbol=ticker,
                        qty=quantity,
                        side=side,
                        time_in_force=TimeInForce.DAY,
                        limit_price=limit_price,
                        order_class=OrderClass.BRACKET,
                        take_profit=TakeProfitRequest(limit_price=profit_price),
                        stop_loss=StopLossRequest(stop_price=stop_price)
                    )
                else:
                    # Selling: Use a tight Limit Order to exit gracefully without getting gouged (e.g. -0.5% buffer)
                    limit_price = round(price * 0.995, 2)
                    order_data = LimitOrderRequest(
                        symbol=ticker,
                        qty=quantity,
                        side=side,
                        time_in_force=TimeInForce.DAY,
                        limit_price=limit_price
                    )

                logger.info(
                    f"[{ticker}] 🚀 Submitting Alpaca Order: {side} {quantity} {ticker}"
                )
                order = self.trading_client.submit_order(order_data)
                alpaca_order_id = str(order.id)
                logger.info(
                    f"[{ticker}] ✅ Alpaca Order Submitted: {alpaca_order_id} ({order.status})"
                )

                mode = "Paper" if self.paper_trading else "LIVE"
                # Send Discord Notification
                self._send_discord_alert(
                    action=action,
                    quantity=quantity,
                    ticker=ticker,
                    price=price,
                    reason=reason,
                    mode=mode,
                )

            except Exception as e:
                logger.error(f"[{ticker}] ❌ Alpaca Execution Failed: {e}")
                return {"status": "FAILED", "reason": f"Alpaca Error: {str(e)}"}

        # 2. Update Local Ledger (Shadow Ledger)
        # REMOVED: Now delegating ledger updates exclusively to Alpaca TradeUpdates WebSocket
        # to ensure cryptographic truth of actual fills, rather than assuming success.
        
        logger.info(f"[{ticker}] ⌛ Waiting for TradeUpdate WebSocket to confirm fill and update ledger...")

        # 3. Log to BigQuery
        execution_id = f"exec-{int(datetime.now().timestamp())}-{ticker}"

        execution_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_id": execution_id,
            "alpaca_order_id": alpaca_order_id,
            "ticker": ticker,
            "action": action,
            "price": price,
            "quantity": quantity,
            "commission": commission,
            "reason": reason,
            "status": execution_status,
        }

        self._log_to_bigquery(execution_data)

        return {
            "status": execution_status,
            "execution_id": execution_id,
            "alpaca_id": alpaca_order_id,
            "details": execution_data,
        }

    def _log_to_bigquery(self, data):
        """Internal helper to stream a single row to BigQuery."""
        if not self.bq_client:
            return

        try:
            errors = self.bq_client.insert_rows_json(self.table_id, [data])  # type: ignore
            if errors:
                logger.error(
                    f"[{data.get('ticker', 'Unknown')}] BigQuery Insert Errors: {errors}"
                )
            else:
                logger.info(
                    f"[{data['ticker']}] Logged execution {data['execution_id']} to {self.table_id}"
                )
        except Exception as e:
            logger.warning(
                f"[{data.get('ticker', 'Unknown')}] Failed to log to BigQuery ({self.table_id}): {e}"
            )

    def _send_discord_alert(self, action, quantity, ticker, price, reason, mode):
        """Sends a notification to the configured Discord webhook using an embed block."""
        if not self.discord_webhook:
            return

        try:
            color = 3066993 if action == "BUY" else 15158332
            embed = {
                "title": f"[{mode}] Trade Executed: {action} {ticker}",
                "color": color,
                "fields": [
                    {"name": "Action", "value": action, "inline": True},
                    {"name": "Ticker", "value": ticker, "inline": True},
                    {"name": "Quantity", "value": str(quantity), "inline": True},
                    {"name": "Price", "value": f"${price:.2f}", "inline": True},
                    {"name": "Reason", "value": reason, "inline": False},
                ],
                "footer": {"text": "Aberfeldie Trading Node"},
            }
            payload = {"username": "Trader Bot", "embeds": [embed]}

            resp = requests.post(self.discord_webhook, json=payload, timeout=5)
            if resp.status_code >= 400:
                logger.warning(
                    f"Failed to send Discord alert: {resp.status_code} - {resp.text}"
                )
        except Exception as e:
            logger.warning(f"Error sending Discord alert: {e}")
