# System Architecture: Autonomous Trading Bot

This document outlines the architecture, components, and logic of the autonomous trading system currently deployed on Google Cloud Platform (GCP).

## 1. High-Level Overview

The system is a cloud-native, event-driven trading bot designed to:
1.  **Ingest Market Data**: Historical prices (Alpaca) and News (Finnhub).
2.  **Analyze**: Compute technical indicators, AI-driven sentiment, and fundamental health.
3.  **Decide**: Generate BUY/SELL/HOLD signals based on a hybrid technical + fundamental strategy.
4.  **Execute**: Place paper trades via Alpaca and update the internal BigQuery ledger.
5.  **Reconcile**: Sync the BigQuery ledger against Alpaca's source-of-truth after each cycle.
6.  **Track**: Persist all data, decisions, and performance metrics to BigQuery and Cloud Monitoring.

## 2. Architecture Diagram

```mermaid
graph TD
    subgraph "External APIs"
        Alpaca["Alpaca API<br>(Market Data & Execution)"]
        Finnhub["Finnhub API<br>(News & Macro Fallback)"]
        FMP["Financial Modeling Prep<br>(FMP Stable API — Fundamentals, Technicals, Insider Data)"]
        Vertex["Vertex AI<br>(Gemini 2.0 Flash)"]
    end

    subgraph "Cloud Run Service (The Bot)"
        Main["main.py<br>(Orchestrator)"]
        Signal["SignalAgent<br>(Strategy Logic)"]
        Exec["ExecutionManager<br>(Order Routing)"]
        Sent["SentimentAnalyzer<br>(AI Analysis)"]
        Fund["FundamentalAgent<br>(Value & Health Analysis)"]
        Recon["PortfolioReconciler<br>(Alpaca Sync)"]
    end

    subgraph "Google Cloud Data"
        BQ_Exec[("BigQuery<br>executions")]
        BQ_Port[("BigQuery<br>portfolio")]
        BQ_Logs[("BigQuery<br>watchlist_logs")]
        BQ_Perf[("BigQuery<br>performance_logs")]
        BQ_Macro[("BigQuery<br>macro_snapshots")]
    end

    %% Data Flow
    Alpaca -->|Daily Candles & Live Quotes| Main
    Finnhub -->|News Headlines| Main
    FMP -->|Technicals, Financials, Insider Trades| Fund
    Main -->|News + Context| Vertex
    Vertex -->|AI Reasoning + Score| Sent
    Sent -->|Sentiment Score| Signal
    Main -->|Health Check| Fund
    Fund -->|F-Score, Quality, Deep Health| Signal

    Main -->|Market Data + Intel| Signal
    Signal -->|Trade Signal| Exec

    Exec -->|Market Order| Alpaca
    Exec -->|Trade Record| BQ_Exec
    Exec -->|Ledger Update| BQ_Port

    Recon -->|Overwrite with Actuals| BQ_Port
    Alpaca -->|Position & Cash Truth| Recon

    Main -->|Watchlist Metrics| BQ_Logs
    Main -->|Equity Snapshot| BQ_Perf
    Main -->|Macro Context| BQ_Macro
```

## 3. Core Components

### A. Orchestrator (`main.py`)
- **Role**: The central nervous system.
- **Function**:
    - Initializes all managers and API clients.
    - Runs the watchlist: `TSLA, NVDA, AMD, MU, PLTR, COIN, META, AAPL, MSFT, GOLD, AMZN, AVGO, ASML, LLY, LMT` (configurable via `BASE_TICKERS` env var).
    - **Hedge Auto-Injection**: Automatically includes `PSQ` in every audit cycle for protection.
    - Fetches data in parallel: Alpaca candles, FMP technicals, Finnhub news, fundamental health, macro context.
    - Coordinates: Data → Signal → Execution → Logging.
    - **Macro Hedging**: Evaluates market distress and scales inverse positions accordingly.
    - Exposes `/equity` endpoint for real-time live portfolio equity (bypasses stale logs).

### B. Signal Agent (`signal_agent.py`)
- **Role**: The strategist.
- **Logic**: Hybrid Technical + Fundamental + Sentiment pipeline with **Dynamic Risk Scaling**.
- **Strategy Pipeline**:
    1.  **Holiday Filter**: Skips processing if the market is closed.
    2.  **Volatility Gate**: Skips trading if Bollinger Band width > threshold (default 35%).
    3.  **Institutional Exit Logic** (runs before buy signals):
        - **Partial Scaling**: SELL 50% of the position if profit hits **+5%**.
        - **Trailing Stop-Loss**: Activates once profit hits **+3%**. Exits the position if the price pulls back **2% from its High Water Mark (HWM)**.
        - **Sentiment Exit**: SELL if Sentiment < -0.4.
        - **RSI Overbought Exit**: SELL if RSI ≥ 85.
    4.  **Macro Hedging**: 
        - Determines hedge status based on VIX and QQQ Trend.
        - **AI-Aware**: Consults Gemini sentiment for PSQ before entering a hedge (Veto power).
        - **Caution (2%)**, **Fear (5%)**, or **Panic (10%)** target percentages.
    5.  **Dynamic Position Sizing**: Calculates optimal allocation (up to 40% cap) based on **Conviction**, **VIX**, and **Band Width**.
    6.  **Technical Baseline**:
        - BUY if `Price ≤ Lower Band` AND Sentiment ≥ 0.4.
        - SELL if `Price ≥ Upper Band`.
        - RSI Oversold Aggression: BUY if RSI ≤ 30 AND Sentiment > 0.4.
    7.  **Low Exposure Aggression** (`PROACTIVE_WARRANTED_ENTRY`): If portfolio < 85% invested, allows entry into leaders even if not at technical extremes.
    8.  **Fundamental Gatekeeper**: Blocks BUY if F-Score is critically low or basic health fails.
    9.  **Star Rating**: Flags elite opportunities (AI ≥ 85, F-Score ≥ 7) with a minimum 20% capital floor.

