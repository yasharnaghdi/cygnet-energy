from typing import List

from src.api.client import EntsoEAPIClient


def get_zone_keys(country: str) -> List[str]:
    """Return all identifiers used for a country in the database."""
    if not country:
        return []

    eic = EntsoEAPIClient.BIDDING_ZONES.get(country)
    if eic and eic != country:
        return [country, eic]
    return [country]
