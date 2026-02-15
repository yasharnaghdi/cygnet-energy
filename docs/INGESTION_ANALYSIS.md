# Streamlit-to-API Ingestion Analysis

## Source File
- `main_app.py` (~99KB Streamlit app)

## Extracted ENTSO-E Fetch Logic
- `fetch_generation_data(conn, country, start_dt, end_dt)`:
  - Uses `EntsoEAPIClient.get_actual_generation(...)`.
  - Parses XML with `EntsoEXMLParser.parse_generation_xml(...)`.
  - Adds `bidding_zone_mrid`, `quality_code`, `data_source`.
  - Executes batched upsert into `generation_actual` on `(time, bidding_zone_mrid, psr_type)`.

## Extracted Transformation Logic
- Renewable mapping used in Streamlit:
  - Renewable PSR set: `B01`, `B17`, `B18`, `B19`, `B20`.
  - Renewable/fossil totals computed via SQL `SUM(CASE...)`.
- Aggregations used for operational views:
  - Hourly total generation from `generation_actual`.
  - Renewable percentage: `renewable_gen / total_gen * 100`.
  - Zone normalization via `get_zone_keys(...)` for country and EIC IDs.

## Database Interaction Patterns Observed
- Direct psycopg2 SQL cursor usage (no ORM in Streamlit path).
- Batch writes via `psycopg2.extras.execute_batch`.
- Read path combines:
  - Time-filtered generation reads.
  - Aggregate rollups for renewable/fossil breakdown.
  - Fallback demo mode if source tables are empty.

## New Service Mapping
- Implemented in `src/services/ingestion.py`:
  - `EntsoEIngestionService.fetch_and_store(zone, start, end)`.
  - Uses existing `EntsoEAPIClient` + `EntsoEXMLParser`.
  - Produces normalized records for:
    - `generation_records` (wind/solar/hydro/total per timestamp).
    - `load_records` (load per timestamp).
  - Upserts through SQLAlchemy models (`src/db/models.py`).
  - Exposes Prometheus metrics:
    - `cygnet_data_freshness_seconds`
    - `cygnet_scrape_duration_seconds`
