# Cygnet Energy - European Grid Intelligence Platform

CYGNET Energy  
Real-time carbon intelligence on top of ENTSO-E data, built as an interview-ready engineering project.  

***

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
- **Issues:** [GitHub Issues](https://github.com/yasharnaghdi/cygnet-energy/issues)

## Acknowledgments

- ENTSO-E Transparency Platform for real-time grid data
- TimescaleDB for time-series database optimization
- FastAPI community for web framework

---

**Last Updated:** January 2025  
**Version:** 0.1.0 (MVP)  
**Status:** Active Development
