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
*   **Sentiment Soft Stop (+2.5%)**: If the stock is up at least 2.5% from your average cost, but the AI determines sentiment has flipped negative, the bot **SELLS 25%**. This takes risk off the table proactively while allowing the remaining 75% to rely on trailing stops.
*   **Volatility-Scaled Trailing Stop**: 
    1.  **Limit**: Scales continuously from **-3.5%** up to **-8.0%** from the High Water Mark (HWM), depending on the stock's historical volatility. Wild stocks get a longer leash.
    2.  **Activation**: Becomes fully active dynamically (usually around **+3%** to **+6%** profit) once the stock clears expected market noise.
*   **Dynamic Hard Stop-Loss**: Scales continuously from a strict **-2.5%** floor all the way to **-12.0%** for highly volatile assets, protecting capital without premature whipsawing.
*   **RSI Overbought (≥ 85)**: Exit to capture extreme momentum exhaustion.

### Step B: The Volatility Filter
*   **Check**: Are the price swings too wild? (Band Width > **42.5%** normally).
*   **Action**: If yes, the bot **SITS OUT**. It avoids catching a falling knife.

### Step C: Technical Baseline
*   **IF** Price ≤ Lower Bollinger Band AND Sentiment ≥ 0.4: **Baseline = BUY**.
*   **IF** Price ≥ Upper Bollinger Band AND Volume > 1.5× Average Volume: **Baseline = MOMENTUM_BREAKOUT** (Aggressive BUY, overrides normal SELL).
*   **IF** Price ≥ Upper Bollinger Band (with normal volume): **Baseline = SELL** (Mean reversion).
*   **IF** RSI ≤ 30 AND Sentiment > 0.4: **Baseline = RSI_OVERSOLD_BUY** (Overrides HOLD).
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
    | `≥ 5` | — | BUY permitted |

*   **Basic Health Check**: If EPS < 0 or PE > 100 (`is_healthy = False`), BUY is also rejected.

### Step F (Part 2): Sector Limit Gate
*   **Condition**: The bot prefers diversification. By default, sector limits are disabled to allow momentum trading, but if `ENFORCE_SECTOR_LIMITS=true` is set in the environment:
*   **Action**: The bot will strictly reject any new entry into a sector if the portfolio already holds **2 positions** in that identical sector.

### Step G: Macro Hedging (AI-Aware Defense)
The bot continuously monitors the **VIX** and **NASDAQ Trend (QQQ vs SMA-50)**. Before entering a hedge (**PSQ**), it consults Gemini. If Gemini provides a "Veto" (Sentiment < -0.2 for PSQ, implying a market recovery), the hedge is skipped.

| Alert Level | Condition | Hedge Size |
| :--- | :--- | :--- |
| **Clear** | Bullish trend & low VIX | 0% |
| **Caution** | QQQ < SMA-50 OR VIX > 30 | 2% |
| **Fear** | QQQ < SMA-50 AND VIX > 35 | 5% |
| **Panic** | VIX > 45 | 10% |

### Step H: Volatility-Scaled Position Sizing (Risk Parity)
Unlike fixed sizing, the bot mathematically equates physical dollar risk across all assets using a dynamic risk-parity formula:
1.  **Risk Budget**: Determines the absolute maximum USD you are willing to lose on the trade (scales strictly from 0.4% to 1.0% of total equity based on AI Conviction).
2.  **Fear & Volatility Dampers**: The absolute Risk Budget is reduced by multipliers if the VIX is elevated (> 20) or the specific ticker's Bollinger Bands are exceptionally wide (> 5%).
3.  **Dynamic Stop Division**: The final Risk Budget is divided precisely by the stock's custom dynamic stop-loss distance (between 2.5% and 12.0%). 
    * *Result:* Extremely volatile stocks (like AMD with a 10% stop) will automatically scale your purchased shares down heavily compared to stable stocks (like LLY with a 2.5% stop). If either stock hits its unique stop, you lose the exact identical amount of dollars.
4.  **Cascading Executions**: During active trading, the bot buys highest-conviction stocks first, immediately deducting the exact cost from its local working memory. Subsequent runner-up trades perfectly scale down into the remaining fraction of available cash until the pool hits $1,000. 

*   **Max Cap**: 28% of total equity per position.
*   **Star Floor**: Elite trades are guaranteed at least a target allocation to maximize winners.

---

## 3. Portfolio-Level Logic (The Conviction Swap)

This is the "Auditor" logic. At the portfolio level, the bot identifies:
*   **Weakest Link**: The held stock with the lowest Conviction Score, prioritizing those with failing Deep Health or Sentiment Collapse (`< -0.1`).
*   **Rising Star**: The non-held stock with a Blended Conviction Score **>= 80** AND strictly positive sentiment (**>= 0.2**).
*   **The Swap**: Sells the Weakest Link to fund the Rising Star.
*   **Hurdle**: Swaps if the Rising Star's conviction is higher, with higher sentiment breaking ties.

---

## 4. Position Exit Rules (Summary)

The bot exits positions (beyond the initial stop/profit targets) if:

1.  **Profit Target (+5%)**: Locks in the gain.
2.  **Stop Loss (-2.5%)**: Protects the capital pool.
3.  **RSI Overbought (≥ 80)**: Momentum exhaustion signal.
4.  **Upper Bollinger Band**: Price has reverted to fair/overvalued territory.

---

---

## 5. Summary Table

| Input | Threshold | Role |
| :--- | :--- | :--- |
| **Vol Filter** | > 42.5% | Safety Brake — skips trade |
| **Bollinger Band** | Lower / Upper | Initial Buy / Sell signal |
| **RSI (14)** | ≤ 30 / ≥ 80 | Oversold aggression / Overbought exit |
| **Sentiment Gate** | ≥ 0.4 | Permission to BUY |
| **F-Score** | ≤ 1 | High-confidence turnaround play only |
| **F-Score** | < 5 | Fundamental rejection |
| **F-Score** | ≥ 7 | Conviction bonus (+10) |
| **AI Confidence** | ≥ 80 + F-Score ≥ 7 | Star rating — conviction swap priority |
| **Profit Target** | +5% | Exit to lock half gain |
| **Sentiment Fade** | +2.5% | Exit 25% if sentiment flips negative (Soft Stop) |
| **Trailing Stop** | -3.5% to -8.0% | Dynamic high-water mark trailing exit |
| **Stop Loss** | -2.5% to -12.0% | Exit to protect capital (Volatility-scaled) |
