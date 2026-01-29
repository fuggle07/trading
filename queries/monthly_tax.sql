-- High-Resolution Tax & Performance Audit
-- Data Source: master_log_sink (Aggregated Cloud Run Logs)
-- Logic: Calculates net profit after dynamic mortgage interest deduction

WITH trade_events AS (
  SELECT 
    timestamp,
    jsonPayload.details.ticker as ticker,
    jsonPayload.event as event_type,
    -- Extract trade details from the Master Log JSON
    CAST(jsonPayload.details.price AS FLOAT64) as trade_price,
    CAST(jsonPayload.details.shares AS INT64) as shares,
    CAST(jsonPayload.details.active_mortgage_rate AS FLOAT64) as mortgage_rate,
    -- Calculate position value
    (CAST(jsonPayload.details.shares AS INT64) * CAST(jsonPayload.details.price AS FLOAT64)) as position_value
  FROM `unified-aberfeldie-node.system_logs.stdout`
  WHERE jsonPayload.component = "trading-bot"
    AND jsonPayload.event IN ("EXECUTION", "STARTUP")
),

monthly_summary AS (
  SELECT 
    FORMAT_TIMESTAMP('%Y-%m', timestamp) as audit_month,
    ticker,
    -- Aggregate total proceeds from SELL events
    SUM(CASE WHEN event_type = "EXECUTION" AND jsonPayload.message LIKE "%SELL%" THEN position_value ELSE 0 END) as gross_proceeds,
    -- Calculate interest expense based on the rate active at the time of the trade
    -- Assumes 1/12th of annual rate applied to the capital used
    SUM(position_value * (mortgage_rate / 12)) as interest_deduction
  FROM trade_events
  GROUP BY 1, 2
)

SELECT 
  audit_month,
  ticker,
  ROUND(gross_proceeds, 2) as income_aud,
  ROUND(interest_deduction, 2) as deductible_interest,
  ROUND(gross_proceeds - interest_deduction, 2) as taxable_position,
  -- Estimate liability at a standard 30% rate for the pilot fund
  ROUND((gross_proceeds - interest_deduction) * 0.30, 2) as estimated_tax_liability
FROM monthly_summary
WHERE gross_proceeds > 0
ORDER BY audit_month DESC;

