"""
Background ingestion runner - fetches ENTSO-E data every 15 minutes.
Run as: poetry run python scripts/run_ingestion.py
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    from src.services.ingestion import EntsoEIngestionService

    token = os.getenv("ENTSOE_API_TOKEN")
    if not token or token == "replace_with_token":
        print("ENTSOE_API_TOKEN not set in environment")
        print("Get token from: https://transparency.entsoe.eu/")
        return

    service = EntsoEIngestionService()
    zones = ["DE", "FR", "ES"]

    print(f"Starting ingestion for zones: {zones}")
    print("Press Ctrl+C to stop")

    while True:
        try:
            end = datetime.now(timezone.utc)
            start = end - timedelta(hours=48)

            for zone in zones:
                print(f"\nFetching {zone}: {start.date()} to {end.date()}")
                service.fetch_and_store(zone, start, end)
                print(f"{zone} complete")

            print("\nNext run in 15 minutes...")
            time.sleep(900)

        except KeyboardInterrupt:
            print("\nStopping ingestion")
            break
        except Exception as exc:
            print(f"Error: {exc}")
            print("Retrying in 60 seconds...")
            time.sleep(60)


if __name__ == "__main__":
    main()
