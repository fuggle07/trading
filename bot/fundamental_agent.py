import logging
from alpha_vantage.fundamentaldata import FundamentalData
from google.cloud import bigquery
import os
import json
from datetime import datetime

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FundamentalAgent")

PROJECT_ID = os.getenv("PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")

class FundamentalAgent:
    def __init__(self):
        self.api_key = os.getenv("ALPHA_VANTAGE_KEY")
        self.bq_client = bigquery.Client(project=PROJECT_ID) if PROJECT_ID else None
        
        if not self.api_key:
            logger.warning(
                "⚠️ ALPHA_VANTAGE_KEY not found. Fundamental analysis disabled."
            )
            self.fd = None
        else:
            self.fd = FundamentalData(key=self.api_key, output_format="json")
            logger.info("✅ Alpha Vantage Connected")

    async def get_fundamentals(self, ticker: str):
        """
        Fetches basic fundamental data: PE Ratio, EPS, Sector.
        """
        if not self.fd:
            return None

        try:
            # Fetch Company Overview
            overview, _ = self.fd.get_company_overview(symbol=ticker)

            if not overview:
                logger.warning(f"⚠️ No fundamental data found for {ticker}")
                return None

            data = {
                "pe_ratio": float(overview.get("PERatio", 0) or 0),
                "eps": float(overview.get("EPS", 0) or 0),
                "sector": overview.get("Sector", "Unknown"),
                "industry": overview.get("Industry", "Unknown"),
                "market_cap": int(overview.get("MarketCapitalization", 0) or 0),
            }
            logger.info(
                f"📊 {ticker} Fundamentals: PE={data['pe_ratio']}, EPS={data['eps']}"
            )
            return data

        except Exception as e:
            logger.error(f"❌ Failed to fetch fundamentals for {ticker}: {e}")
            return None

    def _get_cached_evaluation(self, ticker: str):
        """Checks BigQuery for today's evaluation of this ticker."""
        client = self.bq_client
        if not client:
            return None
            
        query = f"""
            SELECT is_healthy, health_reason, is_deep_healthy, deep_health_reason
            FROM `{PROJECT_ID}.trading_data.fundamental_cache`
            WHERE ticker = '{ticker}'
            AND DATE(timestamp) = CURRENT_DATE('America/New_York')
            ORDER BY timestamp DESC
            LIMIT 1
        """
        try:
            # We use a thread for the query since we are in an async context
            # but using the sync BQ client
            query_job = client.query(query)
            results = query_job.to_dataframe()
            if not results.empty:
                return results.iloc[0].to_dict()
        except Exception as e:
            logger.error(f"⚠️ Cache lookup failed for {ticker}: {e}")
        return None

    def _save_to_cache(self, ticker: str, is_healthy: bool, h_reason: str, is_deep: bool, d_reason: str):
        """Persists evaluation results to BigQuery."""
        client = self.bq_client
        if not client:
            return
            
        rows_to_insert = [
            {
                "timestamp": datetime.now().isoformat(),
                "ticker": ticker,
                "is_healthy": is_healthy,
                "health_reason": h_reason,
                "is_deep_healthy": is_deep,
                "deep_health_reason": d_reason
            }
        ]
        try:
            table_id = f"{PROJECT_ID}.trading_data.fundamental_cache"
            client.insert_rows_json(table_id, rows_to_insert)
            logger.info(f"✅ Cached fundamental results for {ticker}")
        except Exception as e:
            logger.error(f"❌ Failed to cache results for {ticker}: {e}")

    async def evaluate_health(self, ticker: str):
        """
        Returns a simplified health check tuple: (is_healthy: bool, reason: str)
        Rule: Healthy if PE < 60 (Tech adjusted) and EPS > 0.
        """
        # 1. Check Cache
        import asyncio
        cached = await asyncio.to_thread(self._get_cached_evaluation, ticker)
        if cached:
            logger.info(f"💾 Using cached health for {ticker}")
            return cached["is_healthy"], cached["health_reason"]

        # 2. Proceed to API if no cache
        data = await self.get_fundamentals(ticker)
        if not data:
            return True, "No Data (Skipped)"

        pe = data["pe_ratio"]
        eps = data["eps"]

        if eps <= 0:
            return False, f"Unprofitable (EPS {eps})"
        if pe > 100:
            return False, f"Overvalued (PE {pe} > 100)"

        return True, f"Healthy (PE {pe}, EPS {eps})"

    async def get_financial_statements(self, ticker: str):
        """
        Fetches Income Statement, Balance Sheet and Cash Flow.
        """
        if not self.fd:
            return None

        try:
            logger.info(f"📡 Fetching deep financials for {ticker}...")
            # to_thread if the library is blocking. wrap calls if needed.
            # FundamentalData is synchronous, so we should wrap these
            import asyncio
            income_q, _ = await asyncio.to_thread(self.fd.get_income_statement_quarterly, symbol=ticker)
            if isinstance(income_q, str) and "Alpha Vantage! Please consider" in income_q:
                 logger.error(f"❌ Alpha Vantage Rate Limit Hit (Income Q): {income_q}")
                 return None
            
            balance_a, _ = await asyncio.to_thread(self.fd.get_balance_sheet_annual, symbol=ticker)
            if isinstance(balance_a, str) and "Alpha Vantage! Please consider" in balance_a:
                 logger.error(f"❌ Alpha Vantage Rate Limit Hit (Balance A): {balance_a}")
                 return None
            
            cash_a, _ = await asyncio.to_thread(self.fd.get_cash_flow_annual, symbol=ticker)
            return {"income_q": income_q, "balance_a": balance_a, "cash_a": cash_a}
        except Exception as e:
            logger.error(f"❌ Failed to fetch financial statements for {ticker}: {e}")
            return None

    async def evaluate_deep_health(self, ticker: str):
        """
        Returns (is_deep_healthy: bool, reason: str) and CACHES result.
        """
        # 1. Check Cache
        import asyncio
        cached = await asyncio.to_thread(self._get_cached_evaluation, ticker)
        if cached:
            return cached["is_deep_healthy"], cached["deep_health_reason"]

        # 2. Proceed to API
        is_healthy, h_reason = await self.evaluate_health(ticker)
        
        stats = await self.get_financial_statements(ticker)
        if not stats or not stats.get("balance_a") or not stats.get("income_q"):
            is_deep, d_reason = True, "No Statement Data (Skipped)"
        else:
            try:
                reports = stats["balance_a"].get("annualReports", [])
                if not reports:
                    is_deep, d_reason = True, "No Balance Sheet reports (Skipped)"
                else:
                    recent_balance = reports[0]
                    current_assets = float(recent_balance.get("totalCurrentAssets", 0) or 0)
                    current_liabilities = float(recent_balance.get("totalCurrentLiabilities", 0) or 0)
                    current_ratio = (current_assets / current_liabilities if current_liabilities > 0 else 1.0)
                    total_liabilities = float(recent_balance.get("totalLiabilities", 0) or 0)
                    equity = float(recent_balance.get("totalShareholderEquity", 0) or 1)
                    de_ratio = total_liabilities / equity if equity != 0 else 0
                    q_reports = stats["income_q"].get("quarterlyReports", [])
                    if not q_reports:
                        is_deep, d_reason = True, "No Income Statement reports (Skipped)"
                    else:
                        recent_income_q = q_reports[:4]
                        net_incomes = [float(q.get("netIncome", 0) or 0) for q in recent_income_q]
                        is_profitable_trend = all(ni > 0 for ni in net_incomes)

                        if current_ratio < 0.8:
                            is_deep, d_reason = False, f"Liquidity Crisis (CR {current_ratio:.2f})"
                        elif de_ratio > 3.0:
                            is_deep, d_reason = False, f"High Leverage (D/E {de_ratio:.2f})"
                        elif not is_profitable_trend:
                            is_deep, d_reason = False, "Unstable Earnings"
                        else:
                            is_deep, d_reason = True, f"Deep Health OK (CR {current_ratio:.2f})"
            except Exception as e:
                logger.error(f"⚠️ Error parsing financials for {ticker}: {e}")
                is_deep, d_reason = True, "Parsing Error (Skipped)"

        # 3. Cache the final result of BOTH evaluations (async to thread since BQ client is sync)
        await asyncio.to_thread(self._save_to_cache, ticker, is_healthy, h_reason, is_deep, d_reason)
        return is_deep, d_reason
