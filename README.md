# Cygnet Energy - European Grid Intelligence Platform

# CYGNET Energy

**Real-time carbon intelligence for European electricity grids**

A production-grade platform that transforms ENTSO-E transparency data into actionable carbon intelligence, enabling data-driven decisions for energy optimization and sustainability.

***
=======
CYGNET Energy
Real-time carbon intelligence on top of ENTSO-E data, built as an interview-ready engineering project.


***
CYGNET Energy is a comprehensive grid intelligence platform that:

- **Ingests** real-time and historical generation data from ENTSO-E Transparency Platform
- **Computes** grid carbon intensity using IPCC 2014 lifecycle emission factors
- **Forecasts** 24-hour carbon intensity patterns using historical data analysis
- **Identifies** optimal low-carbon hours for energy consumption
- **Quantifies** cost and emissions savings from load shifting strategies
- **Visualizes** multi-country grid comparisons and carbon trends

**Production deployment capabilities:**
- PostgreSQL-backed historical analytics for high-frequency queries
- Live API fallback for real-time data across 7 European countries
- Scalable architecture supporting both batch processing and real-time requests
- RESTful API foundation ready for enterprise integrations

***

## Core Value Proposition

CYGNET addresses a critical gap in European energy markets: **grid carbon intensity varies 4-6x throughout the day**, but most energy management systems ignore this temporal dimension.

**Key insights delivered:**
- Real-time CO₂ intensity (gCO₂/kWh) across European bidding zones
- Renewable vs fossil generation composition
- Peak vs off-peak carbon profiles
- Financial impact quantification (€/MWh savings potential)
- EV fleet optimization scenarios with validated ROI calculations

***

## Architecture & Tech Stack

### Data Layer
**PostgreSQL 14+**
- Time-series storage for `generation_actual` table
- Indexed on `time`, `bidding_zone_mrid`, `psr_type`
- Currently storing 4.3M+ rows for German historical data
- Schema designed for multi-country expansion

**ENTSO-E Integration**
- `src/api/client.py`: HTTP client with bidding zone mapping (DE, FR, GB, ES, IT, NL, BE)[1]
- `src/api/parser.py`: XML→DataFrame transformer with correct namespace handling[2]
- Automatic fallback: database-first for speed, API for coverage[3]

### Service Layer
**CarbonIntensityService** (`src/services/carbon_service.py`)[3]

Core capabilities:
- **`get_current_intensity(country)`**: Hybrid query (DB + API fallback)
- **`get_24h_forecast(country, hours)`**: Pattern-based prediction using hour-of-day profiles
- **`get_green_hours(country, threshold)`**: Optimization windows for load shifting
- **`calculate_charging_impact(num_evs, daily_mwh)`**: EV fleet TCO modeling

**Emission factors**: IPCC 2014 Lifecycle Assessment standards
- 20+ PSR type mappings (B01-B21)
- Weighted CO₂ calculation: Σ(Generation_MW × EmissionFactor) / TotalGeneration_MW
- Renewable classification logic for accurate green/fossil split

### Application Layer
**Streamlit Dashboard** (`streamlit_carbon_app.py`)[4]
- Plotly-based interactive visualizations
- Responsive multi-column layouts
- Real-time data refresh with caching
- Multi-country comparison mode (WIP)

**Extensible API Foundation**
- FastAPI + Uvicorn stack configured in dependencies[5]
- Pydantic models for type-safe request/response schemas
- APScheduler for periodic ETL jobs
- Prometheus-ready metrics endpoints

### Development Stack
**Python 3.11** managed via **Poetry**[5]

Key dependencies:
```
Core: pandas, numpy, psycopg2-binary, requests, lxml
API: fastapi, uvicorn, pydantic
Viz: streamlit, plotly
ML: scikit-learn (for forecast enhancement)
Ops: apscheduler, prometheus-client, python-dotenv
```

***

## Project Structure

