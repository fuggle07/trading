# Decision Logic: The Aberfeldie Node Strategy

This document explains in plain English how the Aberfeldie Node decides to BUY, SELL, or HOLD a position. The system uses a multi-layered "Decision Tree" that combines technical math, news sentiment, AI conviction, and fundamental health.

---

## 1. The Inputs (What the Bot Sees)

The bot gathers five primary data points for every ticker in its watchlist (`TSLA, NVDA, AMD, MU, PLTR, COIN, META, AAPL, MSFT, GOLD, AMZN, AVGO, ASML, LLY, LMT`):

1.  **Technicals (FMP Stable API)**: Bollinger Bands (SMA-20 ± 2×StdDev) and **RSI (14)** — fetched directly from FMP's stable endpoints.
2.  **Sentiment (Gemini 2.0 Flash)**: Synthesizes news headlines (or general context if news is sparse), RSI, analyst consensus, and **Insider Trading Momentum** into a score from -1 (toxic) to +1 (elite).
3.  **Fundamental Health (FMP Deep Dive)**: Annual income, balance sheet, and cash flow statements. Calculates **Piotroski F-Score (0–9)** and a **Quality Score (0–100)**.
4.  **Intelligence Metrics (FMP Stable API)**: Analyst EPS estimates, price-target consensus, and insider Buy/Sell ratios from the last 100 insider trades.
5.  **Portfolio Context**: Cash available, current exposure (%), and average entry price for held positions.

---

## 2. The Decision Tree (The Logical Flow)

When the bot evaluates a stock (e.g., NVDA), it follows this step-by-step logic:

### Step A: The Exit Override (Institutional Risk Model)
If you already own the stock, the bot checks your P&L **before** looking at new opportunities:
*   **Partial Scaling (+5%)**: If the stock is up 5% from your average cost, the bot **SELLS 50%**. This locks in gains while leaving half exposed to further upside.
*   **Trailing Stop-Loss**: 
    1.  **Activation**: Becomes active once a ticker is up **+3%**.
    2.  **Trigger**: If the price pulls back **2% from its High Water Mark (HWM)**, the bot exits the remaining position.
*   **Sentiment Crash**: If sentiment drops below **-0.4**, the bot exits even if price looks fine.
*   **RSI Overbought (≥ 85)**: Exit to capture extreme momentum exhaustion.

### Step B: The Volatility Filter
*   **Check**: Are the price swings too wild? (Band Width > 35% normally; relaxed to 52.5% when exposure is low).
*   **Action**: If yes, the bot **SITS OUT**. It avoids catching a falling knife.

### Step C: Technical Baseline
*   **IF** Price ≤ Lower Bollinger Band AND Sentiment ≥ 0.4: **Baseline = BUY**.
*   **IF** Price ≥ Upper Bollinger Band: **Baseline = SELL**.
*   **IF** RSI ≤ 30 AND Sentiment > 0.4: **Baseline = RSI_OVERSOLD_BUY** (overrides HOLD).
*   **OTHERWISE**: **Baseline = HOLD**.

### Step D: The Sentiment Gate (For Buying)
*   **Condition**: The **Sentiment Score** must be **≥ 0.4** to permit any BUY signal.
*   **Logic**: We don't buy a dip if the news narrative is currently toxic.

### Step E: Low Exposure Aggression (`PROACTIVE_WARRANTED_ENTRY`)
*   **Condition**: If the portfolio is **< 85% invested**.
*   **Rule Change**: The bot becomes more aggressive. It will BUY on a HOLD technical signal if:
    1.  **Sentiment** ≥ 0.2 (lowered threshold to deploy idle cash into leaders).
    2.  **AI Confidence** ≥ 70.
*   **Signal Name**: Appears in logs as `PROACTIVE_WARRANTED_ENTRY`.

### Step F: The Fundamental Gatekeeper
*   **F-Score Check (0–9, higher is healthier)**:

    | F-Score | Condition | Action |
    | :--- | :--- | :--- |
    | `None` (missing data) | AI Confidence < 70 | REJECT — insufficient data |
    | `None` (missing data) | AI Confidence ≥ 70 AND Sentiment ≥ 0.2 | BUY with reduced conviction (data-missing bypass) |
    | `≤ 1` (critically weak) | AI ≥ 70 AND Sentiment ≥ 0.4 | BUY as turnaround play (high-confidence override) |
    | `≤ 1` (critically weak) | Otherwise | REJECT |
    | `2–4` (below threshold) | AI Confidence below bypass threshold | REJECT |
    | `2–4` (below threshold) | AI Confidence above bypass threshold | BUY (F-Score bypassed by high conviction) |
    | `≥ 5` normal / `≥ 2` low-exposure | — | BUY permitted |

