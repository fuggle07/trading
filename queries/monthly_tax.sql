-- High-resolution tax calculation using logged rates
SELECT 
  FORMAT_TIMESTAMP('%Y-%m', timestamp) as month,
  jsonPayload.details.ticker,
  SUM(CAST(jsonPayload.details.sale_proceeds AS FLOAT64)) as total_income,
  -- Dynamic interest cost based on the logged rate at time of trade
  SUM((CAST(jsonPayload.details.shares AS INT64) * CAST(jsonPayload.details.price AS FLOAT64)) 
      * (CAST(jsonPayload.details.active_mortgage_rate AS FLOAT64) / 12)) as interest_expense
FROM `unified-aberfeldie-node.system_logs.stdout`
WHERE jsonPayload.event = "EXECUTION"
GROUP BY 1, 2
ORDER BY month DESC

