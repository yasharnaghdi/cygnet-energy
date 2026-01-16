"""
Carbon Intensity Calculation Service

Real-time CO2 emissions tracking for European electricity grids.
Calculates carbon intensity based on generation mix.

Formula:
    CO2_Intensity = Σ(Generation_MW_i × Emission_Factor_i) / Total_Generation_MW
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from src.api.client import EntsoEAPIClient
from src.api.parser import EntsoEXMLParser
from src.utils.zones import get_zone_keys
import psycopg2
from psycopg2 import sql
import logging



logger = logging.getLogger(__name__)


class CarbonIntensityService:
    """Calculate and track CO2 intensity of electricity grids"""

    # Emission factors (gCO2/kWh) - IPCC 2014 Lifecycle Assessment
    EMISSION_FACTORS = {
        'B01': 120,   # Biomass
        'B02': 820,   # Fossil Brown Coal/Lignite
        'B03': 490,   # Fossil Coal-Derived Gas
        'B04': 490,   # Fossil Gas (CCGT)
        'B05': 820,   # Fossil Hard Coal
        'B06': 650,   # Fossil Oil
        'B07': 820,   # Fossil Oil Shale
        'B08': 820,   # Fossil Peat
        'B09': 45,    # Geothermal
        'B10': 24,    # Hydro Pumped Storage
        'B11': 24,    # Hydro Run-of-River
        'B12': 24,    # Hydro Reservoir
        'B13': 20,    # Marine
        'B14': 12,    # Nuclear
        'B15': 100,   # Other
        'B16': 50,    # Other Renewable
        'B17': 41,    # Solar (generic)
        'B18': 41,    # Solar Photovoltaic
        'B19': 11,    # Wind Onshore
        'B20': 11,    # Wind Offshore
        'B21': 120,   # Waste
    }

    # Generation type names for display
    PSR_NAMES = {
        'B01': 'Biomass',
        'B02': 'Brown Coal',
        'B04': 'Fossil Gas',
        'B05': 'Hard Coal',
        'B06': 'Fossil Oil',
        'B09': 'Geothermal',
        'B10': 'Hydro Pumped',
        'B11': 'Hydro Run-of-River',
        'B12': 'Hydro Reservoir',
        'B14': 'Nuclear',
        'B17': 'Solar',
        'B18': 'Solar PV',
        'B19': 'Wind Onshore',
        'B20': 'Wind Offshore',
        'B21': 'Waste',
    }

    def __init__(self, db_connection):
        """
        Initialize with database connection

        Args:
            db_connection: psycopg2 connection object
        """
        self.conn = db_connection

    def _fetch_from_api(self, country: str) -> Optional[Dict]:
        """Fetch real-time data from ENTSO-E API"""

        try:
            logger.info(f"Fetching live data for {country} from API...")

            api_client = EntsoEAPIClient()
            end_date = datetime.now()
            start_date = end_date - timedelta(hours=24)

            xml_response = api_client.get_actual_generation(country, start_date, end_date)

            if not xml_response:
                return None

            df = EntsoEXMLParser.parse_generation_xml(xml_response)

            if df is None or df.empty:
                return None

            # Get most recent data
            latest_time = df['time'].max()
            latest_data = df[df['time'] == latest_time]

            generation_mix = {}
            for _, row in latest_data.iterrows():
                generation_mix[row['psr_type']] = row['actual_generation_mw']

            total_generation = sum(generation_mix.values())
            if total_generation == 0:
                return None

            co2_intensity = self._calculate_intensity(generation_mix, total_generation)
            renewable_pct = self._get_renewable_pct(generation_mix, total_generation)

            return {
                'timestamp': latest_time,
                'country': country,
                'co2_intensity': round(co2_intensity, 2),
                'generation_mix': self._format_mix(generation_mix),
                'renewable_pct': round(renewable_pct, 1),
                'fossil_pct': round(100 - renewable_pct, 1),
                'status': self._get_status(co2_intensity),
                'total_generation_mw': round(total_generation, 2),
                'data_source': 'Live API'
            }

        except Exception as e:
            logger.error(f"API error for {country}: {e}")
            return None


    def get_current_intensity(self, country: str) -> Optional[Dict]:
        """Get current CO2 intensity - tries database first, then API"""

        try:
            cursor = self.conn.cursor()
            zone_keys = get_zone_keys(country)

            cursor.execute("""
                SELECT time, psr_type, actual_generation_mw
                FROM generation_actual
                WHERE bidding_zone_mrid = ANY(%s)
                AND time = (
                    SELECT MAX(time)
                    FROM generation_actual
                    WHERE bidding_zone_mrid = ANY(%s)
                )
                ORDER BY time DESC, psr_type
            """, (zone_keys, zone_keys))

            rows = cursor.fetchall()
            cursor.close()

            if rows:
                generation_mix = {}
                total_generation = 0

                for row in rows:
                    time, psr_type, mw = row
                    generation_mix[psr_type] = mw
                    total_generation += mw

                if total_generation > 0:
                    co2_intensity = self._calculate_intensity(generation_mix, total_generation)
                    renewable_pct = self._get_renewable_pct(generation_mix, total_generation)

                    return {
                        'timestamp': rows[0][0],
                        'country': country,
                        'co2_intensity': round(co2_intensity, 2),
                        'generation_mix': self._format_mix(generation_mix),
                        'renewable_pct': round(renewable_pct, 1),
                        'fossil_pct': round(100 - renewable_pct, 1),
                        'status': self._get_status(co2_intensity),
                        'total_generation_mw': round(total_generation, 2),
                        'data_source': 'Database'
                    }

            # No database data - try API
            logger.warning(f"No data found for {country} in database, trying API...")
            return self._fetch_from_api(country)

        except Exception as e:
            logger.error(f"Error getting intensity: {e}")
            return self._fetch_from_api(country)

    def get_24h_forecast(self, country: str, hours: int = 24) -> Optional[pd.DataFrame]:
        """
        Get CO2 intensity forecast for next N hours (based on historical patterns)

        Args:
            country: Country code
            hours: Number of hours to forecast

        Returns:
            DataFrame with columns: [timestamp, co2_intensity, status, renewable_pct]
        """
        try:
            cursor = self.conn.cursor()
            zone_keys = get_zone_keys(country)

            # Get average generation by hour of day for past 30 days
            cursor.execute("""
                SELECT
                    EXTRACT(HOUR FROM time)::int as hour_of_day,
                    psr_type,
                    AVG(actual_generation_mw) as avg_generation
                FROM generation_actual
                WHERE bidding_zone_mrid = ANY(%s)
                AND time >= NOW() - INTERVAL '30 days'
                AND time < NOW()
                GROUP BY hour_of_day, psr_type
                ORDER BY hour_of_day, psr_type
            """, (zone_keys,))

            rows = cursor.fetchall()
            cursor.close()

            if not rows:
                return None

            # Build forecast
            forecast_data = []
            now = datetime.now().replace(minute=0, second=0, microsecond=0)

            for i in range(hours):
                forecast_time = now + timedelta(hours=i)
                hour_of_day = forecast_time.hour

                # Get generation for this hour
                mix = {}
                total_gen = 0

                for row in rows:
                    h, psr_type, avg_gen = row
                    if h == hour_of_day:
                        mix[psr_type] = avg_gen
                        total_gen += avg_gen

                if total_gen > 0:
                    intensity = self._calculate_intensity(mix, total_gen)
                    renewable_pct = self._get_renewable_pct(mix, total_gen)

                    forecast_data.append({
                        'timestamp': forecast_time,
                        'hour': hour_of_day,
                        'co2_intensity': round(intensity, 2),
                        'renewable_pct': round(renewable_pct, 1),
                        'status': self._get_status(intensity)
                    })

            return pd.DataFrame(forecast_data)

        except Exception as e:
            logger.error(f"Forecast error: {e}")
            return None

    def get_green_hours(self, country: str, threshold: float = 200) -> Optional[Dict]:
        """
        Identify "green hours" - times when CO2 intensity is below threshold

        Args:
            country: Country code
            threshold: CO2 intensity threshold (gCO2/kWh)

        Returns:
            {
                'green_hours': [list of hours with timestamps],
                'worst_hours': [list of worst hours],
                'best_hour': datetime,
                'savings_potential': {
                    'cost_reduction_pct': float,
                    'co2_reduction_tons': float
                }
            }
        """
        forecast_df = self.get_24h_forecast(country)

        if forecast_df is None or forecast_df.empty:
            return None

        # Find green hours
        green = forecast_df[forecast_df['co2_intensity'] <= threshold]
        worst = forecast_df.nlargest(3, 'co2_intensity')
        best = forecast_df.loc[forecast_df['co2_intensity'].idxmin()]

        # Calculate savings
        avg_intensity = forecast_df['co2_intensity'].mean()
        green_intensity = green['co2_intensity'].mean() if not green.empty else avg_intensity

        if green_intensity > 0 and avg_intensity > 0:
            co2_reduction_pct = ((avg_intensity - green_intensity) / avg_intensity) * 100
        else:
            co2_reduction_pct = 0

        return {
            'green_hours': green[['timestamp', 'co2_intensity', 'renewable_pct']].to_dict('records'),
            'best_hour': {
                'timestamp': best['timestamp'],
                'co2_intensity': best['co2_intensity'],
                'renewable_pct': best['renewable_pct']
            },
            'worst_hours': worst[['timestamp', 'co2_intensity', 'renewable_pct']].to_dict('records'),
            'average_intensity': round(avg_intensity, 2),
            'savings_potential': {
                'co2_reduction_pct': round(co2_reduction_pct, 1),
                'cost_reduction_pct': round(co2_reduction_pct * 0.8, 1)  # Rough estimate
            }
        }

    def calculate_charging_impact(
        self,
        num_evs: int = 100,
        daily_charging_mwh: float = 2.0,
        charge_at_peak: bool = True
    ) -> Dict:
        """
        Calculate cost and emissions impact of EV charging timing

        Args:
            num_evs: Number of electric vehicles
            daily_charging_mwh: Daily energy per EV (MWh)
            charge_at_peak: If True, assumes peak hour charging; False assumes best hour

        Returns:
            {
                'scenario_peak': {...},
                'scenario_green': {...},
                'monthly_savings': {...},
                'annual_savings': {...},
                'environmental_impact': {...}
            }
        """

        # Default assumptions
        peak_price = 85  # €/MWh at peak
        green_price = 25  # €/MWh at green hours
        peak_intensity = 450  # gCO2/kWh at peak
        green_intensity = 120  # gCO2/kWh at green hours

        daily_total_mwh = num_evs * daily_charging_mwh
        monthly_total_mwh = daily_total_mwh * 30
        annual_total_mwh = daily_total_mwh * 365

        # Peak scenario
        peak_cost_monthly = monthly_total_mwh * peak_price
        peak_emissions_monthly = (monthly_total_mwh * 1000) * (peak_intensity / 1000)  # tons CO2

        # Green scenario
        green_cost_monthly = monthly_total_mwh * green_price
        green_emissions_monthly = (monthly_total_mwh * 1000) * (green_intensity / 1000)

        # Calculate savings
        cost_savings_monthly = peak_cost_monthly - green_cost_monthly
        emissions_savings_monthly = peak_emissions_monthly - green_emissions_monthly

        return {
            'scenario_peak': {
                'monthly_cost': round(peak_cost_monthly, 2),
                'monthly_emissions_tons': round(peak_emissions_monthly, 2),
                'monthly_emissions_description': f"{int(peak_emissions_monthly / 100)} tons (= {int(peak_emissions_monthly / 5.5)} trees)"
            },
            'scenario_green': {
                'monthly_cost': round(green_cost_monthly, 2),
                'monthly_emissions_tons': round(green_emissions_monthly, 2),
                'monthly_emissions_description': f"{int(green_emissions_monthly / 100)} tons (= {int(green_emissions_monthly / 5.5)} trees)"
            },
            'monthly_savings': {
                'cost': round(cost_savings_monthly, 2),
                'cost_pct': round((cost_savings_monthly / peak_cost_monthly) * 100, 1),
                'emissions_tons': round(emissions_savings_monthly, 2),
                'emissions_pct': round((emissions_savings_monthly / peak_emissions_monthly) * 100, 1)
            },
            'annual_savings': {
                'cost': round(cost_savings_monthly * 12, 2),
                'emissions_tons': round(emissions_savings_monthly * 12, 2),
                'trees_equivalent': int((emissions_savings_monthly * 12) / 5.5)
            }
        }

    # Private helper methods

    def _calculate_intensity(self, generation_mix: Dict, total_generation: float) -> float:
        """Calculate CO2 intensity from generation mix"""
        if total_generation == 0:
            return 0

        total_emissions = 0
        for psr_type, mw in generation_mix.items():
            factor = self.EMISSION_FACTORS.get(psr_type, 0)
            total_emissions += mw * factor

        return total_emissions / total_generation

    def _get_renewable_pct(self, generation_mix: Dict, total_generation: float) -> float:
        """Calculate renewable percentage"""
        renewable_types = ['B01', 'B09', 'B10', 'B11', 'B12', 'B13', 'B16', 'B17', 'B18', 'B19', 'B20']
        renewable_gen = sum(generation_mix.get(t, 0) for t in renewable_types)
        return (renewable_gen / total_generation * 100) if total_generation > 0 else 0

    def _get_status(self, intensity: float) -> str:
        """Get status based on intensity"""
        if intensity < 150:
            return 'LOW'
        elif intensity < 300:
            return 'MODERATE'
        elif intensity < 500:
            return 'HIGH'
        else:
            return 'CRITICAL'

    def _format_mix(self, generation_mix: Dict) -> Dict:
        """Format generation mix with names and percentages"""
        total = sum(generation_mix.values())

        formatted = {}
        for psr_type, mw in sorted(generation_mix.items(), key=lambda x: x[1], reverse=True):
            if mw > 0:
                name = self.PSR_NAMES.get(psr_type, psr_type)
                pct = (mw / total * 100) if total > 0 else 0
                formatted[name] = {
                    'mw': round(mw, 2),
                    'pct': round(pct, 1),
                    'emissions': round(mw * self.EMISSION_FACTORS.get(psr_type, 0), 0)
                }

        return formatted


# Test the service
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    from src.db.connection import get_connection

    logging.basicConfig(level=logging.INFO)

    conn = get_connection()
    service = CarbonIntensityService(conn)

    # Test current intensity
    current = service.get_current_intensity("DE")
    if current:
        print(f"\n✅ Current CO2 Intensity (DE): {current['co2_intensity']} gCO2/kWh")
        print(f"   Status: {current['status']}")
        print(f"   Renewable: {current['renewable_pct']}%")

    # Test forecast
    forecast = service.get_24h_forecast("DE", hours=6)
    if forecast is not None:
        print(f"\n✅ 24h Forecast:")
        print(forecast.head())

    # Test green hours
    green = service.get_green_hours("DE")
    if green:
        print(f"\n✅ Green Hours: {len(green['green_hours'])} hours below 200 gCO2/kWh")
        print(f"   Best hour: {green['best_hour']['timestamp']}")
        print(f"   CO2 reduction potential: {green['savings_potential']['co2_reduction_pct']}%")

    # Test EV charging impact
    impact = service.calculate_charging_impact(num_evs=100)
    print(f"\n✅ EV Charging Impact (100 vehicles):")
    print(f"   Monthly savings: €{impact['monthly_savings']['cost']:,.0f}")
    print(f"   Annual savings: €{impact['annual_savings']['cost']:,.0f}")
    print(f"   CO2 prevented: {impact['annual_savings']['emissions_tons']:,.0f} tons/year")

    conn.close()
