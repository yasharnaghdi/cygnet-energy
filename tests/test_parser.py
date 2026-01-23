from src.api.parser import EntsoEXMLParser


def test_parse_generation_xml_with_minimum_fields():
    xml_string = """<?xml version="1.0" encoding="UTF-8"?>
    <Publication_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-6:generationloaddocument:3:0">
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

    df = EntsoEXMLParser.parse_generation_xml(xml_string)

    assert df is not None
    assert len(df) == 1
    assert df.iloc[0]["psr_type"] == "B18"
    assert df.iloc[0]["actual_generation_mw"] == 1200.5


def test_parse_generation_xml_returns_none_on_empty_timeseries():
    xml_string = """<?xml version="1.0" encoding="UTF-8"?>
    <Publication_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-6:generationloaddocument:3:0">
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
                </Point>
            </Period>
        </TimeSeries>
    </Publication_MarketDocument>"""

    df = EntsoEXMLParser.parse_generation_xml(xml_string)

    assert df is None
