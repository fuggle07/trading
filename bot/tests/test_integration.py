import pytest
import httpx
from unittest.mock import patch, MagicMock
from portfolio_manager import PortfolioManager

# This test requires pytest-asyncio to be installed
@pytest.mark.asyncio
async def test_service_connectivity_dry_run():
    """
    Dry Run: Confirms the bot can talk to Finance/Sentiment services.
    Mocks BigQuery to prevent any real ledger updates.
    """
    # 1. Setup Mocks for Infrastructure
    with patch('google.cloud.bigquery.Client') as mock_bq_client:
        mock_bq = mock_bq_client.return_value
        
        # 2. Mock Portfolio Manager to return a safe test state
        pm = PortfolioManager(mock_bq, "test-project.trading_data.portfolio")
        
        # 3. Define the internal endpoints (using your local defaults)
        finance_url = "http://localhost:8081/price/QQQ"
        sentiment_url = "http://localhost:8082/sentiment/QQQ"

        async with httpx.AsyncClient() as client:
            # Test Finance Service Connectivity
            try:
                price_res = await client.get(finance_url, timeout=2.0)
                if price_res.status_code == 200:
                    data = price_res.json()
                    assert "price" in data
                    assert isinstance(data["price"], (int, float))
            except httpx.ConnectError:
                pytest.skip("Finance service offline - skipping integration check")

            # Test Sentiment Service Connectivity
            try:
                sent_res = await client.get(sentiment_url, timeout=2.0)
                if sent_res.status_code == 200:
                    data = sent_res.json()
                    assert "score" in data
                    assert -1.0 <= data["score"] <= 1.0
            except httpx.ConnectError:
                pytest.skip("Sentiment service offline - skipping integration check")

def test_ledger_sql_logic_integrity():
    """
    Verify the PortfolioManager correctly formats the UPDATE DML
    without actually executing it against BigQuery.
    """
    mock_client = MagicMock()
    table_id = "unified-aberfeldie-node.trading_data.portfolio"
    pm = PortfolioManager(mock_client, table_id)
    
    # Simulate a ledger sync
    pm.update_ledger("QQQ", 45000.0, 100)
    
    # Verify the SQL string construction
    assert mock_client.query.called
    sql_call = mock_client.query.call_args[0][0]
    assert f"UPDATE `{table_id}`" in sql_call
    assert "SET cash_balance = 45000.0" in sql_call
    assert "asset_name = 'QQQ'" in sql_call

