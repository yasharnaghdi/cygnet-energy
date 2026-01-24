#!/usr/bin/env python
"""Load Open Power System Data CSV into PostgreSQL."""
import pandas as pd
import psycopg2.extras
from pathlib import Path
import sys
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.db.connection import get_connection


PSR_TYPE_MAPPING = {
    "solar": "B18",
    "wind_onshore": "B19",
    "wind_offshore": "B20",
    "biomass": "B01",
    "fossil_gas": "B04",
    "fossil_hard_coal": "B05",
    "hydro_run_of_river": "B12",
    "hydro_water_reservoir": "B11",
    "nuclear": "B14",
}


def load_csv_to_db(
    csv_path: str,
    bidding_zone: str = "DE",
    batch_size: int = 10000,
    dry_run: bool = False,
):
    """
    Load CSV data for specified bidding zone into database.

    Args:
        csv_path: Path to time_series_60min_singleindex.csv
        bidding_zone: Country code (default: DE for Germany)
        batch_size: Rows per insert batch (default: 10000)
        dry_run: If True, validate and report without DB writes
    """
    print(f"📊 Loading CSV: {csv_path}")
    print(f"🌍 Filtering for zone: {bidding_zone}")

    # Read CSV
    df = pd.read_csv(csv_path, parse_dates=["utc_timestamp"])
    print(f"✅ Loaded {len(df):,} rows, {len(df.columns)} columns")

    if "utc_timestamp" not in df.columns:
        raise ValueError("CSV missing required column: utc_timestamp")

    # Filter columns for target zone
    zone_prefix = f"{bidding_zone}_"
    generation_cols = [col for col in df.columns if col.startswith(zone_prefix) and "_generation_actual" in col]
    load_cols = [col for col in df.columns if col.startswith(zone_prefix) and "_load_actual" in col]

    print(f"📈 Found {len(generation_cols)} generation columns")
    print(f"📉 Found {len(load_cols)} load columns")

    if not generation_cols and not load_cols:
        raise ValueError(f"No generation/load columns found for zone {bidding_zone}")

    if dry_run:
        generation_rows = int(df[generation_cols].notna().sum().sum()) if generation_cols else 0
        load_rows = int(df[load_cols].notna().sum().sum()) if load_cols else 0
        print("Dry run: no database writes performed")
        print(f"   Estimated generation rows: {generation_rows:,}")
        print(f"   Estimated load rows: {load_rows:,}")
        return {
            "rows": len(df),
            "generation_cols": generation_cols,
            "load_cols": load_cols,
            "generation_rows": generation_rows,
            "load_rows": load_rows,
        }

    conn = get_connection()
    cur = conn.cursor()

    # Insert generation data
    total_gen_rows = 0
    for col in generation_cols:
        # Extract PSR type from column name
        # Example: "DE_solar_generation_actual" -> "solar"
        psr_name = col.replace(zone_prefix, "").replace("_generation_actual", "")
        psr_type = PSR_TYPE_MAPPING.get(psr_name, psr_name.upper())

        # Prepare data
        data = df[["utc_timestamp", col]].dropna()
        data = data.rename(columns={"utc_timestamp": "time", col: "actual_generation_mw"})
        data["bidding_zone_mrid"] = bidding_zone
        data["psr_type"] = psr_type
        data["quality_code"] = "A"
        data["data_source"] = "OPSD"

        # Batch insert
        records = data.to_dict("records")
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]

            psycopg2.extras.execute_batch(
                cur,
                """
                INSERT INTO generation_actual
                (time, bidding_zone_mrid, psr_type, actual_generation_mw, quality_code, data_source)
                VALUES (%(time)s, %(bidding_zone_mrid)s, %(psr_type)s, %(actual_generation_mw)s, %(quality_code)s, %(data_source)s)
                ON CONFLICT DO NOTHING
                """,
                batch,
                page_size=1000
            )
            conn.commit()

        total_gen_rows += len(records)
        print(f"  ✓ Inserted {len(records):,} rows for {psr_type}")

    # Insert load data
    total_load_rows = 0
    for col in load_cols:
        data = df[["utc_timestamp", col]].dropna()
        data = data.rename(columns={"utc_timestamp": "time", col: "load_consumption_mw"})
        data["bidding_zone_mrid"] = bidding_zone
        data["quality_code"] = "A"
        data["data_source"] = "OPSD"

        records = data.to_dict("records")
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]

            psycopg2.extras.execute_batch(
                cur,
                """
                INSERT INTO load_actual
                (time, bidding_zone_mrid, load_consumption_mw, quality_code, data_source)
                VALUES (%(time)s, %(bidding_zone_mrid)s, %(load_consumption_mw)s, %(quality_code)s, %(data_source)s)
                ON CONFLICT DO NOTHING
                """,
                batch,
                page_size=1000
            )
            conn.commit()

        total_load_rows += len(records)
        print(f"  ✓ Inserted {len(records):,} rows for load data")

    cur.close()
    conn.close()

    print(f"\n✅ Import complete!")
    print(f"   Generation rows: {total_gen_rows:,}")
    print(f"   Load rows: {total_load_rows:,}")
    print(f"   Total: {total_gen_rows + total_load_rows:,}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Load OPSD CSV into database")
    parser.add_argument("--csv-path", required=True, help="Path to CSV file")
    parser.add_argument("--zone", default="DE", help="Bidding zone code (default: DE)")
    parser.add_argument("--batch-size", type=int, default=10000, help="Insert batch size")
    parser.add_argument("--dry-run", action="store_true", help="Validate CSV without DB writes")

    args = parser.parse_args()

    load_csv_to_db(args.csv_path, args.zone, args.batch_size, args.dry_run)