### C. Execution Manager (`execution_manager.py`)
- **Role**: The trader.
- **Function**:
    - Validates `PortfolioManager` for sufficient Cash (BUY) or Holdings (SELL).
    - Supports **Partial Sells** (SELL_PARTIAL_50) for scaling out.
    - Submits **Market Orders** to Alpaca (Paper Trading mode).
    - Records every trade to `trading_data.executions` in BigQuery.

### D. Portfolio Manager (`portfolio_manager.py`)
- **Role**: The accountant.
- **Function**:
    - Manages the internal BigQuery ledger (`trading_data.portfolio`).
    - **Unified Cash Pool**: Single 'USD' row holds all purchasing power.
    - **Tracking**: Persistent tracking of **High Water Marks** and **Scaled-Out status** for advanced exit logic.
    - **Asset Tracking**: Tracks holdings and **Weighted Average Cost (WAC)** per ticker.

### E. Portfolio Reconciler (`portfolio_reconciler.py`)
- **Role**: The auditor.
- **Function**:
    - Runs at the **start** of every audit cycle and **after trades execute**.
    - Overwrites the BigQuery `portfolio` table with Alpaca's actual cash and positions.
    - Syncs `executions` table with real fill prices and quantities from Alpaca.
    - Prevents ledger drift from slippage, fees, or missed signals.

### F. Sentiment Analyzer (`sentiment_analyzer.py`)
- **Role**: The news analyst.
- **Function**:
    - Uses Google's **Gemini 2.0 Flash** via Vertex AI.
    - Synthesizes news headlines, RSI, SMA stretch, analyst consensus, and **Insider Trading Momentum** into a score (-1.0 to +1.0).
    - Returns a reasoning string explaining the score.

### G. Fundamental Agent (`fundamental_agent.py`)
- **Role**: The value investor.
- **Primary Source**: **Financial Modeling Prep (FMP) Stable API**.
- **Function**:
    - **Stable Endpoints**: Uses modern `/stable/` endpoints to resolve legacy compatibility errors.
    - **VIX Isolation**: Independent fetching of ^VIX with proxy fallback (Finnhub/VXX).
    - **Basic Health**: PE Ratio and EPS checks (via FMP + Finnhub fallback).
    - **Deep Health** (Piotroski F-Score): Analyzes income, balance sheet, and cash flow statements (annual, 2-year).
    - **Technical Indicators**: RSI, SMA-20, SMA-50 via FMP stable endpoints.
    - **Macro Context**: VIX, SPY/QQQ performance, QQQ SMA-50 trend, treasury rates.
    - **Caching**: Results are cached in BigQuery to reduce API calls.

### H. Ticker Ranker (`ticker_ranker.py`)
- **Role**: The pre-market filter.
- **Function**: Runs a daily 9:15 AM ET job to establish a "Confidence Baseline" (AI Conviction Score) for all tickers before trading opens.

### I. Feedback Agent (`feedback_agent.py`)
- **Role**: The learner.
- **Function**: Post-cycle hindsight analysis; generates "lessons learned" that influence future sentiment scoring.

## 4. Key Data Flows

1.  **Phase 0 — Reconciliation**: `PortfolioReconciler` syncs BigQuery ← Alpaca.
2.  **Phase 1 — Intelligence Gathering**: Parallel fetch of quotes, news, fundamentals, macro (including **PSQ** auto-inclusion).
3.  **Phase 1.5 — Hedge Check**: Strategic evaluation of market distress and PSQ scaling (Entry/Top-up/Clear).
4.  **Phase 2 — Portfolio Analysis**: Calculates dynamic position sizes; identifying swaps.
5.  **Phase 3 — Execution**: SELLs first (including partial profit-takes), then BUYs.
6.  **Phase 4 — Post-Trade Reconciliation**: 45s wait for Alpaca fills, then re-sync.
7.  **Phase 5 — Reflection**: Feedback Agent logs hindsight analysis.

## 5. Infrastructure (Terraform)

- **Cloud Run**: Hosts the Python bot container (`trading-audit-agent`).
- **Cloud Scheduler**: Triggers the bot via HTTP POST on a schedule.
- **BigQuery**: Warehouses all structured data (Tables: `portfolio`, `executions`, `watchlist_logs`, `performance_logs`, `macro_snapshots`).
- **Secret Manager**: Stores API Keys (`FMP_KEY`, `ALPACA_API_KEY`, `ALPACA_API_SECRET`, `EXCHANGE_API_KEY`).
- **Cloud Monitoring**: Custom dashboard (`Aberfeldie Node: NASDAQ Monitor`) with aggregated log-based metrics.
