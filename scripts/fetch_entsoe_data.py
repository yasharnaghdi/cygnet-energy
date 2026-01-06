"""
Fetch ENTSO-E data from live API and store in PostgreSQL

Usage:
    python scripts/fetch_entsoe_data.py --country DR --start 2020-06-01 --end 2020-06-30

    # or just fetch yesterday's data:
    python scripts/fetch_entsoe_data.py --country DE
"""

import argparse
import logging
from datetime import datetime, timedelta , date
from typing import Optional
import psycopg2
from psycopg2 import sql
import requests

# Add src to path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.client import EntsoEAPIClient
from src.utils.config import DATABASE_URL, DEBUG

# Setup logging
logging.basicConfig(
    level = logging.INFO,
    format = '%(asctime)s %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FetchAndStoreData:
    """Fetch ENTSO-E data and store in PostgreSQL"""

    def __init__(self, db_url: str, api_client: EntsoEAPIClient):
        self.db_url = db_url
        self.api_client = api_client
        self.conn = None

    def connect_db(self) -> bool:
        """Docstring for connect_db """
        try:
            self.conn = psycopg2.connect(self.db_url)
            logger.info(" Connected to PostgreSQL")
            return True
        except Exception as e:
            logger.error(f" Database connection failed: {e}")
            return False

    def close_db(self):
        """ Close DB connection"""
        if self.conn:
            self.conn.close()
            logger.info("Closed database connection")

    def fetch_and_insert(
        self,
        country: str,
        start: datetime,
        end: datetime
    ) -> int:
        """
        Docstring for fetch_and_insert

        :param self: Description
        :param country: Description
        :type country: str
        :param start: Description
        :type start: datetime
        :param end: Description
        :type end: datetime
        :return: Description
        :rtype: int
        """

        if not self.connect_db():
            return 0

        try:
            # fetch from API
            logger.info(f" Fetching data for {country} ({start.date()} to {end.date()}...)")
            xml_data = self.api_client.get_actual_generation(country, start, end)

            if not xml_data:
                logger.warning(f" No data returned from API for {country}")
                return 0

            # Parse XML to DataFrame
            from src.api.parser import EntsoEXMLParser
            df = EntsoEXMLParser.parse_generation_xml(xml_data)

            if df is None or df.empty:
                logger.warning(" No records parsed from XML")
                return 0


            # Add country code
            df['bidding_zone_mrid'] = self.api_client.BIDDING_ZONES.get(country,country)

            df['quality_code'] = 'A'
            df['data_source'] = 'ENTSOE_API'

            # insert into database
            inserted = self._insert_records(df, country)

            return inserted

        except Exception as e:
            logger.error(f" Error during fetch and insert: {e}")
            return 0
        finally:
            self.close_db()

    def _insert_records(self, df, country: str) -> int:
        """Insert DataFrame records into PostgreSQL"""

        cursor = self.conn.cursor()
        inserted_count = 0

        try:
            for _, row in df.iterrows():
                try:
                    cursor.execute("""
                        INSERT INTO generation_actual
                        (time, bidding_zone_mrid, psr_type, actual_generation_mw, quality_code, data_source)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (time, bidding_zone_mrid, psr_type)
                        DO UPDATE SET actual_generation_mw = EXCLUDED.actual_generation_mw
                    """, (
                        row['time'],
                        row['bidding_zone_mrid'],
                        row['psr_type'],
                        row['actual_generation_mw'],
                        row['quality_code'],
                        row['data_source']  # ADD THIS LINE
                    ))

                    inserted_count += 1

                except Exception as e:
                    logger.error(f"Row insert error: {e}")  # Changed from logger.debug
                    continue

            self.conn.commit()
            logger.info(f"inserted/updated {inserted_count} records for {country}")
            return inserted_count

        except Exception as e:
            logger.error(f" Batch insert failed: {e}")
            self.conn.rollback()
            return 0
        finally:
            cursor.close()

def main():
    parser = argparse.ArgumentParser(
        description="Fetch ENTSO-E generation data and store in PostgreSQL"
    )

    parser.add_argument(
        '--country',
        type=str,
        required=True,
        choices=['DE', 'FR', 'GB', 'ES', 'IT', 'NL', 'BE'],
        help='Country code (e.g., DE, FR, GB)'
    )

    parser.add_argument(
        '--start',
        type=str,
        default=None,
        help='End date (YYYY-MM-DD). Default: today'
    )

    parser.add_argument(
        '--end',
        type=str,
        default=None,
        help='End date (YYYY-MM-DD). Default: today'
    )

    parser.add_argument(
        '--days',
        type=int,
        default=1,
        help='Number of days to fetch (if no start date given)'
    )

    args = parser.parse_args()

    # Parse dates
    if args.start:
        start_date = datetime.strptime(args.start , '%Y-%m-%d')
    else:
        start_date = datetime.now() - timedelta(days=args.days)

    if args.end:
        end_date = datetime.strptime(args.end, '%Y-%m-%d')
    else:
        end_date = datetime.now()

    # Ensure times span full days
    start = datetime.combine(start_date.date(), datetime.min.time())
    end = datetime.combine(end_date.date(), datetime.max.time())

    logger.info("="* 60)
    logger.info("ENTSO-E Data Fetch & Store")
    logger.info("="* 60)
    logger.info(f"Country: {args.country}")
    logger.info(f"Date Range: {start.date()} to {end.date()}")
    logger.info("="* 60)

    # initialise client and fetcher
    api_client = EntsoEAPIClient()
    fetcher = FetchAndStoreData(DATABASE_URL, api_client)

    # Fetch and insert
    try:
        inserted = fetcher.fetch_and_insert(args.country, start, end)
        logger.info(f"\n{'='*60}")
        logger.info(f" Success: {inserted} records processed")
        logger.info(f"{'='*60}")

    except Exception as e:
        logger.error(f" Failed: {e}")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())
