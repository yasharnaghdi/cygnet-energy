import requests
from typing import Optional, Dict
from datetime import datetime
from src.utils.config import API_TOKEN, DEBUG

class EntsoEAPIClient:
    """Client for ENTSO-E Transparency Platform API"""

    # Correct base URL - NO /api path needed!
    BASE_URL = "https://web-api.tp.entsoe.eu/api"

    # Country to Bidding Zone mapping (EIC codes)
    BIDDING_ZONES = {
        "DE": "10Y1001A1001A83F",  # Germany (DE-LU from 2018-10-01)
        "FR": "10YFR-RTE------C",   # France
        "GB": "10YGB----------A",   # Great Britain
        "ES": "10YES-REE------0",   # Spain
        "IT": "10YIT-GRTN-----B",   # Italy
        "NL": "10YNL----------L",   # Netherlands
        "BE": "10YBE----------2",   # Belgium
    }

    def __init__(self, token: str = API_TOKEN):
        self.token = token

    def _format_datetime(self, dt: datetime) -> str:
        """Format datetime to ENTSO-E format: YYYYMMDDHHmm"""
        return dt.strftime("%Y%m%d%H%M")

    def get_actual_generation(
        self,
        country: str,
        start: datetime,
        end: datetime,
        psr_type: Optional[str] = None
    ) -> Optional[str]:
        """
        Fetch actual generation per type (A75 document)

        Args:
            country: Country code (DE, FR, GB, ES, IT, NL, BE)
            start: Start datetime
            end: End datetime
            psr_type: Optional PSR type filter (e.g., 'B01', 'B18', 'B19')

        Returns:
            XML response string or None if error
        """

        if country not in self.BIDDING_ZONES:
            print(f"❌ Unknown country: {country}")
            return None

        bidding_zone = self.BIDDING_ZONES[country]

        # Build parameters according to ENTSO-E API spec
        params = {
            'securityToken': self.token,
            'documentType': 'A75',  # Actual generation per type
            'processType': 'A16',    # Realised
            'in_Domain': bidding_zone,
            'periodStart': self._format_datetime(start),
            'periodEnd': self._format_datetime(end)
        }

        if psr_type:
            params['psrType'] = psr_type

        try:
            # Note: URL is just base, params go in query string
            response = requests.get(
                self.BASE_URL,
                params=params,
                timeout=30
            )
            response.raise_for_status()

            if DEBUG:
                print(f"✅ API Response: {response.status_code} for {country}")
                print(f"📍 URL: {response.url}")

            return response.text  # Returns XML

        except requests.exceptions.HTTPError as e:
            print(f"❌ HTTP Error {e.response.status_code}: {e}")
            if e.response.status_code == 401:
                print("   → Check your API token")
            elif e.response.status_code == 404:
                print("   → No data available for this period/country")
            elif e.response.status_code == 429:
                print("   → Rate limit exceeded, wait and retry")
            return None

        except requests.exceptions.RequestException as e:
            print(f"❌ API Error: {e}")
            return None

    def get_load(
        self,
        country: str,
        start: datetime,
        end: datetime
    ) -> Optional[str]:
        """Fetch actual total load (A65 document)"""

        if country not in self.BIDDING_ZONES:
            return None

        bidding_zone = self.BIDDING_ZONES[country]

        params = {
            'securityToken': self.token,
            'documentType': 'A65',  # Actual total load
            'processType': 'A16',    # Realised
            'outBiddingZone_Domain': bidding_zone,
            'periodStart': self._format_datetime(start),
            'periodEnd': self._format_datetime(end)
        }

        try:
            response = requests.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            return response.text

        except requests.exceptions.RequestException as e:
            print(f"❌ Load API Error: {e}")
            return None

    def test_connection(self) -> bool:
        """Test API connectivity with minimal request"""
        try:
            print("🧪 Testing ENTSO-E API connection...")
            start = datetime(2024, 1, 1, 0, 0)
            end = datetime(2024, 1, 1, 1, 0)

            result = self.get_actual_generation("DE", start, end)

            if result and '<' in result:  # Valid XML starts with <
                print("✅ API connection successful!")
                print(f"   Sample response length: {len(result)} chars")
                return True
            else:
                print("❌ API returned no valid data")
                return False

        except Exception as e:
            print(f"❌ Connection test failed: {e}")
            return False


# Quick test
if __name__ == "__main__":
    client = EntsoEAPIClient()
    client.test_connection()