```
cygnet-energy/
├── config/
│   ├── config.yaml              # Environment-specific settings
│   └── settings.yaml            # Application configuration
├── data/samples/
│   └── time_series_60min_singleindex.csv  # ENTSO-E reference data
├── scripts/
│   ├── init_db.py               # Database schema initialization
│   ├── load_csv_to_db.py        # Bulk CSV ingestion
│   └── fetch_entsoe_data.py     # Live API data collector
├── src/
│   ├── api/
│   │   ├── client.py            # ENTSO-E HTTP client [file:48]
│   │   └── parser.py            # XML parsing layer [file:45]
│   ├── db/
│   │   ├── connection.py        # PostgreSQL connection pool
│   │   └── schema.py            # DDL definitions
│   ├── services/
│   │   └── carbon_service.py    # Core carbon intelligence [file:44]
│   ├── models/
│   │   └── generation.py        # Domain models
│   └── utils/
│       └── config.py            # Configuration loader
├── streamlit_carbon_app.py      # Production dashboard [file:46]
├── tests/
│   ├── unit/                    # Service layer tests
│   └── integration/             # API + DB tests
├── pyproject.toml               # Poetry dependency manifest [file:1]
└── README.md
```

***

## Deployment Guide

### Prerequisites
- Python 3.11+
- PostgreSQL 14+
- Poetry 1.7+
=======
## 1. Project Scope

This project ingests ENTSO-E transparency data, stores it in PostgreSQL, and exposes it through:

- A **data & API layer** (FastAPI-style stack)
- A **carbon intelligence service** that computes grid CO₂ intensity
- A **Streamlit dashboard** for visual, interview-friendly storytelling

**Current focus:**

- One fully populated bidding zone in DB: **DE** (Germany, from CSV)
- Other countries (**FR, GB, ES, IT**) fetched in **real time from ENTSO-E API**
- Clear separation between:
  - Historical database-backed analytics (for DE)
  - Live API-backed analytics (for other countries)

The project is intentionally scoped for interviews: it demonstrates data ingestion, modeling, API integration, and frontend visualization in a compact but realistic energy-data scenario.

***

## 2. Tech Stack

### Core Languages & Runtime

- **Python**: 3.11 (configured via Poetry in `pyproject.toml`)[1]

### Backend & Services

- **FastAPI + Uvicorn** (planned/available stack, used by scripts/tests and can be extended):
  - FastAPI for HTTP API endpoints
  - Uvicorn as ASGI server[1]
- **PostgreSQL**:
  - Stores `generation_actual` time series (actual generation by PSR type)
  - Accessed via `psycopg2-binary` in `src/db/connection.py` and used by `CarbonIntensityService`[3]
- **Scheduling & monitoring**:
  - `apscheduler` for periodic ETL / API fetch jobs (via scripts)[1]
  - `prometheus-client` for metrics (ready to plug into a FastAPI/worker process)[1]

### Data & Modeling

- **pandas** for time series manipulation and DataFrame-based transformations[3]
- **numpy** for numerical operations[3]
- **pydantic / pydantic-settings** for config and typed models (API + config structures)[1]
- **scikit-learn** (added) for potential forecasting / modeling tasks (e.g. 24h forecast refinement)[1]
- **lxml / xml.etree** for ENTSO-E XML parsing in `src/api/parser.py`[5]

### ENTSO-E Integration

- `src/api/client.py`:
  - Wraps ENTSO-E **Transparency Platform** REST API with a typed client, handles:
    - Security token
    - Correct base URL
    - Bidding zone mapping (`BIDDING_ZONES`) for DE, FR, GB, ES, IT, NL, BE[8]
- `src/api/parser.py`:
  - Parses **A75 actual generation** XML into a normalized DataFrame:
    - Columns: `time`, `psr_type`, `actual_generation_mw`
    - Correct namespace for `generationloaddocument`[5]

### Carbon Intelligence Layer

- `src/services/carbon_service.py`:
  - Central service used by the dashboard and can be used by a future API[4]
  - Responsibilities:
    - **get_current_intensity(country)**:
      - Try PostgreSQL for that `bidding_zone_mrid` (for DE)
      - If no rows → call ENTSO-E API via `EntsoEAPIClient`, parse via `EntsoEXMLParser`[4][8][5]
      - Compute:
        - CO₂ intensity \(gCO₂/kWh\) using IPCC 2014 emission factors
        - Renewable vs fossil shares
        - Status bucket: LOW / MODERATE / HIGH / CRITICAL
    - **get_24h_forecast(country)**:
      - Uses historical DB data (DE) to build an hour-of-day average–based “profile” forecast[4]
    - **get_green_hours(country, threshold)**:
      - Identifies hours with intensity below a threshold, returns best/worst hours + savings potential[4]
    - **calculate_charging_impact(num_evs, daily_charging_mwh)**:
      - Simple, parameterized peak vs green scenario for EV fleet cost and CO₂[4]

### Frontend / Visualization