*   **Basic Health Check**: If EPS < 0 or PE > 100 (`is_healthy = False`), BUY is also rejected.

### Step G: Macro Hedging (AI-Aware Defense)
The bot continuously monitors the **VIX** and **NASDAQ Trend (QQQ vs SMA-50)**. Before entering a hedge (**PSQ**), it consults Gemini. If Gemini provides a "Veto" (Sentiment < -0.2 for PSQ, implying a market recovery), the hedge is skipped.

| Alert Level | Condition | Hedge Size |
| :--- | :--- | :--- |
| **Clear** | Bullish trend & low VIX | 0% |
| **Caution** | QQQ < SMA-50 OR VIX > 30 | 2% |
| **Fear** | QQQ < SMA-50 AND VIX > 35 | 5% |
| **Panic** | VIX > 45 | 10% |

### Step H: Dynamic Position Sizing
Unlike fixed sizing, the bot now calculates the exact USD for every trade based on three factors:
1.  **Conviction (AI Score)**: Higher conviction → Larger size.
2.  **VIX (Market Risk)**: High VIX → Squeezes position sizes down to preserve cash.
3.  **Band Width (Volatility)**: High volatility → Reduces exposure.

**Formula**: `Base Size × (Conviction/100) × (1 - (VIX/100)) × (1 - (Width/0.5))`
*   **Max Cap**: 40% of total equity.
*   **Star Floor**: Elite trades are guaranteed at least 20% allocation.

---

## 3. Portfolio-Level Logic (The Conviction Swap)

This is the "Auditor" logic. At the portfolio level, the bot identifies:
*   **Weakest Link**: Any held stock with Conviction Score **< 50** or failing Deep Health.
*   **Rising Star**: Any non-held stock with Conviction Score **> 80**.
*   **The Swap**: Sells the Weakest Link to fund the Rising Star.
*   **Hurdle**: Only swaps if the Rising Star's conviction beats the Weakest Link's conviction.

---

## 4. Position Exit Rules (Summary)

The bot exits positions (beyond the initial stop/profit targets) if:

1.  **Profit Target (+5%)**: Locks in the gain.
2.  **Stop Loss (-2.5%)**: Protects the capital pool.
3.  **Sentiment Crash (< -0.4)**: News has turned seriously negative.
4.  **RSI Overbought (≥ 80)**: Momentum exhaustion signal.
5.  **Upper Bollinger Band**: Price has reverted to fair/overvalued territory.

---

## 5. The Financial Benchmark (The Hurdle Rate)

The Aberfeldie Node operates on a **"Beat the Bank"** philosophy. Every dollar in cash sits in the mortgage offset account, effectively earning the current mortgage rate tax-free.

### The Calculation
1.  **Raw Mortgage Rate**: Set via `MORTGAGE_RATE` env var (e.g., 5.40%).
2.  **Tax-Adjusted Hurdle**: `Rate × (1 - 0.35)` (35% tax benefit).
3.  **The Goal**: Only deploy capital for opportunities with a high probability of beating this benchmark.

---

## 6. Summary Table

| Input | Threshold | Role |
| :--- | :--- | :--- |
| **Vol Filter** | > 35% (> 52.5% low-exposure) | Safety Brake — skips trade |
| **Bollinger Band** | Lower / Upper | Initial Buy / Sell signal |
| **RSI (14)** | ≤ 30 / ≥ 80 | Oversold aggression / Overbought exit |
| **Sentiment Gate** | ≥ 0.4 (≥ 0.2 low-exposure) | Permission to BUY |
| **Sentiment Exit** | < -0.4 | Forced SELL |
| **F-Score** | ≤ 1 | High-confidence turnaround play only (relaxed sentiment for low-exposure) |
| **F-Score** | < 5 normal / < 2 low-exposure | Fundamental rejection |
| **F-Score** | ≥ 7 | Conviction bonus (+10) |
| **AI Confidence** | ≥ 85 + F-Score ≥ 7 | Star rating — conviction swap priority |
| **Profit Target** | +5% | Exit to lock gain |
| **Stop Loss** | -2.5% | Exit to protect capital |
| **Mortgage Rate** | Env var `MORTGAGE_RATE` | Raw bank benchmark |
| **Benchmark** | Rate × 0.65 (3.5%) | Effective benchmark to beat (Performance target) |
