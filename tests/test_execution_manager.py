
import sys
import unittest
from unittest.mock import MagicMock, patch
import os

# Create mock modules for google.cloud and google.cloud.bigquery
# This allows testing ExecutionManager logic without installing the actual libraries
# which are failing to install on Python 3.14 due to protobuf issues.
mock_google = MagicMock()
mock_cloud = MagicMock()
mock_bigquery = MagicMock()

# Setup module structure
mock_google.cloud = mock_cloud
mock_cloud.bigquery = mock_bigquery

# Inject into sys.modules
sys.modules['google'] = mock_google
sys.modules['google.cloud'] = mock_cloud
sys.modules['google.cloud.bigquery'] = mock_bigquery

# Ensure bot directory is in path
sys.path.append(os.path.join(os.path.dirname(__file__), '../bot'))

from execution_manager import ExecutionManager

class TestExecutionManager(unittest.TestCase):
    def setUp(self):
        # Mock environment variables
        self.env_patcher = patch.dict(os.environ, {"PROJECT_ID": "test-project"})
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    def test_init_success(self):
        """Test that BQ client initializes when PROJECT_ID is present."""
        # Reset the mock client call history
        mock_bigquery.Client.reset_mock()
        
        manager = ExecutionManager()
        self.assertIsNotNone(manager.bq_client)
        mock_bigquery.Client.assert_called_with(project="test-project")


    def test_init_no_project_id(self):
        """Test that BQ client is None when PROJECT_ID is missing."""
        with patch.dict(os.environ, {}, clear=True):
            manager = ExecutionManager()
            self.assertIsNone(manager.bq_client)

    @patch('google.cloud.bigquery.Client')
    def test_place_order_logging(self, mock_bq_client):
        """Test that place_order calls _log_to_bigquery."""
        # Setup Mock
        mock_client_instance = MagicMock()
        mock_bq_client.return_value = mock_client_instance
        
        manager = ExecutionManager()
        
        signal = {
            "ticker": "NVDA",
            "action": "BUY",
            "price": 100.0,
            "reason": "Test Signal"
        }
        
        result = manager.place_order(signal)
        
        # Verify result structure
        self.assertEqual(result['status'], 'FILLED')
        self.assertEqual(result['details']['ticker'], 'NVDA')
        
        # Verify BQ insertion was attempted
        mock_client_instance.insert_rows_json.assert_called_once()
        call_args = mock_client_instance.insert_rows_json.call_args
        self.assertEqual(call_args[0][0], "trading_data.executions") # check table_id
        self.assertEqual(call_args[0][1][0]['ticker'], 'NVDA') # check data payload

    @patch('google.cloud.bigquery.Client')
    def test_log_error_handling(self, mock_bq_client):
        """Test that logging failure doesn't crash the app."""
        mock_client_instance = MagicMock()
        # Simulate an API error (e.g. 404 table not found)
        mock_client_instance.insert_rows_json.side_effect = Exception("Table not found")
        mock_bq_client.return_value = mock_client_instance
        
        manager = ExecutionManager()
        
        # Should not raise exception
        try:
            manager.place_order({"ticker": "FAIL_TEST"})
        except Exception as e:
            self.fail(f"place_order raised exception unexpectedly: {e}")

if __name__ == '__main__':
    unittest.main()