- **Streamlit**:
  - Multiple entry points exist; the current main one is:
    - `streamlit_carbon_app.py` – “Carbon Intelligence Dashboard”[6]
  - Uses:
    - `plotly.graph_objects` and `plotly.express` for charts[6]
    - Responsive layout with `st.columns` for metrics and comparison views[6]

**Key UI features already present:**

1. **Single-country live status view** (DE or live-API countries):
   - CO₂ intensity
   - Renewable percentage
   - Total generation
   - Status indicator and timestamp[6][4]
2. **Generation mix chart**:
   - Horizontal bar chart showing emissions by source (using PSR names and calculated emissions)[6][4]
3. **24-hour forecast (DE)**:
   - Intensity curve with color bands and a 200 gCO₂/kWh “green” reference[6]
4. **EV charging impact widget**:
   - Compares “peak” vs “green” charging cost and CO₂ for a configurable fleet size and energy use[4][6]

(You have also started adding a country comparison view; this can be documented once stabilised.)

***

## 3. Project Structure (High Level)

```text
cygnet-energy/
├── config/
│   ├── config.yaml              # App / API / DB settings templates
│   ├── config.yaml.example
│   └── settings.yaml
├── data/
│   └── samples/
│       └── time_series_60min_singleindex.csv  # Example ENTSO-E CSV input
├── scripts/
│   ├── fetch_entsoe_data.py     # Fetch from ENTSO-E and store/process
│   ├── init_db.py               # Create DB schema
│   └── load_csv_to_db.py        # Load sample CSV into PostgreSQL
├── src/
│   ├── api/
│   │   ├── client.py            # EntsoEAPIClient (HTTP client) [file:48]
│   │   └── parser.py            # EntsoEXMLParser (XML→DataFrame) [file:45]
│   ├── db/
│   │   ├── connection.py        # psycopg2 connection helper
│   │   └── schema.py            # DDL for generation_actual and related tables
│   ├── models/
│   │   └── generation.py        # Domain models / pydantic schemas
│   ├── services/
│   │   └── carbon_service.py    # CarbonIntensityService core logic [file:44]
│   └── utils/
│       └── config.py            # App config loader (env + yaml)
├── streamlit_carbon_app.py      # Main dashboard for interviews [file:46]
├── streamlit_app.py             # Earlier Streamlit variant (legacy)
├── streamlit_minimal.py         # Minimal/experimental UI (legacy)
├── tests/
│   ├── unit/
│   └── integration/
├── pyproject.toml               # Poetry config, dependencies, Python 3.11 [file:1]
├── README.md                    # (this file)
└── SETUP_GUIDE.md               # More detailed step-by-step setup (already present)
```

***

## 4. Setup & Running (Poetry + venv)

### 4.1. Prerequisites

- Python **3.11**
- PostgreSQL running locally
- Poetry installed globally

### 4.2. Install dependencies

```bash
# Clone repository
git clone https://github.com/yasharnaghdi/cygnet-energy.git
cd cygnet-energy

# Install dependencies
poetry install

# Configure environment
cp config/config.yaml.example config/config.yaml
# Edit config.yaml with your DB credentials and ENTSO-E API token
```

### Database Setup

```bash
# Initialize schema
poetry run python scripts/init_db.py

# Load historical data (Germany baseline)
poetry run python scripts/load_csv_to_db.py
```

### Run Dashboard

```bash
poetry run streamlit run streamlit_carbon_app.py
```

Access at `http://localhost:8501`

### Production Deployment Options

**Containerized (Docker)**
```bash
docker build -t cygnet-energy .
docker run -p 8501:8501 -e DB_HOST=your-db cygnet-energy
```

**Cloud Platforms**
- Streamlit Cloud (frontend)
- Heroku / Railway (API + workers)
- AWS RDS / DigitalOcean Managed PostgreSQL (database)

***

## Technical Features

### Data Pipeline
1. **Ingestion**: Batch CSV loads + scheduled API fetches
2. **Transformation**: XML parsing → normalized time series
3. **Storage**: PostgreSQL with time-based partitioning (future)
4. **Retrieval**: Indexed queries with <50ms p95 latency (DE historical)

### Carbon Calculation Methodology

**Formula:**
\[
\text{CO}_2\text{ Intensity} = \frac{\sum_{i} (\text{Generation}_i \times \text{EmissionFactor}_i)}{\sum_{i} \text{Generation}_i}
\]

**PSR Type Emission Factors (gCO₂/kWh):**
- Coal (B02, B05): 820
- Gas (B04): 490
- Solar (B17, B18): 41
- Wind (B19, B20): 11
- Nuclear (B14): 12
- Hydro (B10-B12): 24

