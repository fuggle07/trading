# System Architecture: Autonomous Trading Bot

This document outlines the architecture, components, and logic of the autonomous trading system currently deployed on Google Cloud Platform (GCP).

## 1. High-Level Overview

The system is a cloud-native, event-driven trading bot designed to:
1.  **Ingest Market Data**: Historical prices (Alpaca) and News Sentiment (Finnhub).
2.  **Analyze**: Compute technical indicators and AI-driven sentiment analysis.
3.  **Decide**: Generate BUY/SELL/HOLD signals based on a hybrid strategy.
4.  **Execute**: Place paper trades via Alpaca and simulate execution internally.
5.  **Track**: Persist all data, decisions, and performance metrics to BigQuery.

## 2. Architecture Diagram

```mermaid
graph TD
    subgraph "External APIs"
        Alpaca[Alpaca API<br>(Market Data & Execution)]
        Finnhub[Finnhub API<br>(News Sentiment)]
        Alpha[Alpha Vantage<br>(Fundamental Data)]
        Vertex[Vertex AI<br>(Gemini 1.5 Pro)]
    end

    subgraph "Cloud Run Service (The Bot)"
        Main[main.py<br>(Orchestrator)]
        Signal[SignalAgent<br>(Strategy Logic)]
        Exec[ExecutionManager<br>(Order Routing)]
        Port[PortfolioManager<br>(State & Ledger)]
        Port[PortfolioManager<br>(State & Ledger)]
        Sent[SentimentAnalyzer<br>(AI Analysis)]
        Fund[FundamentalAgent<br>(Value Analysis)]
    end

    subgraph "Google Cloud Data"
        BQ_Exec[(BigQuery<br>executions)]
        BQ_Port[(BigQuery<br>portfolio)]
        BQ_Logs[(BigQuery<br>watchlist_logs)]
        BQ_Perf[(BigQuery<br>performance_logs)]
    end

    %% Data Flow
    Alpaca -->|Daily Candles| Main
    Finnhub -->|News & Score| Main
    Alpha -->|PE/EPS Data| Main
    Main -->|News Context| Vertex
    Vertex -->|AI Reasoning| Sent
    Sent -->|Sentiment Score| Signal
    Main -->|Health Check| Fund
    Fund -->|Value Score| Signal

    Main -->|Market Data| Signal
    Signal -->|Trade Signal| Exec

    Exec -->|Order Request| Alpaca
    Exec -->|Trade Details| BQ_Exec
    Exec -->|Ledger Update| Port

    Port <-->|Sync State| BQ_Port
    Main -->|Log Metrics| BQ_Logs
    Main -->|Log Equity| BQ_Perf
```

## 3. Core Components

### A. Orchestrator (`main.py`)
- **Role**: The central nervous system.
- **Function**:
    - Initializes all managers and API clients.
    - Loops through the watchlist (NVDA, AAPL, TSLA, MSFT, AMD).
    - Fetches data from Alpaca and Finnhub.
    - Coordinates the flow: Data -> Signal -> Execution -> Logging.
    - Calculates and logs total portfolio equity at the end of each cycle.

### B. Signal Agent (`signal_agent.py`)
- **Role**: The strategist.
- **Logic**: Hybrid Technical + Fundamental(Sentiment).
- **Strategy Pipeline**:
    1.  **Holiday Filter**: Skips processing if the market is closed.
    2.  **Volatility Gate**: Skips trading if price volatility > 15% (Safety).
    3.  **Technical Signal**:
        - **Golden Cross**: BUY if SMA-20 crosses *above* SMA-50.
        - **Death Cross**: SELL if SMA-20 crosses *below* SMA-50.
    4.  **Sentiment Filter**:
        - Rejects BUY signals if `Sentiment Score < -0.5` (Negative News).
    5.  **Stop Loss**:
        - **Hard Exit**: SELL if `Current Price < Avg Entry Price * 0.90` (10% Loss).

### C. Execution Manager (`execution_manager.py`)
- **Role**: The trader.
- **Function**:
    - **Validation**: Checks `PortfolioManager` for sufficient Cash (for BUY) or Holdings (for SELL).
    - **Execution**:
        - Submits **Market Orders** to Alpaca (Paper Trading).
    - **Logging**: Records every trade (attempted and filled) to `trading_data.executions`.

### D. Portfolio Manager (`portfolio_manager.py`)
- **Role**: The accountant.
- **Function**:
    - Manages the internal ledger in BigQuery (`trading_data.portfolio`).
    - **Unified Cash Pool**: Manages a single 'USD' asset row for all purchasing power.
    - **Asset Tracking**: Tracks holdings and **Weighted Average Cost (WAC)** per ticker.
    - **Equity Calculation**: Computes Real-time Total Equity = `Cash + (Holdings * Current Price)`.

### E. Sentiment Analyzer (`sentiment_analyzer.py`)
- **Role**: The analyst.
- **Function**:
    - Uses Google's **Gemini 1.5** via Vertex AI.
    - Analyzes raw news headlines/summaries to derive a nuanced sentiment score (-1 to +1).
    - Provides reasoning for the score (e.g., "Regulatory concerns outweigh earnings beat").

### F. Fundamental Agent (`fundamental_agent.py`)
- **Role**: The value investor.
- **Function**:
    - **Source**: Alpha Vantage API.
    - **Logic**: Checks for basic financial health (PE Ratio, EPS).
    - **Filter**: Rejects BUY signals for unprofitable companies (EPS < 0) or extreme bubbles (PE > 100).

## 4. Key Data Flows

### 1. The Audit Cycle (Every ~1-5 mins)
1.  **Fetch**: Retrieve last 60 days of daily candles from Alpaca.
2.  **Compute**: Calculate SMA-20, SMA-50, Bollinger Bands.
3.  **Sense**: Fetch news sentiment & Fundamental Health (PE/EPS).
4.  **Evaluate**: `SignalAgent` determines action (e.g., BUY NVDA).
5.  **Execute**: `ExecutionManager` routes order to Alpaca.
6.  **Record**: Trade logged to BigQuery; Portfolio updated.
7.  **Monitor**: Total Equity calculated and logged to `performance_logs`.

### 2. Infrastructure (Terraform)
- **Cloud Run**: Hosts the Python bot container.
- **Cloud Scheduler**: Triggers the bot execution via HTTP POST.
- **BigQuery**: Warehouses all structured data (Signals, Executions, Portfolio, Logs).
- **Secret Manager**: Securely stores API Keys (Alpaca, Finnhub).
