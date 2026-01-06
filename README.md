# Cygnet Energy - European Grid Intelligence Platform

# CYGNET Energy

**Real-time carbon intelligence for European electricity grids**

A production-grade platform that transforms ENTSO-E transparency data into actionable carbon intelligence, enabling data-driven decisions for energy optimization and sustainability.

***

## Project Overview

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

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/cygnet-energy.git
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


## Contact & Support

- **Author:** Yashar Naghdi
- **GitHub:** [@yasharnaghdi](https://github.com/yasharnaghdi)
- **Email:** he@yasharnaghdi.com
- **Issues:** [GitHub Issues](https://github.com/yasharnaghdi/cygnet-energy/issues)

## Acknowledgments

- ENTSO-E Transparency Platform for real-time grid data
- TimescaleDB for time-series database optimization
- FastAPI community for web framework

---

**Last Updated:** January 2025
**Version:** 0.1.0 (MVP)
**Status:** Active Development