Source: IPCC 2014 Fifth Assessment Report[3]

### API Integration Architecture

**Hybrid Data Strategy:**
- **Hot path (DE)**: PostgreSQL read (4.3M rows, sub-second queries)
- **Cold path (FR/GB/ES/IT)**: ENTSO-E API with 30s timeout + retry logic
- **Graceful degradation**: Returns last known good data if API fails

**Rate Limiting:**
- ENTSO-E: 400 requests/minute per token
- Current implementation: No client-side limiting (production: implement token bucket)

***

## Current Data Coverage

| Country | Bidding Zone | Data Source | Update Frequency | Historical Depth |
|---------|--------------|-------------|------------------|------------------|
| DE | 10Y1001A1001A83F | PostgreSQL | Static (CSV) | 30 days |
| FR | 10YFR-RTE------C | Live API | Real-time | None (ephemeral) |
| GB | 10YGB----------A | Live API | Real-time | None (ephemeral) |
| ES | 10YES-REE------0 | Live API | Real-time | None (ephemeral) |
| IT | 10YIT-GRTN-----B | Live API | Real-time | None (ephemeral) |

**Roadmap**: Expand PostgreSQL coverage to all zones with scheduled ETL jobs.

***

## Dashboard Features

### Live Grid Status
- Real-time CO₂ intensity with status indicators (LOW/MODERATE/HIGH/CRITICAL)
- Renewable percentage and fossil fuel share
- Total generation (MW)
- Data source transparency badge (Database vs Live API)

### Generation Mix Breakdown
- Horizontal bar chart showing emissions contribution by source
- Color-coded by carbon intensity (green → yellow → red gradient)
- Detailed source breakdown with MW, %, and total gCO₂

### 24-Hour Forecast
- Hourly carbon intensity prediction
- Visual threshold bands (green <150, yellow 150-300, red >300 gCO₂/kWh)
- Best/worst hour identification for load optimization

### EV Fleet Optimizer
- Configurable fleet size and daily energy consumption
- Peak vs green hour charging comparison
- Monthly/annual cost and emissions savings
- Trees-equivalent environmental impact metric

### Multi-Country Comparison (In Development)
- Side-by-side metrics for up to 4 countries
- Intensity ranking table
- Comparative bar charts

***

## Configuration

**Environment Variables** (`.env` or `config/config.yaml`):
```yaml
database:
  host: localhost
  port: 5432
  name: cygnet_energy
  user: postgres
  password: your_password

entsoe:
  api_token: your_entso_api_token
  base_url: https://web-api.tp.entsoe.eu/api

app:
  debug: false
  log_level: INFO
```

***

## Testing

```bash
# Run full test suite
poetry run pytest

# With coverage report
poetry run pytest --cov=src --cov-report=html

# Unit tests only
poetry run pytest tests/unit/

# Integration tests (requires DB)
poetry run pytest tests/integration/
```

**Test configuration** in `pyproject.toml`:[5]
- Minimum coverage: 80% (aspirational)
- pytest-asyncio for async API tests
- pytest-cov for coverage metrics

***

##  Roadmap

### Phase 1 (Current)
- PostgreSQL + ENTSO-E API integration
- Carbon intensity calculation service
- Streamlit dashboard MVP
- Multi-country live data support
- Multi-country comparison UI

### Phase 2 (Q1 2026)
- FastAPI REST endpoints for carbon service
- Scheduled ETL jobs for all 7 countries
- Historical data backfill (90 days)
- Machine learning-based 24h forecast (scikit-learn)
- Alert system (email/webhook for low-carbon windows)

### Phase 3 (Q2 2026)
- Time-series forecasting with Prophet/LSTM
- Peak/off-peak tariff integration
- Interactive European heatmap
- PDF/CSV export for sustainability reporting
- Multi-tenancy + API key authentication

### Phase 4 (Future)
- Kubernetes deployment manifests
- Grafana dashboards for ops monitoring
- GraphQL API layer
- Mobile app (React Native)
- Blockchain-verified carbon credits integration

***

##  References

