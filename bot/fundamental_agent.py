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
        
        url = f"https://financialmodelingprep.com/stable/{endpoint}?symbol={ticker}&apikey={self.fmp_key}" # Switch to stable/query param
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
            # /quote gives MarketCap, Price. /ratios-ttm gives PE, EPS.
            quote_task = self._fetch_fmp("quote", ticker)
            ratios_task = self._fetch_fmp("ratios-ttm", ticker)
            
            quote_data, ratios_data = await asyncio.gather(quote_task, ratios_task)

            if quote_data:
                q = quote_data[0]
                pe = 0.0
                eps = 0.0
                
                # Try to get PE/EPS from ratios-ttm first (more reliable on stable)
                if ratios_data:
                    r = ratios_data[0]
                    pe = float(r.get("priceToEarningsRatioTTM", 0) or 0)
                    eps = float(r.get("netIncomePerShareTTM", 0) or 0)
                else:
                    # Fallback to quote if ratios failed (legacy behavior)
                    pe = float(q.get("pe", 0) or 0)
                    eps = float(q.get("eps", 0) or 0)

                data = {
                    "pe_ratio": pe,
                    "eps": eps,
                    "sector": "Unknown", 
                    "industry": "Unknown",
                    "market_cap": int(q.get("marketCap", 0) or 0),
                }
                logger.info(f"[{ticker}] 📊 {ticker} Fundamentals (FMP): PE={data['pe_ratio']:.2f}, EPS={data['eps']:.2f}")

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

    async def get_intelligence_metrics(self, ticker: str) -> dict:
        """
        Fetches 'Soft' context: Analyst Consensus and Institutional Flow.
        """
        intelligence = {
            "analyst_consensus": "Neutral",
            "institutional_momentum": "Neutral"
        }
        
        if not self.fmp_key:
            return intelligence

        try:
            # 1. Analyst Ratings (FMP /analyst-stock-recommendations)
            ratings_data = await self._fetch_fmp("analyst-stock-recommendations", ticker)
            if ratings_data and isinstance(ratings_data, list):
                r = ratings_data[0]
                intelligence["analyst_consensus"] = f"{r.get('recommendation', 'Neutral')} (Consensus of {r.get('analystRatingsTotal', 0)} analysts)"
            
            # 2. Institutional/Insider Flow (FMP /institutional-ownership/symbol-ownership-percent)
            # We look at 'totalOwnershipPercentage' or recent institutional trends if available.
            # Simplified proxy: Institutional Ownership Percent
            inst_data = await self._fetch_fmp("institutional-ownership/symbol-ownership-percent", ticker)
            if inst_data and isinstance(inst_data, list):
                pct = float(inst_data[0].get("totalOwnershipPercentage", 0) or 0)
                intelligence["institutional_momentum"] = f"{pct:.1f}% Institutional Ownership"

        except Exception as e:
            logger.error(f"[{ticker}] ⚠️ Failed to fetch intelligence metrics: {e}")
            
        return intelligence

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

    def _save_to_cache(self, ticker: str, is_healthy: bool, h_reason: str, is_deep: bool, d_reason: str, metrics: dict = None):
        """Persists evaluation results to BigQuery."""
        client = self.bq_client
        if not client:
            return

        import json
        metrics_json = json.dumps(metrics) if metrics else None

        rows_to_insert = [{
            "timestamp": datetime.now().isoformat(),
            "ticker": ticker,
            "is_healthy": is_healthy,
            "health_reason": h_reason,
            "is_deep_healthy": is_deep,
            "deep_health_reason": d_reason,
            "metrics_json": metrics_json
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
            url = f"https://financialmodelingprep.com/stable/{endpoint}?symbol={ticker}&limit=2&apikey={self.fmp_key}" # Switch to stable/query param
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

    def calculate_quality_score(self, ratios: dict, metrics: dict, financials: dict):
        """
        Calculates a Composite Quality Score (0-100).
        Weighted average of Profitability, Safety, and Value.
        """
        score = 0.0
        
        # Helper to safely get float
        def g(d, k, default=0.0):
            return float(d.get(k, 0) or default)

        # 1. Profitability (40 points)
        # ROE > 15% (+10), ROA > 5% (+10), Gross Margin > 40% (+10), Net Margin > 10% (+10)
        roe = g(ratios, "returnOnEquityTTM")
        roa = g(ratios, "returnOnAssetsTTM")
        gm = g(ratios, "grossProfitMarginTTM")
        nm = g(ratios, "netProfitMarginTTM")

        if roe > 0.15: score += 10
        elif roe > 0.08: score += 5
        
        if roa > 0.05: score += 10
        elif roa > 0.02: score += 5

        if gm > 0.40: score += 10
        elif gm > 0.20: score += 5

        if nm > 0.10: score += 10
        elif nm > 0: score += 5

        # 2. Safety (30 points)
        # Current Ratio > 1.5 (+10), Debt/Equity < 0.5 (+10), Interest Cov > 5 (+10)
        cr = g(ratios, "currentRatioTTM")
        de = g(ratios, "debtToEquityRatioTTM")
        ic = g(ratios, "interestCoverageRatioTTM")

        if cr > 1.5: score += 10
        elif cr > 1.0: score += 5

        if de < 0.5: score += 10
        elif de < 1.0: score += 5

        if ic > 5: score += 10
        elif ic > 1: score += 5

        # 3. Value (30 points)
        # PE < 25 (+10), PEG < 1.5 (+10), DCF Upside > 10% (+10)
        pe = g(ratios, "priceToEarningsRatioTTM")
        peg = g(ratios, "priceToEarningsGrowthRatioTTM")
        
        # DCF Upside Logic
        # We need recent Price and Fair Value, which aren't in ratios/metrics directly strictly speaking 
        # but we can approximate or pass them in? 
        # Actually, let's keep it simple and use whatever ratios has or skip DCF here 
        # and assume "Price to Free Cash Flow" is a good proxy for value.
        pfcf = g(ratios, "priceToFreeCashFlowRatioTTM")

        if 0 < pe < 25: score += 10
        elif 0 < pe < 40: score += 5

        if 0 < peg < 1.5: score += 10
        elif 0 < peg < 2.5: score += 5

        if 0 < pfcf < 20: score += 10
        elif 0 < pfcf < 30: score += 5

        return int(score)

    async def evaluate_deep_health(self, ticker: str):
        """
        Returns (is_deep_healthy, reason) using Advanced Fundamental Analysis.
        Integrates DCF, Piotroski F-Score, and Growth.
        """
        # --- 0. Initialize Variables (Prevention for UnboundLocalError) ---
        is_deep = True
        d_reason = "Analysis Pending"
        f_score = 0
        quality_score = 0
        rev_growth = 0.0
        fair_value = 0.0
        price = 0.0
        ratios = {}
        metrics = {}
        
        # Get basic health first (we need is_healthy and h_reason for caching)
        is_healthy, h_reason = await self.evaluate_health(ticker)

        # 1. Check Cache
        cached = await asyncio.to_thread(self._get_cached_evaluation, ticker)
        if cached:
            # Attempt to parse F-Score from reason string if cached
            import re
            d_reason = cached["deep_health_reason"]
            f_score_match = re.search(r"F-Score (\d+)/9", d_reason)
            cached_f_score = int(f_score_match.group(1)) if f_score_match else 0
            
            return cached["is_deep_healthy"], d_reason, cached_f_score

        # 2. Proceed to analysis (Need cache update at end)
        is_healthy, h_reason = await self.evaluate_health(ticker)
        
        is_deep = True
        d_reason_parts = []

        if self.fmp_key:
            try:
                # Fetch Annual Financials, TTM Metrics, Quote, AND Ratios
                financials_task = self.fetch_annual_financials(ticker)
                metrics_task = self._fetch_fmp("key-metrics-ttm", ticker)
                ratios_task = self._fetch_fmp("ratios-ttm", ticker)
                quote_task = self._fetch_fmp("quote", ticker)
                
                financials, metrics_data, ratios_data, quote_data = await asyncio.gather(
                    financials_task, metrics_task, ratios_task, quote_task
                )

                # CHECK FOR FMP DATA FAILURE
                if not financials.get("income") or not metrics_data:
                    logger.warning(f"[{ticker}] ⚠️ FMP Data Incomplete. Triggering Fallback.")
                    raise ValueError("Incomplete FMP Data")

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

                # --- D. Quality Score ---
                ratios = ratios_data[0] if ratios_data else {}
                metrics = metrics_data[0] if metrics_data else {}
                quality_score = self.calculate_quality_score(ratios, metrics, financials)

                # --- Rating Logic ---
                # 1. Financial Strength (F-Score)
                if f_score < 4:
                    is_deep = False
                    d_reason_parts.append(f"Weak Financials (F-Score {f_score}/9)")
                else:
                    d_reason_parts.append(f"F-Score {f_score}/9")

                # Quality Score
                d_reason_parts.append(f"Quality {quality_score}/100")
                if quality_score < 40:
                    is_deep = False
                    d_reason_parts.append("Low Quality")

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
                logger.error(f"[{ticker}] ⚠️ Deep Health Check Failed (FMP): {e}")
                # FALLBACK TO BASIC HEALTH IF FMP FAILS
                if is_healthy:
                    d_reason = "Basic Health Only (FMP Failed)"
                    # Set a passing F-Score (5/9) to avoid blocking trades due to API failure
                    # We assume "Innocent until proven guilty" if basic health passes
                    f_score = 5
                else:
                    d_reason = f"Unhealthy Basic (FMP Failed): {h_reason}"
                    is_deep = False
        else:
            # NO FMP KEY -> Check basic health only
            if is_healthy:
                d_reason = "Basic Health Only (No FMP Key)"
                f_score = 5 # Pass if basic health is good
            else:
                d_reason = f"Unhealthy Basic: {h_reason}"
                is_deep = False
        
        # 3. Cache Result (with metrics)
        metrics_snapshot = {
            "pe": float(ratios.get("priceToEarningsRatioTTM", 0) or 0),
            "eps": float(ratios.get("netIncomePerShareTTM", 0) or 0),
            "f_score": f_score,
            "quality_score": quality_score,
            "rev_growth": rev_growth,
            "fair_value": fair_value,
            "price": price,
            "raw_ratios": ratios,  # Archive ALL raw FMP data
            "raw_metrics": metrics
        }
        await asyncio.to_thread(self._save_to_cache, ticker, is_healthy, h_reason, is_deep, d_reason, metrics_snapshot)
        
        return is_deep, d_reason, f_score
