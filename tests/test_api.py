import pytest
from unittest.mock import patch
from src.api.client import EntsoEAPIClient
from datetime import datetime

@pytest.fixture
def api_client():
    return EntsoEAPIClient(token="test_token_12345")

class TestEntsoEAPI:

    def test_api_initialization(self, api_client):
        """Test client initializes correctly"""
        assert api_client.token == "test_token_12345"
        assert api_client.BASE_URL == "https://web-api.tp.entsoe.eu/api"
        assert "DE" in api_client.BIDDING_ZONES

    def test_bidding_zone_mapping(self, api_client):
        """Test country to bidding zone mapping"""
        assert api_client.BIDDING_ZONES["DE"] == "10YDE-LHM------7"
        assert api_client.BIDDING_ZONES["FR"] == "10YFR-RTE------C"
        assert api_client.BIDDING_ZONES["GB"] == "10YGB-NGET-----0"

    @patch('requests.get')
    def test_get_actual_generation_success(self, mock_get, api_client):
        """Test successful generation data fetch"""
        mock_response = mock_get.return_value
        mock_response.status_code = 200
        mock_response.text = "<Publication_MarketDocument>...</Publication_MarketDocument>"

        start = datetime(2020, 6, 1, 0, 0)
        end = datetime(2020, 6, 1, 1, 0)

        result = api_client.get_actual_generation("DE", start, end)

        assert result is not None
        assert "Publication_MarketDocument" in result
        mock_get.assert_called_once()

    def test_invalid_country(self, api_client):
        """Test handling of invalid country code"""
        start = datetime(2020, 6, 1, 0, 0)
        end = datetime(2020, 6, 1, 1, 0)

        result = api_client.get_actual_generation("XX", start, end)

        assert result is None