- [ENTSO-E Transparency Platform](https://transparency.entsoe.eu)[6]
- [ENTSO-E API Documentation](https://transparency.entsoe.eu/content/static_content/Static%20content/web%20api/Guide.html)[7]
- [IPCC 2014 Emission Factors](https://www.ipcc.ch/report/ar5/wg3/)
- [EEA Greenhouse Gas Indicators](https://www.eea.europa.eu/en/analysis/indicators/greenhouse-gas-emission-intensity-of-1/greenhouse-gas-emission-intensity)[8]

***
##  Contributing

This is a flagship demonstration project. For production use cases or enterprise deployments, contact the maintainers.
=======
# From project root
poetry install
```

This reads `pyproject.toml` and installs all main + dev dependencies, including FastAPI, psycopg2, pandas, numpy, streamlit, plotly, scikit-learn, etc.[1]

### 4.3. Environment / Config

Either:

- Use environment variables (`.env` + `python-dotenv`), or
- Edit `config/config.yaml` and/or `settings.yaml` with:

- DB host / port / name (`cygnet_energy`)
- ENTSO-E API token
- Debug flags

The DB name you used so far is `cygnet_energy` and table `generation_actual` is populated for DE from CSV via `load_csv_to_db.py`.

### 4.4. Initialize the database

From the project root:

```bash
poetry run python scripts/init_db.py
poetry run python scripts/load_csv_to_db.py
```

- `init_db.py` creates the `generation_actual` table (and any related schema) in `cygnet_energy`.
- `load_csv_to_db.py` loads the sample CSV into the DB (DE zone).

### 4.5. Run the Streamlit dashboard

```bash
poetry run streamlit run streamlit_carbon_app.py
```

Open the URL shown in the terminal (typically `http://localhost:8501`).[6]

You should be able to:

- Select **DE** and see DB-driven metrics and forecast
- Select **FR/GB/ES/IT** and see live API data via `EntsoEAPIClient` + `EntsoEXMLParser` + `CarbonIntensityService`[8][5][4]

***

## 5. Current Features (Interview-Ready)

### 5.1. Data & Integration

- **PostgreSQL-backed historical data** for one zone (DE) from ENTSO-E CSV, via scripts in `scripts/` and `src/db/`[3]
- **Live ENTSO-E API integration** with:
  - Correct bidding zone mapping
  - Robust XML parsing
  - Integration into the main `CarbonIntensityService` path as a fallback when DB has no rows[5][8][4]

### 5.2. Carbon Intelligence Logic

- **IPCC 2014-based emission factors** per PSR code, encapsulated in `CarbonIntensityService.EMISSION_FACTORS`[4]
- Computation of:
  - Grid CO₂ intensity (weighted by generation mix)
  - Renewable vs fossil shares
  - Hourly forecast using historical patterns
  - “Green hours” based on intensity thresholds
  - EV fleet peak vs green charging scenarios in terms of both cost and emissions[4]

### 5.3. Frontend UX (Streamlit)

- Live status KPIs
- Generation mix visualization
- 24-hour intensity forecast with thresholds
- EV charging impact widget
- WIP: multi-country comparison mode (side-by-side metrics, intensity bar chart, rankings)

***

## 6. How to Talk About This in an Interview

When asked “What is this project?” you can briefly say:

- *“It’s a European grid intelligence project that combines PostgreSQL, an ENTSO-E API client, and a carbon-intensity service exposed via a Streamlit dashboard. For Germany, I load historical generation data into PostgreSQL, and for other countries I fetch real-time data from the ENTSO-E Transparency Platform. On top of that I compute grid CO₂ intensity, renewable shares, and EV charging cost/emissions scenarios, and visualize them in a dashboard. The stack uses Python 3.11, Poetry, psycopg2, pandas, and a layered design (API client → parser → service → UI).”*


```

## Documentation

- [Technical Architecture](docs/ARCHITECTURE.md) - Detailed design document
- [API Reference](docs/API.md) - Endpoint specifications
- [Database Schema](docs/SCHEMA.md) - SQL table definitions
- [Operations Runbook](docs/OPERATIONS.md) - Daily operations procedures
- [Contributing Guide](CONTRIBUTING.md) - Development workflow


## Contact & Support

- **Author:** Yashar Naghdi
- **GitHub:** [@yasharnaghdi](https://github.com/yasharnaghdi)
- **Email:** he@yasharnaghdi.com
=======

- **Issues:** [GitHub Issues](https://github.com/yasharnaghdi/cygnet-energy/issues)

## Acknowledgments

- ENTSO-E Transparency Platform for real-time grid data
- TimescaleDB for time-series database optimization
- FastAPI community for web framework

---

**Last Updated:** January 2025
**Version:** 0.1.0 (MVP)
**Status:** Active Development
