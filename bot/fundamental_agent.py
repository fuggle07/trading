import os
import asyncio
import aiohttp
from datetime import datetime, timedelta
from google.cloud import bigquery
from bot.telemetry import logger

PROJECT_ID = os.getenv("PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")


class FundamentalAgent:
    def __init__(self, finnhub_client=None):
        self.fmp_key = os.getenv("FMP_KEY")
        self.finnhub_client = finnhub_client  # Keep as backup if needed
        self.av_key = os.getenv("ALPHA_VANTAGE_KEY")
        self.bq_client = bigquery.Client(project=PROJECT_ID) if PROJECT_ID else None

        if not self.fmp_key:
            logger.warning("⚠️ FMP_KEY not found. Fundamental analysis restricted.")
        else:
            logger.info("✅ Financial Modeling Prep (FMP) Connected")

    async def _fetch_fmp(
        self, endpoint: str, ticker: str, params: dict = None, version: str = "v3"
    ):
        """
        Helper to fetch data from FMP API.
        - v3/v4: Mostly path-based (e.g., /v3/income-statement/AAPL)
        - stable: Mostly query-based (e.g., /stable/technical-indicators/sma?symbol=AAPL)
        """
        if not self.fmp_key:
            return None

        # Build URL and Query Params based on version
        query_params = {"apikey": self.fmp_key}
        if params:
            query_params.update(params)

        if version == "stable":
            # Stable indicators usually require ?symbol=TICKER
            url = f"https://financialmodelingprep.com/{version}/{endpoint}"
            if ticker:
                query_params["symbol"] = ticker
        else:
            # v3/v4 usually uses path-based (e.g., /v3/quote/AAPL)
            if ticker:
                url = f"https://financialmodelingprep.com/{version}/{endpoint}/{ticker}"
            else:
                url = f"https://financialmodelingprep.com/{version}/{endpoint}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, params=query_params, timeout=10
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data:
                            return data
                    elif response.status == 403:
                        # Premium endpoint not available on free FMP tier — skip silently
                        logger.debug(
                            f"[{ticker}] ⚠️ FMP {endpoint}: 403 (premium tier required, skipping)"
                        )
                    else:
                        logger.error(
                            f"[{ticker}] ❌ FMP Error {endpoint}: {response.status}"
                        )
        except Exception as e:
            logger.error(f"[{ticker}] ⚠️ FMP Exception {endpoint}: {e}")
        return None

    async def _fetch_alphavantage(self, function: str, params: dict = None):
        """Helper to fetch data from AlphaVantage API."""
        if not self.av_key:
            return None

        url = "https://www.alphavantage.co/query"
        query_params = {"function": function, "apikey": self.av_key}
        if params:
            query_params.update(params)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, params=query_params, timeout=10
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(
                            f"❌ AlphaVantage Error {function}: {response.status}"
                        )
        except Exception as e:
            logger.error(f"⚠️ AlphaVantage Exception {function}: {e}")
        return None

    async def get_technical_indicator(
        self,
        ticker: str,
        indicator_type: str,
        period: int = 20,
        timeframe: str = "1day",
    ):
        """
        Fetches technical indicators from FMP (e.g., sma, rsi, ema).
        URL: https://financialmodelingprep.com/stable/technical-indicators/{type}?symbol={ticker}&periodLength={period}&timeframe={timeframe}&apikey={key}
        """
        endpoint = f"technical-indicators/{indicator_type}"
        params = {"periodLength": period, "timeframe": timeframe}
        data = await self._fetch_fmp(endpoint, ticker, params=params, version="stable")
        if data and isinstance(data, list):
            # FMP returns a list of indicators, we usually want the latest one
            return data[0]
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
                logger.info(
                    f"[{ticker}] 📊 {ticker} Fundamentals (FMP): PE={data['pe_ratio']:.2f}, EPS={data['eps']:.2f}"
                )

        # 2. Fallback to Finnhub if FMP fails
        if not data and self.finnhub_client:
            try:
                logger.info(
                    f"[{ticker}] 📡 Falling back to Finnhub for {ticker} fundamentals..."
                )
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
                        "market_cap": int(metric.get("marketCapitalization", 0) or 0)
                        * 1_000_000,
                    }
                    logger.info(
                        f"[{ticker}] 📊 {ticker} Fundamentals (Finnhub): PE={data['pe_ratio']}, EPS={data['eps']}"
                    )
            except Exception as e:
                logger.error(f"[{ticker}] ❌ Finnhub Fallback failed: {e}")

        return data

    async def get_intelligence_metrics(self, ticker: str) -> dict:
        """
        Fetches 'Soft' context: Analyst Consensus and Institutional Flow.
        """
        intelligence = {
            "analyst_consensus": "Neutral",
            "institutional_momentum": "Neutral",
        }

        if not self.fmp_key:
            return intelligence

        try:
            # 1. Analyst Ratings (FMP /analyst-stock-recommendations)
            ratings_task = self._fetch_fmp("analyst-stock-recommendations", ticker)

            # 2. Institutional Ownership %
            inst_task = self._fetch_fmp(
                "institutional-ownership/symbol-ownership-percent", ticker
            )

            ratings_data, inst_data = await asyncio.gather(ratings_task, inst_task)

            if ratings_data and isinstance(ratings_data, list):
                r = ratings_data[0]
                intelligence["analyst_consensus"] = (
                    f"{r.get('recommendation', 'Neutral')} (Consensus of {r.get('analystRatingsTotal', 0)} analysts)"
                )

            if inst_data and isinstance(inst_data, list):
                pct = float(inst_data[0].get("totalOwnershipPercentage", 0) or 0)
                intelligence["institutional_momentum"] = (
                    f"{pct:.1f}% Institutional Ownership"
                )

        except Exception as e:
            logger.error(f"[{ticker}] ⚠️ Failed to fetch intelligence metrics: {e}")

        return intelligence

    async def get_economic_calendar(self, days_ahead: int = 7) -> list:
        """
        Fetches upcoming High-Impact US economic events.
        Fallbacks to Finnhub if FMP fails.
        """
        # 1. Try FMP (v3)
        if self.fmp_key:
            data = await self._fetch_fmp("economic_calendar", "", version="v3")
            if data and isinstance(data, list):
                high_impact = [
                    ev
                    for ev in data
                    if ev.get("country") == "US" and ev.get("impact") == "High"
                ]
                if high_impact:
                    return high_impact[:5]

        # 2. Fallback to Finnhub
        if self.finnhub_client:
            try:
                from_date = datetime.now().strftime("%Y-%m-%d")
                to_date = (datetime.now() + timedelta(days=days_ahead)).strftime(
                    "%Y-%m-%d"
                )

                # Finnhub SDK call
                res = await asyncio.to_thread(
                    self.finnhub_client.calendar_economic, _from=from_date, to=to_date
                )
                if res and "economicCalendar" in res:
                    events = res["economicCalendar"]
                    # Filter for High impact US
                    high_impact = [
                        e
                        for e in events
                        if e.get("impact") == "high" and e.get("country") == "US"
                    ]
                    return high_impact[:5]
            except Exception as e:
                logger.error(f"⚠️ Finnhub Economic Calendar Fallback failed: {e}")

        return []

    async def get_treasury_rates(self) -> dict:
        """
        Fetches the latest US Treasury Rates (v4 /treasury_rates).
        Fallbacks to Finnhub (MA-USA codes) if FMP fails.
        """
        # 1. Try FMP (v4)
        if self.fmp_key:
            data = await self._fetch_fmp("treasury_rates", "", version="v4")
            if data and isinstance(data, list):
                latest = data[0]
                return {
                    "date": latest.get("date"),
                    "10Y": float(latest.get("year10", 0) or 0),
                    "2Y": float(latest.get("year2", 0) or 0),
                }

        # 2. Fallback to Finnhub (Macro Data)
        if self.finnhub_client:
            try:
                # DGS10 is the FRED code for 10Y Yield.
                # Finnhub often maps these to MA-USA codes.
                # MA-USA-347 is often 'Long Term Government Bond Yields: 10-year: Main (Including Benchmark) for the United States'
                res = await asyncio.to_thread(
                    self.finnhub_client.economic_data, code="MA-USA-347"
                )
                if res and "data" in res and res["data"]:
                    latest = res["data"][0]  # Usually latest is first
                    return {
                        "date": latest.get("date"),
                        "10Y": float(latest.get("value", 0) or 0),
                        "source": "Finnhub/FRED",
                    }
            except Exception as e:
                logger.error(f"⚠️ Finnhub Treasury Fallback failed: {e}")

        # 3. Fallback to AlphaVantage (Free Treasury Yields)
        if self.av_key:
            try:
                # Daily 10Y Yield
                av_res = await self._fetch_alphavantage(
                    "TREASURY_YIELD", {"maturity": "10year", "interval": "daily"}
                )
                if av_res and "data" in av_res and av_res["data"]:
                    latest = av_res["data"][0]
                    return {
                        "date": latest.get("date"),
                        "10Y": float(latest.get("value", 0) or 0),
                        "source": "AlphaVantage",
                    }
            except Exception as e:
                logger.error(f"⚠️ AlphaVantage Treasury Fallback failed: {e}")

        return {}

    async def get_market_indices(self) -> dict:
        """
        Fetches VIX (Fear Index) and other major indices via /quote.
        Fallbacks to Finnhub Index Quotes or Volatility ETF (VXX) if indices are restricted.
        """
        results = {"vix": 0.0, "spy_perf": 0.0, "qqq_perf": 0.0}

        # 1. Try FMP (v3)
        if self.fmp_key:
            indices = "^VIX,SPY,QQQ"
            data = await self._fetch_fmp("quote", indices, version="v3")
            if data and isinstance(data, list):
                for item in data:
                    sym = item.get("symbol")
                    if sym == "^VIX":
                        results["vix"] = float(item.get("price", 0) or 0)
                    elif sym == "SPY":
                        results["spy_perf"] = float(
                            item.get("changesPercentage", 0) or 0
                        )
                    elif sym == "QQQ":
                        results["qqq_perf"] = float(
                            item.get("changesPercentage", 0) or 0
                        )
                if results["vix"] > 0:
                    return results

        # 2. Fallback to Finnhub
        if self.finnhub_client:
            try:
                # Try Index Quote for ^VIX first
                vix_res = await asyncio.to_thread(self.finnhub_client.quote, "^VIX")
                if vix_res and vix_res.get("pc", 0) > 0:
                    results["vix"] = float(vix_res["c"])
                else:
                    # PROXY: Use VXX (Volatility ETF) as a fear proxy if the actual index is restricted
                    vxx_res = await asyncio.to_thread(self.finnhub_client.quote, "VXX")
                    if vxx_res and vxx_res.get("pc", 0) > 0:
                        results["vix_proxy_vxx"] = float(vxx_res["c"])
                        logger.info("📉 Using VXX as Volatility Proxy (VIX restricted)")

                # Fetch SPY/QQQ performance (These are usually free as they are ETFs)
                spy_task = asyncio.to_thread(self.finnhub_client.quote, "SPY")
                qqq_task = asyncio.to_thread(self.finnhub_client.quote, "QQQ")

                spy_res, qqq_res = await asyncio.gather(spy_task, qqq_task)

                if spy_res and "dp" in spy_res:
                    results["spy_perf"] = float(spy_res["dp"])
                if qqq_res and "dp" in qqq_res:
                    results["qqq_perf"] = float(qqq_res["dp"])

            except Exception as e:
                logger.error(f"⚠️ Finnhub Indices Fallback failed: {e}")

        return results

    def _get_cached_evaluation(self, ticker: str):
        """Checks BigQuery for today's evaluation of this ticker."""
        client = self.bq_client
        if not client:
            return None

        query = f"""
        SELECT is_healthy, health_reason, is_deep_healthy, deep_health_reason, metrics_json
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

    def _save_to_cache(
        self,
        ticker: str,
        is_healthy: bool,
        h_reason: str,
        is_deep: bool,
        d_reason: str,
        metrics: dict = None,
    ):
        """Persists evaluation results to BigQuery."""
        client = self.bq_client
        if not client:
            return

        import json

        metrics_json = json.dumps(metrics) if metrics else None

        rows_to_insert = [
            {
                "timestamp": datetime.now().isoformat(),
                "ticker": ticker,
                "is_healthy": is_healthy,
                "health_reason": h_reason,
                "is_deep_healthy": is_deep,
                "deep_health_reason": d_reason,
                "metrics_json": metrics_json,
            }
        ]
        try:
            table_id = f"{PROJECT_ID}.trading_data.fundamental_cache"
            client.insert_rows_json(table_id, rows_to_insert)
            logger.info(f"[{ticker}] ✅ Cached fundamental results for {ticker}")
        except Exception as e:
            logger.error(f"[{ticker}] ❌ Failed to cache results: {e}")

    async def evaluate_health(self, ticker: str):
        """
        Returns (is_healthy, reason).
        Direct call for evaluate_health remains for separate uses,
        but main.py will move to a consolidated call in evaluate_deep_health.
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

    async def fetch_annual_financials(self, ticker):
        """
        Fetches annual financial statements: Income, Balance Sheet, Cash Flow.
        Uses the standard v3 API with a limit of 2 years for YoY comparison.
        """
        financials = {"income": [], "balance": [], "cash": []}
        if not self.fmp_key:
            return financials

        endpoints = {
            "income": "income-statement",
            "balance": "balance-sheet-statement",
            "cash": "cash-flow-statement",
        }

        for key, endpoint in endpoints.items():
            res = await self._fetch_fmp(endpoint, ticker, params={"limit": 2})
            if res and isinstance(res, list):
                financials[key] = res
            else:
                logger.warning(f"[{ticker}] ⚠️ FMP {key} returned no list-based data.")

        return financials

    def calculate_dcf(
        self,
        fcf_ttm,
        shares_outstanding,
        growth_rate=0.08,
        discount_rate=0.10,
        years=5,
        terminal_growth=0.02,
    ):
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
            current_fcf *= 1 + growth_rate
            discounted_cf = current_fcf / (df_factor**i)
            future_cash_flows.append(discounted_cf)

        # 2. Terminal Value
        terminal_value = (current_fcf * (1 + terminal_growth)) / (
            discount_rate - terminal_growth
        )
        discounted_terminal_value = terminal_value / (df_factor**years)

        # 3. Sum and Divide by Shares
        total_enterprise_value = sum(future_cash_flows) + discounted_terminal_value
        fair_value = total_enterprise_value / shares_outstanding

        return float(round(fair_value, 2))

    def calculate_piotroski_f_score(self, financials, ticker: str):
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
                # Log specific counts to help debug "None" results vs "0"
                logger.debug(f"[{ticker}] F-Score Data Gaps: Inc={len(inc)}, Bal={len(bal)}, Cash={len(cfs)}")
                return None  # Distinguish: None=Missing, 0=Poor Fundamentals

            # Year 0 (Current/Most Recent), Year 1 (Previous)
            i0, i1 = inc[0], inc[1]
            b0, b1 = bal[0], bal[1]
            c0, _c1 = cfs[0], cfs[1]

            # SURGICAL LOGGING: Inspect fields for NVDA/MU to catch schema shifts
            logger.info(f"[{ticker}] F-Score Drilldown: inc0 keys={list(i0.keys())[:5]}")
            logger.debug(f"[{ticker}] i0: NetInc={i0.get('netIncome')}, Rev={i0.get('revenue')}")
            logger.debug(f"[{ticker}] b0: Assets={b0.get('totalAssets')}, Liab={b0.get('totalLiabilities')}")

            # --- Profitability (4 pts) ---
            net_income = float(i0.get("netIncome", 0))
            roa = net_income / float(b0.get("totalAssets", 1))
            cfo = float(c0.get("operatingCashFlow", 0))

            roa_prev = float(i1.get("netIncome", 0)) / float(b1.get("totalAssets", 1))

            if net_income > 0:
                score += 1  # 1. Positive Net Income
            if cfo > 0:
                score += 1  # 2. Positive Operating Cash Flow
            if roa > roa_prev:
                score += 1  # 3. Higher ROA YoY
            if cfo > net_income:
                score += 1  # 4. Cash Flow > Net Income (Quality of Earnings)

            # --- Leverage / Liquidity / Source of Funds (3 pts) ---
            leverage = float(b0.get("totalLiabilities", 0)) / float(
                b0.get("totalAssets", 1)
            )
            leverage_prev = float(b1.get("totalLiabilities", 0)) / float(
                b1.get("totalAssets", 1)
            )

            current_ratio = float(b0.get("totalCurrentAssets", 1)) / float(
                b0.get("totalCurrentLiabilities", 1)
            )
            current_ratio_prev = float(b1.get("totalCurrentAssets", 1)) / float(
                b1.get("totalCurrentLiabilities", 1)
            )

            shares = float(i0.get("weightedAverageShsOut", 0))
            shares_prev = float(i1.get("weightedAverageShsOut", 0))

            if leverage < leverage_prev:
                score += 1  # 5. Lower Leverage
            if current_ratio > current_ratio_prev:
                score += 1  # 6. Higher Current Ratio
            if shares <= shares_prev:
                score += 1  # 7. No Dilution (Shares flat or down)

            # --- Operating Efficiency (2 pts) ---
            gross_margin = (
                float(i0.get("revenue", 1)) - float(i0.get("costOfRevenue", 0))
            ) / float(i0.get("revenue", 1))
            gross_margin_prev = (
                float(i1.get("revenue", 1)) - float(i1.get("costOfRevenue", 0))
            ) / float(i1.get("revenue", 1))

            asset_turnover = float(i0.get("revenue", 0)) / float(
                b0.get("totalAssets", 1)
            )
            asset_turnover_prev = float(i1.get("revenue", 0)) / float(
                b1.get("totalAssets", 1)
            )

            if gross_margin > gross_margin_prev:
                score += 1  # 8. Higher Gross Margin
            if asset_turnover > asset_turnover_prev:
                score += 1  # 9. Higher Asset Turnover

        except Exception as e:
            logger.error(f"F-Score Logic Error: {e}")
            return None

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

        if roe > 0.15:
            score += 10
        elif roe > 0.08:
            score += 5

        if roa > 0.05:
            score += 10
        elif roa > 0.02:
            score += 5

        if gm > 0.40:
            score += 10
        elif gm > 0.20:
            score += 5

        if nm > 0.10:
            score += 10
        elif nm > 0:
            score += 5

        # 2. Safety (30 points)
        # Current Ratio > 1.5 (+10), Debt/Equity < 0.5 (+10), Interest Cov > 5 (+10)
        cr = g(ratios, "currentRatioTTM")
        de = g(ratios, "debtToEquityRatioTTM")
        ic = g(ratios, "interestCoverageRatioTTM")

        if cr > 1.5:
            score += 10
        elif cr > 1.0:
            score += 5

        if de < 0.5:
            score += 10
        elif de < 1.0:
            score += 5

        if ic > 5:
            score += 10
        elif ic > 1:
            score += 5

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

        if 0 < pe < 25:
            score += 10
        elif 0 < pe < 40:
            score += 5

        if 0 < peg < 1.5:
            score += 10
        elif 0 < peg < 2.5:
            score += 5

        if 0 < pfcf < 20:
            score += 10
        elif 0 < pfcf < 30:
            score += 5

        return int(score)

    async def evaluate_deep_health(self, ticker: str):
        """
        Returns (is_healthy, h_reason, is_deep_healthy, d_reason, f_score) 
        using Advanced Fundamental Analysis.
        Integrates DCF, Piotroski F-Score, and Growth.
        Consolidated to check cache once.
        """
        # 1. Check Cache FIRST for everything
        cached = await asyncio.to_thread(self._get_cached_evaluation, ticker)
        if cached:
            logger.info(f"[{ticker}] 💾 Using cached health for {ticker}")
            
            # Extract f_score from metrics_json if available
            import json
            metrics = {}
            f_score = 0
            
            # The get_cached_evaluation query doesn't pull metrics_json? 
            # Let's check the query in _get_cached_evaluation.
            # (Self-correction: I need to check _get_cached_evaluation definition)
            
            # Actually, I'll update _get_cached_evaluation to include metrics_json
            # and then parse it here.
            
            # For now, if we match cache:
            try:
                # We need to extract the F-Score part from the reason if we don't have metrics_json
                import re
                d_reason = cached["deep_health_reason"]
                f_score_match = re.search(r"F-Score (\d+)/9", d_reason)
                f_score = int(f_score_match.group(1)) if f_score_match else 0
            except Exception:
                f_score = 0
                
            return (
                cached["is_healthy"], 
                cached["health_reason"], 
                cached["is_deep_healthy"], 
                cached["deep_health_reason"], 
                f_score
            )

        # 2. No Cache -> Proceed to analysis
        # --- Initialize Variables ---
        is_healthy = True
        h_reason = "Healthy"
        is_deep = True
        d_reason = "Analysis Pending"
        f_score = 0
        d_reason_parts = []

        if self.fmp_key:
            try:
                # Fetch Annual Financials, TTM Metrics, Quote, AND Ratios
                financials_task = self.fetch_annual_financials(ticker)
                metrics_task = self._fetch_fmp("key-metrics-ttm", ticker)
                ratios_task = self._fetch_fmp("ratios-ttm", ticker)
                quote_task = self._fetch_fmp("quote", ticker)

                financials, metrics_data, ratios_data, quote_data = (
                    await asyncio.gather(
                        financials_task, metrics_task, ratios_task, quote_task
                    )
                )

                # CHECK FOR FMP DATA FAILURE
                if not financials.get("income") or not metrics_data:
                    logger.warning(
                        f"[{ticker}] ⚠️ FMP Data Incomplete. Triggering Fallback."
                    )
                    raise ValueError("Incomplete FMP Data")

                price = 0.0
                if quote_data:
                    price = float(quote_data[0].get("price", 0))

                # --- A. Piotroski F-Score ---
                f_score = self.calculate_piotroski_f_score(financials, ticker)

                # --- B. DCF Valuation ---
                fair_value = 0.0
                if metrics_data:
                    m = metrics_data[0]
                    fcf_per_share = float(m.get("freeCashFlowPerShareTTM", 0) or 0)
                    shares_out = float(
                        financials.get("income", [{}])[0].get(
                            "weightedAverageShsOut", 0
                        )
                        or 1
                    )

                    # Estimate Total FCF TTM (Approx)
                    total_fcf = fcf_per_share * shares_out

                    if total_fcf > 0:
                        fair_value = self.calculate_dcf(total_fcf, shares_out)
                        # dcf_upside reserved for future use
                        _ = (fair_value - price) / price if price > 0 else 0

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
                quality_score = self.calculate_quality_score(
                    ratios, metrics, financials
                )

                # --- Rating Logic ---
                # 1. Financial Strength (F-Score)
                # Safeguard against NoneType comparison
                if f_score is not None and f_score < 4:
                    is_deep = False
                    d_reason_parts.append(f"Weak Financials (F-Score {f_score}/9)")
                elif f_score is None:
                    d_reason_parts.append("F-Score N/A (Insufficient Data)")
                else:
                    d_reason_parts.append(f"F-Score {f_score}/9")

                # Quality Score
                d_reason_parts.append(f"Quality {quality_score}/100")
                if quality_score < 40:
                    is_deep = False
                    d_reason_parts.append("Low Quality")

                # 2. Valuation (DCF)
                if price > 0 and fair_value > 0:
                    if price > (fair_value * 1.5):  # 50% premium over fair value
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
                    # Set a "Neutral/Missing" F-Score (None) to avoid blocking trades due to API failure
                    # We assume "Innocent until proven guilty" if basic health passes
                    f_score = None
                else:
                    d_reason = f"Unhealthy Basic (FMP Failed): {h_reason}"
                    is_deep = False
        else:
            # NO FMP KEY -> Check basic health only
            if is_healthy:
                d_reason = "Basic Health Only (No FMP Key)"
                f_score = None  # Neutral if data missing
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
            "raw_metrics": metrics,
        }
        await asyncio.to_thread(
            self._save_to_cache,
            ticker,
            is_healthy,
            h_reason,
            is_deep,
            d_reason,
            metrics_snapshot,
        )

        return is_healthy, h_reason, is_deep, d_reason, f_score
