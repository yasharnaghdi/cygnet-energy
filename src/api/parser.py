"""
XML Parser for ENTSO-E API responses

Converts raw XML from ENTSO-E Transparency Platform to structured data
"""
from typing import List, Dict, Optional
from datetime import datetime
import xml.etree.ElementTree as ET
from lxml import etree
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class EntsoEXMLParser:
    """Parse ENTSO-E XML responses into structured data"""

    # ENTSO-E namespace
    NS = {
        'ns': 'urn:iec62325.351:tc57wg16:451-6:generationloaddocument:3:0'
    }

    # PSR Type mappings (Production Source Type)
    PSR_TYPES = {
        'B01': 'Biomass',
        'B02': 'Fossil Brown Coal/Lignite',
        'B03': 'Fossil Coal-Derived Gas',
        'B04': 'Fossil Gas',
        'B05': 'Fossil Hard Coal',
        'B06': 'Fossil Oil',
        'B07': 'Fossil Oil Shale',
        'B08': 'Fossil Peat',
        'B09': 'Geothermal',
        'B10': 'Hydro Pumped Storage',
        'B11': 'Hydro Run-of-River and Ponds',
        'B12': 'Hydro Reservoir',
        'B13': 'Marine',
        'B14': 'Nuclear',
        'B15': 'Other',
        'B16': 'Other Renewable',
        'B17': 'Solar',
        'B18': 'Solar Photovoltaic',
        'B19': 'Wind Onshore',
        'B20': 'Wind Offshore',
        'B21': 'Waste',
    }

    @staticmethod
    def parse_generation_xml(xml_string: str) -> Optional[pd.DataFrame]:
        """
        Parse actual generation XML response

        Args:
            xml_string: Raw XML from ENTSO-E API

        Returns:
            DataFrame with columns: [time, psr_type, actual_generation_mw]
        """
        try:
            root = ET.fromstring(xml_string)
            data = []

            # Find all TimeSeries elements
            for timeseries in root.findall('.//ns:TimeSeries', EntsoEXMLParser.NS):

                # Get PSR type
                psr_elem = timeseries.find('ns:MktPSRType/ns:psrType', EntsoEXMLParser.NS)
                if psr_elem is None:
                    continue
                psr_type = psr_elem.text

                # Get all Period/Points
                for period in timeseries.findall('.//ns:Period', EntsoEXMLParser.NS):
                    time_interval = period.find('ns:timeInterval', EntsoEXMLParser.NS)
                    if time_interval is None:
                        continue

                    start = time_interval.find('ns:start', EntsoEXMLParser.NS)
                    if start is None or start.text is None:
                        continue

                    start_time = datetime.fromisoformat(start.text.replace('Z', '+00:00'))

                    # Get resolution (PT60M = hourly)
                    resolution = period.find('ns:resolution', EntsoEXMLParser.NS)
                    resolution_str = resolution.text if resolution is not None else 'PT60M'

                    # Parse points
                    for point in period.findall('ns:Point', EntsoEXMLParser.NS):
                        position = point.find('ns:position', EntsoEXMLParser.NS)
                        quantity = point.find('ns:quantity', EntsoEXMLParser.NS)

                        if position is None or quantity is None:
                            continue

                        try:
                            pos = int(position.text)
                            qty = float(quantity.text)
                        except (ValueError, TypeError):
                            continue

                        # Calculate timestamp (position is 1-indexed)
                        from datetime import timedelta
                        timestamp = start_time + timedelta(hours=pos - 1)

                        data.append({
                            'time': timestamp,
                            'psr_type': psr_type,
                            'actual_generation_mw': qty
                        })

            if not data:
                logger.warning("No data extracted from XML")
                return None

            df = pd.DataFrame(data)
            logger.info(f"✅ Parsed {len(df)} records from XML")
            return df

        except ET.ParseError as e:
            logger.error(f"❌ XML Parse Error: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Parsing Error: {e}")
            return None

    @staticmethod
    def parse_load_xml(xml_string: str) -> Optional[pd.DataFrame]:
        """
        Parse actual total load XML response

        Args:
            xml_string: Raw XML from ENTSO-E API

        Returns:
            DataFrame with columns: [time, total_load_mw]
        """
        try:
            root = ET.fromstring(xml_string)
            data = []

            for timeseries in root.findall('.//ns:TimeSeries', EntsoEXMLParser.NS):
                for period in timeseries.findall('.//ns:Period', EntsoEXMLParser.NS):
                    time_interval = period.find('ns:timeInterval', EntsoEXMLParser.NS)
                    if time_interval is None:
                        continue

                    start = time_interval.find('ns:start', EntsoEXMLParser.NS)
                    if start is None:
                        continue

                    start_time = datetime.fromisoformat(start.text.replace('Z', '+00:00'))

                    for point in period.findall('ns:Point', EntsoEXMLParser.NS):
                        position = point.find('ns:position', EntsoEXMLParser.NS)
                        quantity = point.find('ns:quantity', EntsoEXMLParser.NS)

                        if position is None or quantity is None:
                            continue

                        try:
                            pos = int(position.text)
                            qty = float(quantity.text)
                        except ValueError:
                            continue

                        from datetime import timedelta
                        timestamp = start_time + timedelta(hours=pos - 1)

                        data.append({
                            'time': timestamp,
                            'total_load_mw': qty
                        })

            if not data:
                logger.warning("No load data extracted from XML")
                return None

            df = pd.DataFrame(data)
            logger.info(f"✅ Parsed {len(df)} load records from XML")
            return df

        except Exception as e:
            logger.error(f"❌ Load Parse Error: {e}")
            return None

    @staticmethod
    def get_psr_name(psr_type: str) -> str:
        """Get human-readable name for PSR type"""
        return EntsoEXMLParser.PSR_TYPES.get(psr_type, f"Unknown ({psr_type})")


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test with sample XML
    sample_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <Publication_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-1:generationloaddocumenttype:3:0">
        <TimeSeries>
            <MktPSRType>
                <psrType>B18</psrType>
            </MktPSRType>
            <Period>
                <timeInterval>
                    <start>2020-06-01T00:00Z</start>
                </timeInterval>
                <resolution>PT60M</resolution>
                <Point>
                    <position>1</position>
                    <quantity>1200.5</quantity>
                </Point>
            </Period>
        </TimeSeries>
    </Publication_MarketDocument>"""

    parser = EntsoEXMLParser()
    df = parser.parse_generation_xml(sample_xml)
    if df is not None:
        print(df.head())
