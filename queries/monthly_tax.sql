-- Monthly Tax Estimator for Aberfeldie Node
-- Directive: Calculate AUD-denominated tax liability

WITH daily_stats AS (
  SELECT 
    EXTRACT(MONTH FROM timestamp) as trade_month,
    paper_equity as equity_usd,
    fx_rate_aud,
    (paper_equity * fx_rate_aud) as equity_aud,
    LAG(paper_equity * fx_rate_aud) OVER (ORDER BY timestamp) as prev_equity_aud
  FROM `your-project-id.trading_data.performance_logs`
)

SELECT 
  trade_month,
  ROUND(MAX(equity_aud) - MIN(equity_aud), 2) as monthly_profit_aud,
  -- Estimating tax at a 32.5% marginal rate
  ROUND((MAX(equity_aud) - MIN(equity_aud)) * 0.325, 2) as est_tax_liability_aud,
  -- Showing 'Alpha' in local currency
  ROUND(AVG(fx_rate_aud), 4) as avg_fx_rate
FROM daily_stats
GROUP BY trade_month
ORDER BY trade_month;

