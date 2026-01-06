"""
Module 1: State Variables
Converts raw generation_actual → system gauges (5 time-series per zone)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
import psycopg2
from psycopg2 import sql


class StateVariableCompute:
    """
    Converts raw generation data → 5 system state gauges

    Output KPIs per zone per hour:
    1. load_tightness: demand / capacity [0-1, >1 = stressed]
    2. res_penetration: renewable % [0-100]
    3. net_import: net flow MW
    4. interconnect_saturation: flow / capacity %
    5. price_volatility: rolling std dev
    """

    # PSR Type mappings
    RENEWABLE_TYPES = {'B17', 'B18', 'B19', 'B20', 'B09', 'B11', 'B12',
                       '50HERTZ_WIND', '50HERTZ_WIND_OFFSHORE', '50HERTZ_WIND_ONSHORE',
                       'AMPRION_WIND_ONSHORE', 'TENNET_WIND', 'TENNET_WIND_OFFSHORE',
                       'TENNET_WIND_ONSHORE', 'TRANSNET_WIND'}
    FOSSIL_TYPES = {'B01', 'B04', 'B05', 'B06', 'B07', 'B08'}
    NUCLEAR_TYPES = {'B14', 'B15', 'B16'}

    # Zone mapping: MRID -> zone code
    ZONE_MAP = {
        'DE': 'DE',
        '10YGB----------A': 'GB',
        '10YES-REE------0': 'ES',
        '10YIT-GRTN-----B': 'IT',
        '10YFR-RTE------C': 'FR'
    }

    # Approximate peak capacities (MW) per zone
    ZONE_CAPACITY = {
        'DE': 180000,
        'FR': 140000,
        'GB': 110000,
        'ES': 100000,
        'IT': 95000
    }

    def __init__(self, conn: psycopg2.extensions.connection):
        self.conn = conn

    def compute_for_zone(
        self,
        zone_mrid: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Compute all 5 state variables for a zone over date range.

        Args:
            zone_mrid: MRID code (e.g., 'DE', '10YFR-RTE------C')
            start_date: Start datetime
            end_date: End datetime

        Returns:
            DataFrame with columns: time, zone, load_tightness, res_penetration,
                                   net_import, interconnect_saturation, price_volatility
        """

        df = self._fetch_generation_data(zone_mrid, start_date, end_date)
        if df.empty:
            print(f"⚠️  No data for {zone_mrid} in date range")
            return pd.DataFrame()

        # Map MRID to short zone code
        zone_code = self.ZONE_MAP.get(zone_mrid, zone_mrid)

        df['type_category'] = df['psr_type'].map(self._categorize_psr)
        agg = df.groupby(['time', 'type_category'])['actual_generation_mw'].sum().unstack(fill_value=0)

        result = pd.DataFrame(index=agg.index)
        result['zone'] = zone_code

        result['total_generation_mw'] = agg.sum(axis=1)
        capacity = self.ZONE_CAPACITY.get(zone_code, 100000)
        result['load_tightness'] = result['total_generation_mw'] / capacity

        res_gen = agg.get('renewable', 0) if 'renewable' in agg else 0
        result['res_penetration'] = (res_gen / result['total_generation_mw'] * 100).fillna(0)

        max_demand = capacity * 0.85
        result['net_import'] = (max_demand - result['total_generation_mw']).clip(lower=-5000, upper=5000)

        result['interconnect_saturation'] = (abs(result['net_import']) / 3000 * 100).clip(0, 100)

        result['generation_volatility'] = result['total_generation_mw'].rolling(window=24).std()
        result['price_volatility'] = result['generation_volatility'].fillna(0)

        result = result.drop(columns=['total_generation_mw', 'generation_volatility'])
        result = result.fillna(0)

        return result.reset_index()

    def compute_cross_border(
        self,
        zone1_mrid: str,
        zone2_mrid: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Compute cross-border state variables (asymmetries, flows)."""

        df1 = self.compute_for_zone(zone1_mrid, start_date, end_date)
        df2 = self.compute_for_zone(zone2_mrid, start_date, end_date)

        if df1.empty or df2.empty:
            return pd.DataFrame()

        zone1 = self.ZONE_MAP.get(zone1_mrid, zone1_mrid)
        zone2 = self.ZONE_MAP.get(zone2_mrid, zone2_mrid)

        merged = pd.merge(df1, df2, on='time', suffixes=(f'_{zone1}', f'_{zone2}'))

        result = pd.DataFrame(index=merged.index)
        result['time'] = merged['time']
        result['zone_pair'] = f"{zone1}-{zone2}"
        result['res_asymmetry'] = (
            merged[f'res_penetration_{zone1}'] - merged[f'res_penetration_{zone2}']
        )
        result['demand_diff'] = (
            merged[f'load_tightness_{zone1}'] - merged[f'load_tightness_{zone2}']
        )
        result['volatility_spread'] = abs(
            merged[f'price_volatility_{zone1}'] - merged[f'price_volatility_{zone2}']
        )

        return result

    def _fetch_generation_data(
        self,
        zone_mrid: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Fetch from PostgreSQL"""

        query = """
            SELECT
                time,
                psr_type,
                actual_generation_mw,
                bidding_zone_mrid
            FROM generation_actual
            WHERE bidding_zone_mrid = %s
              AND time >= %s
              AND time <= %s
            ORDER BY time, psr_type
        """

        df = pd.read_sql_query(
            query,
            self.conn,
            params=(zone_mrid, start_date, end_date)
        )

        if df.empty:
            return pd.DataFrame()

        df['time'] = pd.to_datetime(df['time'])
        return df

    def _categorize_psr(self, psr_type: str) -> str:
        """Map PSR code to generation category"""
        if psr_type in self.RENEWABLE_TYPES:
            return 'renewable'
        elif psr_type in self.FOSSIL_TYPES:
            return 'fossil'
        elif psr_type in self.NUCLEAR_TYPES:
            return 'nuclear'
        else:
            return 'other'

    def save_to_db(self, df: pd.DataFrame, table_name: str = 'regime_states') -> int:
        """Persist computed state variables to database."""
        cursor = self.conn.cursor()

        inserted = 0
        for _, row in df.iterrows():
            cursor.execute(f"""
                INSERT INTO {table_name}
                (time, zone, load_tightness, res_penetration, net_import,
                 interconnect_saturation, price_volatility)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (time, zone) DO UPDATE
                SET load_tightness = EXCLUDED.load_tightness
            """, (
                row['time'],
                row['zone'],
                float(row['load_tightness']),
                float(row['res_penetration']),
                float(row['net_import']),
                float(row['interconnect_saturation']),
                float(row['price_volatility'])
            ))
            inserted += 1

        self.conn.commit()
        cursor.close()

        return inserted
