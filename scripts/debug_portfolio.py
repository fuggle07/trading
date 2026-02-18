from google.cloud import bigquery

# Force correct project (user's project ID from context)
PROJECT_ID = "utopian-calling-429014-r9"
DATASET_ID = "trading_processed"
TABLE_ID = "portfolio"


def debug_portfolio():
    client = bigquery.Client(project=PROJECT_ID)
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

    print(f"🔍 Dumping Portfolio Table: {table_ref}")

    query = f"SELECT * FROM `{table_ref}`"
    results = list(client.query(query).result())

    total_cash = 0.0
    total_holdings = 0.0

    print(
        f"{'ASSET':<10} | {'CASH':<15} | {'HOLDINGS':<10} | {'AVG_PRICE':<10} | {'LAST_UPDATED'}"
    )
    print("-" * 80)

    for row in results:
        t_cash = row.cash_balance
        t_holdings = row.holdings
        try:
            t_avg = row.avg_price
        except:
            t_avg = None

        print(
            f"{row.asset_name:<10} | ${t_cash:,.2f}      | {t_holdings:<10} | {t_avg} | {row.last_updated}"
        )

        total_cash += t_cash
        # we can't sum holdings directly as they are different assets, but good for count

    print("-" * 80)
    print(f"TOTAL ROW COUNT: {len(results)}")
    print(f"TOTAL CASH SUM:  ${total_cash:,.2f}")


if __name__ == "__main__":
    debug_portfolio()
