"""
Diagnose: What data exists in your database?
Shows which countries have data, date ranges, record counts.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.db.connection import get_connection

def diagnose():
    conn = get_connection()
    cursor = conn.cursor()

    print("\n📊 DATABASE DIAGNOSTIC REPORT\n")
    print("="*60)

    # Check which zones have data
    cursor.execute("""
        SELECT
            bidding_zone_mrid,
            COUNT(*) as record_count,
            MIN(time) as earliest,
            MAX(time) as latest,
            EXTRACT(DAY FROM MAX(time) - MIN(time)) as days_span
        FROM generation_actual
        GROUP BY bidding_zone_mrid
        ORDER BY record_count DESC;
    """)

    zones = cursor.fetchall()

    if not zones:
        print("❌ NO DATA IN DATABASE!")
        print("Run: poetry run python scripts/fetch_entsoe_data.py")
        return

    print(f"{'Zone':<10} {'Records':<12} {'Earliest':<20} {'Latest':<20} {'Days':<6}")
    print("-"*60)

    for zone, count, earliest, latest, days in zones:
        print(f"{zone:<10} {count:<12,} {str(earliest):<20} {str(latest):<20} {int(days or 0):<6}")

    print("\n" + "="*60)
    print("💡 ACTION: Use only the zones and date ranges shown above.")
    print("="*60 + "\n")

    conn.close()

if __name__ == "__main__":
    diagnose()
