# Decision Logic: The Aberfeldie Node Strategy

This document explains in plain English how the Aberfeldie Node decides to BUY, SELL, or HOLD a position. The system uses a multi-layered "Decision Tree" that combines technical math, news sentiment, and fundamental health.

---

## 1. The Inputs (What the Bot Sees)

The bot gathers four primary data points for every ticker in its watchlist:

1.  **Technicals (Bollinger Bands)**: Measures the "stretch" of the price. Is it too low (oversold) or too high (overbought)?
2.  **Sentiment (Gemini 2.0 Flash)**: Scans recent news headers. Is the global narrative positive, neutral, or negative?
3.  **Fundamental Health**: Checks balance sheets and filings. Is the company "healthy" or showing signs of distress?
4.  **Portfolio Context**: Looks at what we already own. Do we have a "laggard" that should be replaced by a "rising star"?

---

## 2. The Decision Tree (The Logical Flow)

When the bot evaluates a stock (e.g., NVDA), it follows this step-by-step logic:

### Step A: The Volatility Filter
*   **Check**: Are the price swings too wild? (Band Width > 25%)
*   **Action**: If yes, the bot **SITS OUT**. It avoids "catching a falling knife" or buying into extreme chaos.

### Step B: The Priority Override (Exit Rules)
**Rule**: If you already own the stock, the bot checks your Profit/Loss **before** looking at the charts.
*   **The Profit Target (+5%)**: If the stock is up 5%, the bot **SELLS IMMEDIATELY**. It does not care if the technical data suggests it could go higher. The priority is returning the gain to your mortgage offset.
*   **The Stop Loss (-2.5%)**: If the stock drops 2.5%, the bot exits to protect your capital.
*   **The Narrative Crash**: If news sentiment drops below **-0.4**, the bot exits even if the technical price looks fine.

### Step C: Technical Baseline
*   **IF** Price <= Lower Bollinger Band: **Baseline = BUY**.
*   **IF** Price >= Upper Bollinger Band: **Baseline = SELL**.
*   **OTHERWISE**: **Baseline = HOLD**.

### Step C: The Sentiment Gate (For Buying)
*   **Condition**: Even if the price is low (Technical BUY), the **Sentiment Score** must be **higher than 0.4**.
*   **Logic**: We don't buy a dip if the news is currently toxic. We want to see the price "bottoming out" with a positive narrative.

### Step D: The Fundamental Kill-Switch
*   **Condition**: If the **Fundamental Score** is **lower than 40/100**.
*   **Action**: **BUY IS CANCELLED**. No matter how cheap the stock is or how good the news sounds, if the "underlying health" is failing, the bot will not deploy capital.

### Step E: Low Exposure Aggression (The "Cash Deployment" Rule)
*   **Condition**: If the portfolio is **> 75% in cash** (Low Exposure).
*   **Rule Change**: The bot becomes more aggressive. It will **BUY** even if the Technical Baseline is **HOLD** (price in the middle of the bands), provided that:
    1.  **Sentiment** is elite (> 0.6).
    2.  **Fundamentals** are elite (> 70).
*   **Signal Name**: This appears in logs as `HOLD_AGGRESSIVE_ENTRY`.

---

## 3. Position Management (When to Exit)

The bot doesn't just wait for Bollinger Bands to hit the top to sell. It will force an exit if:

1.  **Profit Target (+5%)**: Takes the win and moves back to cash offset.
2.  **Stop Loss (-2.5%)**: Cuts the loss quickly to protect the $100,000 capital.
3.  **Sentiment Crash**: If news sentiment drops below **-0.4**, the bot exits immediately, regardless of price action.

---

## 4. The Conviction Swap (Portfolio Level)

This is the "Auditor" logic. If the bot is fully invested but finds a better opportunity:
*   **Weakest Link**: Any current holding with a Conviction Score **< 50%**.
*   **Rising Star**: Any non-held stock with a Conviction Score **> 80%**.
*   **The Swap**: The bot will liquidate the "Weakest Link" to fund the "Rising Star."
*   **Initial Deployment**: If no "Weakest Link" exists (e.g., you are 100% in cash), the bot will immediately buy the **Rising Star** to put your capital to work.

---

## 5. Summary Table

| Input | Threshold | Role |
| :--- | :--- | :--- |
| **Vol Filter** | > 25% | Safety Brake (Skips trade) |
| **Bollinger Band** | Lower / Upper | Initial Buy / Sell signal |
| **Sentiment** | > 0.4 | Permission to BUY |
| **Sentiment** | < -0.4 | Forced SELL (Exit) |
| **Fundamentals** | < 40 | Forbidden to BUY |
| **Fundamentals** | > 70 | Conviction Bonus (+10%) |
| **Mortgage Rate** | 5.2% | The benchmarck to beat |
