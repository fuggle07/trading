import os
import asyncio
import aiohttp
from datetime import datetime
from google.cloud import bigquery
from bot.telemetry import logger

PROJECT_ID = os.getenv("PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")

class FundamentalAgent:
    def __init__(self, finnhub_client=None):
        self.fmp_key = os.getenv("FMP_KEY")
        self.finnhub_client = finnhub_client  # Keep as backup if needed
        self.bq_client = bigquery.Client(project=PROJECT_ID) if PROJECT_ID else None
        
        if not self.fmp_key:
            logger.warning("⚠️ FMP_KEY not found. Fundamental analysis restricted.")
        else:
            logger.info("✅ Financial Modeling Prep (FMP) Connected")

    async def _fetch_fmp(self, endpoint: str, ticker: str):
        """Helper to fetch data from FMP API."""
        if not self.fmp_key:
            return None
        
        url = f"https://financialmodelingprep.com/api/v3/{endpoint}/{ticker}?apikey={self.fmp_key}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data:
                            return data
                    else:
                        logger.error(f"[{ticker}] ❌ FMP Error {endpoint}: {response.status}")
        except Exception as e:
            logger.error(f"[{ticker}] ⚠️ FMP Exception {endpoint}: {e}")
        return None

    async def get_fundamentals(self, ticker: str):
        """
        Fetches core fundamentals: PE, EPS, Market Cap via FMP /quote or /key-metrics-ttm.
        """
        # 1. Try FMP First
        data = None
        if self.fmp_key:
            # /quote gives PE, EPS, MarketCap in one shot and is fast
            quote_data = await self._fetch_fmp("quote", ticker)
            if quote_data:
                q = quote_data[0]
                data = {
                    "pe_ratio": float(q.get("pe", 0) or 0),
                    "eps": float(q.get("eps", 0) or 0),
                    "sector": "Unknown", # FMP /profile has sector, but /quote is faster. 
                    "industry": "Unknown",
                    "market_cap": int(q.get("marketCap", 0) or 0),
                }
                logger.info(f"[{ticker}] 📊 {ticker} Fundamentals (FMP): PE={data['pe_ratio']}, EPS={data['eps']}")

        # 2. Fallback to Finnhub if FMP fails
        if not data and self.finnhub_client:
            try:
                logger.info(f"[{ticker}] 📡 Falling back to Finnhub for {ticker} fundamentals...")
                basic_fin = await asyncio.to_thread(
                    self.finnhub_client.company_basic_financials, ticker, "all"
                )
                metric = basic_fin.get("metric", {})
                if metric:
                    data = {
                        "pe_ratio": float(metric.get("peExclExtraTTM", 0) or 0),
                        "eps": float(metric.get("epsExclExtraItemsTTM", 0) or 0),
                        "sector": "Unknown (Finnhub Fallback)",
                        "industry": "Unknown (Finnhub Fallback)",
                        "market_cap": int(metric.get("marketCapitalization", 0) or 0) * 1_000_000,
                    }
                    logger.info(f"[{ticker}] 📊 {ticker} Fundamentals (Finnhub): PE={data['pe_ratio']}, EPS={data['eps']}")
            except Exception as e:
                logger.error(f"[{ticker}] ❌ Finnhub Fallback failed: {e}")

        return data

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
            query_job = client.query(query)
            results = query_job.to_dataframe()
            if not results.empty:
                return results.iloc[0].to_dict()
        except Exception:
            return None

    def _save_to_cache(self, ticker: str, is_healthy: bool, h_reason: str, is_deep: bool, d_reason: str):
        """Persists evaluation results to BigQuery."""
        client = self.bq_client
        if not client:
            return

        rows_to_insert = [{
            "timestamp": datetime.now().isoformat(),
            "ticker": ticker,
            "is_healthy": is_healthy,
            "health_reason": h_reason,
            "is_deep_healthy": is_deep,
            "deep_health_reason": d_reason,
        }]
        try:
            table_id = f"{PROJECT_ID}.trading_data.fundamental_cache"
            client.insert_rows_json(table_id, rows_to_insert)
            logger.info(f"[{ticker}] ✅ Cached fundamental results for {ticker}")
        except Exception as e:
            logger.error(f"[{ticker}] ❌ Failed to cache results: {e}")

    async def evaluate_health(self, ticker: str):
        """
        Returns (is_healthy, reason).
        Checks basic Valuation and Profitability.
        """
        # 1. Check Cache
        cached = await asyncio.to_thread(self._get_cached_evaluation, ticker)
        if cached:
            logger.info(f"[{ticker}] 💾 Using cached health for {ticker}")
            return cached["is_healthy"], cached["health_reason"]

        # 2. Get Data
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

    async def fetch_annual_financials(self, ticker: str):
        """
        Fetches last 2 years of Annual Income, Balance, and Cash Flow statements.
        Returns a dict with 'income', 'balance', 'cash' lists (sorted desc date).
        """
        financials = {"income": [], "balance": [], "cash": []}
        if not self.fmp_key:
            return financials

        # Limit to 2 years to minimize data transfer / processing (we only need YoY)
        endpoints = {
            "income": "income-statement",
            "balance": "balance-sheet-statement",
            "cash": "cash-flow-statement"
        }

        for key, endpoint in endpoints.items():
            url = f"https://financialmodelingprep.com/api/v3/{endpoint}/{ticker}?limit=2&apikey={self.fmp_key}"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data and isinstance(data, list):
                                financials[key] = data
            except Exception as e:
                logger.error(f"[{ticker}] ⚠️ Failed to fetch annual {key}: {e}")
        
        return financials

    def calculate_dcf(self, fcf_ttm, shares_outstanding, growth_rate=0.08, discount_rate=0.10, years=5, terminal_growth=0.02):
        """
        Simplified DCF Valuation.
        Assumes 8% growth for 5 years, then 2% terminal growth, discounted at 10%.
        Returns Fair Value per Share.
        """
        if fcf_ttm <= 0 or shares_outstanding <= 0:
            return 0.0

        future_cash_flows = []
        df_factor = 1 + discount_rate

        # 1. Project Future Cash Flows
        current_fcf = fcf_ttm
        for i in range(1, years + 1):
            current_fcf *= (1 + growth_rate)
            discounted_cf = current_fcf / (df_factor ** i)
            future_cash_flows.append(discounted_cf)

        # 2. Terminal Value
        terminal_value = (current_fcf * (1 + terminal_growth)) / (discount_rate - terminal_growth)
        discounted_terminal_value = terminal_value / (df_factor ** years)

        # 3. Sum and Divide by Shares
        total_enterprise_value = sum(future_cash_flows) + discounted_terminal_value
        fair_value = total_enterprise_value / shares_outstanding

        return round(fair_value, 2)

    def calculate_piotroski_f_score(self, financials):
        """
        Calculates Piotroski F-Score (0-9) using Annual Data.
        Requires at least 2 years of data in 'income', 'balance', 'cash'.
        """
        score = 0
        try:
            inc = financials.get("income", [])
            bal = financials.get("balance", [])
            cfs = financials.get("cash", [])

            if len(inc) < 2 or len(bal) < 2 or len(cfs) < 2:
                return 0 # Not enough data

            # Year 0 (Current/Most Recent), Year 1 (Previous)
            i0, i1 = inc[0], inc[1]
            b0, b1 = bal[0], bal[1]
            c0, c1 = cfs[0], cfs[1]

            # --- Profitability (4 pts) ---
            net_income = float(i0.get("netIncome", 0))
            roa = net_income / float(b0.get("totalAssets", 1))
            cfo = float(c0.get("operatingCashFlow", 0))
            
            roa_prev = float(i1.get("netIncome", 0)) / float(b1.get("totalAssets", 1))

            if net_income > 0: score += 1      # 1. Positive Net Income
            if cfo > 0: score += 1             # 2. Positive Operating Cash Flow
            if roa > roa_prev: score += 1      # 3. Higher ROA YoY
            if cfo > net_income: score += 1    # 4. Cash Flow > Net Income (Quality of Earnings)

            # --- Leverage / Liquidity / Source of Funds (3 pts) ---
            leverage = float(b0.get("totalLiabilities", 0)) / float(b0.get("totalAssets", 1))
            leverage_prev = float(b1.get("totalLiabilities", 0)) / float(b1.get("totalAssets", 1))
            
            current_ratio = float(b0.get("totalCurrentAssets", 1)) / float(b0.get("totalCurrentLiabilities", 1))
            current_ratio_prev = float(b1.get("totalCurrentAssets", 1)) / float(b1.get("totalCurrentLiabilities", 1))

            shares = float(i0.get("weightedAverageShsOut", 0))
            shares_prev = float(i1.get("weightedAverageShsOut", 0))

            if leverage < leverage_prev: score += 1       # 5. Lower Leverage
            if current_ratio > current_ratio_prev: score += 1 # 6. Higher Current Ratio
            if shares <= shares_prev: score += 1          # 7. No Dilution (Shares flat or down)

            # --- Operating Efficiency (2 pts) ---
            gross_margin = (float(i0.get("revenue", 1)) - float(i0.get("costOfRevenue", 0))) / float(i0.get("revenue", 1))
            gross_margin_prev = (float(i1.get("revenue", 1)) - float(i1.get("costOfRevenue", 0))) / float(i1.get("revenue", 1))

            asset_turnover = float(i0.get("revenue", 0)) / float(b0.get("totalAssets", 1))
            asset_turnover_prev = float(i1.get("revenue", 0)) / float(b1.get("totalAssets", 1))

            if gross_margin > gross_margin_prev: score += 1   # 8. Higher Gross Margin
            if asset_turnover > asset_turnover_prev: score += 1 # 9. Higher Asset Turnover

        except Exception as e:
            logger.error(f"F-Score Logic Error: {e}")
            return 0

        return score

    async def evaluate_deep_health(self, ticker: str):
        """
        Returns (is_deep_healthy, reason) using Advanced Fundamental Analysis.
        Integrates DCF, Piotroski F-Score, and Growth.
        """
        # 1. Check Cache
        cached = await asyncio.to_thread(self._get_cached_evaluation, ticker)
        if cached:
            return cached["is_deep_healthy"], cached["deep_health_reason"]

        # 2. Proceed to analysis (Need cache update at end)
        is_healthy, h_reason = await self.evaluate_health(ticker)
        
        is_deep = True
        d_reason_parts = []

        if self.fmp_key:
            try:
                # Fetch Annual Financials (Last 2 years) & TTM Metrics
                financials_task = self.fetch_annual_financials(ticker)
                metrics_task = self._fetch_fmp("key-metrics-ttm", ticker)
                quote_task = self._fetch_fmp("quote", ticker)
                
                financials, metrics_data, quote_data = await asyncio.gather(financials_task, metrics_task, quote_task)

                price = 0.0
                if quote_data:
                    price = float(quote_data[0].get("price", 0))

                # --- A. Piotroski F-Score ---
                f_score = self.calculate_piotroski_f_score(financials)
                
                # --- B. DCF Valuation ---
                fair_value = 0.0
                dcf_upside = 0.0
                if metrics_data:
                    m = metrics_data[0]
                    fcf_per_share = float(m.get("freeCashFlowPerShareTTM", 0) or 0)
                    shares_out = float(financials.get("income", [{}])[0].get("weightedAverageShsOut", 0) or 1)
                    
                    # Estimate Total FCF TTM (Approx)
                    total_fcf = fcf_per_share * shares_out
                    
                    if total_fcf > 0:
                        fair_value = self.calculate_dcf(total_fcf, shares_out)
                        if price > 0:
                            dcf_upside = (fair_value - price) / price

                # --- C. Growth Analysis (YoY) ---
                rev_growth = 0.0
                inc = financials.get("income", [])
                if len(inc) >= 2:
                    rev_curr = float(inc[0].get("revenue", 1))
                    rev_prev = float(inc[1].get("revenue", 1))
                    rev_growth = (rev_curr - rev_prev) / rev_prev

                # --- Rating Logic ---
                # 1. Financial Strength (F-Score)
                if f_score < 4:
                    is_deep = False
                    d_reason_parts.append(f"Weak Financials (F-Score {f_score}/9)")
                else:
                    d_reason_parts.append(f"F-Score {f_score}/9")

                # 2. Valuation (DCF)
                if price > 0 and fair_value > 0:
                    if price > (fair_value * 1.5): # 50% premium over fair value
                         is_deep = False
                         d_reason_parts.append(f"Overvalued (DCF ${fair_value})")
                    else:
                         d_reason_parts.append(f"DCF Fair Value ${fair_value}")

                # 3. Growth
                if rev_growth < 0:
                     is_deep = False
                     d_reason_parts.append(f"Declining Revenue ({rev_growth:.1%})")
                else:
                     d_reason_parts.append(f"Rev Growth {rev_growth:.1%}")

                if not d_reason_parts:
                    d_reason_parts.append("Analysis Inconclusive")

                d_reason = ", ".join(d_reason_parts)

            except Exception as e:
                logger.error(f"[{ticker}] ⚠️ Deep Health Check Failed: {e}")
                import traceback
                traceback.print_exc()
                d_reason = "Check Failed (Exception)"
                is_deep = False # Fail safe
        else:
             d_reason = "No API Key"
             is_deep = False
        
        # 3. Cache Result
        await asyncio.to_thread(self._save_to_cache, ticker, is_healthy, h_reason, is_deep, d_reason)
        return is_deep, d_reason
