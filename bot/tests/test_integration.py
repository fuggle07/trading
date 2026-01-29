import pytest
import httpx
from unittest.mock import patch, MagicMock

# --- INTEGRATION TESTS ---

@pytest.mark.asyncio
async def test_bot_external_service_connectivity():
    """
    Dry Run: Verify bot can reach external services and parse JSON correctly.
    This confirms the 'House' plumbing is working.
    """
    # MOCK: Prevent actual BigQuery writes during this test
    with patch('google.cloud.bigquery.Client') as mock_bq, \
         patch('portfolio_manager.PortfolioManager.update_ledger') as mock_ledger:
        
        # Setup mock return for get_state
        mock_pm = MagicMock()
        mock_pm.get_state.return_value = {"holdings": 0, "cash_balance": 50000.0}
        
        # Test URLs (using your environment defaults)
        finance_url = "http://localhost:8081/price/QQQ"
        sentiment_url = "http://localhost:8082/sentiment/QQQ"

        async with httpx.AsyncClient() as client:
            # Check Finance Service availability
            try:
                price_res = await client.get(finance_url, timeout=2.0)
                assert price_res.status_code == 200
                assert "price" in price_res.json()
            except httpx.ConnectError:
                pytest.skip("Finance service not reachable for integration test")

            # Check Sentiment Service availability
            try:
                sent_res = await client.get(sentiment_url, timeout=2.0)
                assert sent_res.status_code == 200
                assert "score" in sent_res.json()
            except httpx.ConnectError:
                pytest.skip("Sentiment service not reachable for integration test")

def test_ledger_update_logic_integrity():
    """
    Confirm the PortfolioManager correctly formats SQL without executing it.
    """
    mock_client = MagicMock()
    # We only care that it calls .query() with a string containing our ticker
    from portfolio_manager import PortfolioManager
    pm = PortfolioManager(mock_client, "project.dataset.portfolio")
    
    pm.update_ledger("QQQ", 45000.0, 100)
    
    # Verify that a query was actually dispatched
    assert mock_client.query.called
    args, _ = mock_client.query.call_args
    assert "UPDATE `project.dataset.portfolio`" in args[0]
    assert "asset_name = 'QQQ'" in args[0]

