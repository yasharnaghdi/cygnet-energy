"""
Diagnostic script to check what data exists in generation_actual
"""

import pandas as pd
from src.db.connection import get_connection

conn = get_connection()

# Check what zones exist
zones_sql = """
SELECT DISTINCT bidding_zone_mrid as zone, COUNT(*) as row_count
FROM generation_actual
GROUP BY bidding_zone_mrid
ORDER BY row_count DESC
"""

zones_df = pd.read_sql_query(zones_sql, conn)
print("\n✓ Zones in generation_actual:")
print(zones_df)

# Check date range
date_sql = """
SELECT 
    MIN(time) as earliest,
    MAX(time) as latest,
    COUNT(*) as total_rows
FROM generation_actual
"""

date_df = pd.read_sql_query(date_sql, conn)
print("\n✓ Date range:")
print(date_df)

# Check PSR types
psr_sql = """
SELECT DISTINCT psr_type, COUNT(*) as count
FROM generation_actual
GROUP BY psr_type
ORDER BY count DESC
"""

psr_df = pd.read_sql_query(psr_sql, conn)
print("\n✓ PSR Types:")
print(psr_df.head(10))

conn.close()
