
import logging
from alpha_vantage.fundamentaldata import FundamentalData
import os

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FundamentalAgent")

class FundamentalAgent:
    def __init__(self):
        self.api_key = os.getenv("ALPHA_VANTAGE_KEY")
        if not self.api_key:
            logger.warning(
                "⚠️ ALPHA_VANTAGE_KEY not found. Fundamental analysis disabled."
            )
            self.fd = None
        else:
            self.fd = FundamentalData(key=self.api_key, output_format="json")
            logger.info("✅ Alpha Vantage Connected")

    def get_fundamentals(self, ticker: str):
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

    def evaluate_health(self, ticker: str):
        """
        Returns a simplified health check tuple: (is_healthy: bool, reason: str)
        Rule: Healthy if PE < 60 (Tech adjusted) and EPS > 0.
        """
        data = self.get_fundamentals(ticker)
        if not data:
            return True, "No Data (Skipped)"  # Default to safe if API fails

        pe = data["pe_ratio"]
        eps = data["eps"]

        # 1. Profitability Check
        if eps <= 0:
            return False, f"Unprofitable (EPS {eps})"

        # 2. Valuation Check (Loose for Tech)
        if pe > 100:
            return False, f"Overvalued (PE {pe} > 100)"

        return True, f"Healthy (PE {pe}, EPS {eps})"

    def get_financial_statements(self, ticker: str):
        """
        Fetches Income Statement, Balance Sheet and Cash Flow.
        Uses annual data for balance sheet and quarterly for income trend.
        """
        if not self.fd:
            return None

        try:
            logger.info(f"📡 Fetching deep financials for {ticker}...")
            # We fetch annual for balance sheet (stability) 
            # and quarterly for income (recent trend)
            income_q, _ = self.fd.get_income_statement_quarterly(symbol=ticker)
            if isinstance(income_q, str) and "Alpha Vantage! Please consider" in income_q:
                 logger.error(f"❌ Alpha Vantage Rate Limit Hit (Income Q): {income_q}")
                 return None
            logger.info(f"✅ {ticker} Income Statement (Q) fetched")
            
            balance_a, _ = self.fd.get_balance_sheet_annual(symbol=ticker)
            if isinstance(balance_a, str) and "Alpha Vantage! Please consider" in balance_a:
                 logger.error(f"❌ Alpha Vantage Rate Limit Hit (Balance A): {balance_a}")
                 return None
            logger.info(f"✅ {ticker} Balance Sheet (A) fetched")
            
            cash_a, _ = self.fd.get_cash_flow_annual(symbol=ticker)
            logger.info(f"✅ {ticker} Cash Flow (A) fetched")

            return {"income_q": income_q, "balance_a": balance_a, "cash_a": cash_a}
        except Exception as e:
            logger.error(f"❌ Failed to fetch financial statements for {ticker}: {e}")
            return None

    def evaluate_deep_health(self, ticker: str):
        """
        Calculates Solvency and Growth Stability.
        Returns (is_deep_healthy: bool, reason: str)
        """
        stats = self.get_financial_statements(ticker)
        if not stats or not stats.get("balance_a") or not stats.get("income_q"):
            return True, "No Statement Data (Skipped)"

        try:
            # 1. Solvency: Current Ratio (Current Assets / Current Liabilities)
            # Alpha Vantage returns a list of reports under 'annualReports'
            reports = stats["balance_a"].get("annualReports", [])
            if not reports:
                return True, "No Balance Sheet reports (Skipped)"
                
            recent_balance = reports[0]
            current_assets = float(recent_balance.get("totalCurrentAssets", 0) or 0)
            current_liabilities = float(
                recent_balance.get("totalCurrentLiabilities", 0) or 0
            )

            current_ratio = (
                current_assets / current_liabilities if current_liabilities > 0 else 1.0
            )

            # 2. Debt/Equity (Total Liabilities / Total Shareholder Equity)
            total_liabilities = float(recent_balance.get("totalLiabilities", 0) or 0)
            equity = float(recent_balance.get("totalShareholderEquity", 0) or 1)
            de_ratio = total_liabilities / equity if equity != 0 else 0

            # 3. Growth Stability: Net Income trend (Last 4 quarters)
            q_reports = stats["income_q"].get("quarterlyReports", [])
            if not q_reports:
                 return True, "No Income Statement reports (Skipped)"
                 
            recent_income_q = q_reports[:4]
            net_incomes = [
                float(q.get("netIncome", 0) or 0) for q in recent_income_q
            ]
            is_profitable_trend = all(ni > 0 for ni in net_incomes)

            # --- Safety Gates ---
            msg = f"Deep Health OK (CR={current_ratio:.2f}, D/E={de_ratio:.2f})"
            
            if current_ratio < 0.8:
                return False, f"Liquidity Crisis (Current Ratio {current_ratio:.2f})"

            if de_ratio > 3.0:
                return False, f"High Leverage (D/E {de_ratio:.2f})"

            if not is_profitable_trend:
                return False, "Unstable Earnings (Loss in recent quarters)"

            logger.info(f"📊 {ticker}: {msg}")
            return True, msg

        except (IndexError, KeyError, ValueError, TypeError) as e:
            logger.error(f"⚠️ Error parsing financials for {ticker}: {e}")
            return True, "Parsing Error (Skipped)"
