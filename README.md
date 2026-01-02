# Cygnet Energy - European Grid Intelligence Platform

**Real-time electricity system data collection and analysis from ENTSO-E Transparency Platform**

## Project Overview

Cygnet Energy is a production-grade data platform for ingesting, processing, and analyzing real-time electricity grid data from 39 European countries. The system collects 15-minute interval measurements of generation, consumption, cross-border flows, and unit unavailability from the ENTSO-E Transparency Platform.

**Status:** MVP Phase (Germany single-zone)  
**Target Scale:** 39 countries / 600+ cross-border pairs  
**Data Freshness:** <60 minutes (99% achieved)  
**API Response Time:** <5 seconds (P95)

## Architecture

### Technology Stack

- **Database:** PostgreSQL 14+ with TimescaleDB extension (time-series optimization)
- **API:** FastAPI (async Python web framework)
- **Scheduler:** APScheduler (background task scheduling)
- **HTTP Client:** requests library with exponential backoff
- **Validation:** Pydantic v2
- **Monitoring:** Prometheus metrics + Grafana dashboards (Phase 2)

### Key Components

```
┌─────────────────────────────────────────────────────────────┐
│ ENTSO-E Transparency Platform (XML API)                     │
│ - Generation Actual (GL_GenerationActual_A)                 │
│ - Load Actual (AL_LoadData)                                 │
│ - Physical Flows (cross-border)                             │
│ - Unavailability (outages/maintenance)                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │ Data Collection Service      │
        │ - XML parsing                │
        │ - Rate-limit handling (429)  │
        │ - Batch validation           │
        │ - Error recovery             │
        └──────────────┬───────────────┘
                       │
                       ▼
        ┌──────────────────────────────────┐
        │ TimescaleDB (PostgreSQL)         │
        │ - 4 hypertables (7-day chunks)   │
        │ - Compression (14d+ auto)        │
        │ - Composite indexes              │
        │ - ~110GB / 5 years (compressed)  │
        └──────────────┬───────────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │ REST API Layer (FastAPI)     │
        │ - /generation/current        │
        │ - /analysis/renewable-pct    │
        │ - /monitoring/freshness      │
        └──────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        ▼                             ▼
   Analytics                     Dashboards
   (SQL queries)                 (Grafana/UI)
```

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 14+ (with TimescaleDB extension)
- Git

### Installation

```bash
# Clone repository
git clone https://github.com/yasharnaghdi/cygnet-energy.git
cd cygnet-energy

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate          # macOS/Linux
# OR
venv\Scripts\activate            # Windows

# Install dependencies
pip install poetry
poetry install

# Configure environment
cp config/config.yaml.example config/config.yaml
# Edit config.yaml with your ENTSO-E API key and database credentials

# Run database schema initialization
python scripts/init_db.py

# Start data collection service
python -m src.collector.main

# In another terminal, start API server
python -m uvicorn src.api:app --reload --host 0.0.0.0 --port 8000
```

### Verify Installation

```bash
# Check API health
curl http://localhost:8000/health

# Fetch latest generation data (Germany)
curl "http://localhost:8000/api/v1/generation/current?bidding_zone=DE"

# Get renewable penetration (last 24 hours)
curl "http://localhost:8000/api/v1/analysis/renewable-fraction?bidding_zone=DE&hours=24"
```

## Configuration

### Environment Variables

```bash
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=cygnet_energy
DB_USER=postgres
DB_PASSWORD=your_password

# ENTSO-E API
ENTSO_API_KEY=your_api_key_from_transparency_platform
ENTSO_MAX_RETRIES=5
ENTSO_RATE_LIMIT=10  # requests per second

# Service
LOG_LEVEL=INFO
API_PORT=8000
API_WORKERS=4
```

### Database Configuration

**PostgreSQL Instance Sizing (Production):**

| Component | Recommendation | Notes |
|-----------|----------------|-------|
| CPU | 8 cores | Scale to 16 for >1000 concurrent users |
| Memory | 32 GB | 25% shared buffers, 75% OS cache |
| Storage | 500 GB SSD | 300 GB data, 50 GB WAL, 150 GB backups |
| Retention | 5 years | Automatic purge of data >5 years old |

**TimescaleDB Chunk Strategy:**

- Chunk interval: 7 days (balance compression vs. query overhead)
- Compression threshold: 14 days (automatic)
- Compression ratio: 10-20x for repetitive numeric data
- Estimated size: 110 GB / 5 years (compressed from 550 GB raw)

## Data Schema

### Hypertables (Time-Series)

```sql
generation_actual      -- Generation by zone & type (15-min intervals)
load_actual            -- Consumption by zone (15-min intervals)
crossborder_flows      -- Flows between zones (15-min intervals)
unavailability_units   -- Generator outages (variable frequency)
```

### Metadata Tables

```sql
metadata               -- Zone/generator master data (non-hypertable)
```

## API Endpoints

### Generation

```
GET /api/v1/generation/current
GET /api/v1/generation/history?bidding_zone=DE&hours=24
POST /api/v1/generation/forecast?bidding_zone=DE&horizon_hours=6
```

### Analysis

```
GET /api/v1/analysis/renewable-fraction?hours=24
GET /api/v1/analysis/grid-stress?bidding_zone=DE
GET /api/v1/analysis/demand-forecast?bidding_zone=DE
```

### Monitoring

```
GET /api/v1/monitoring/freshness
GET /api/v1/monitoring/anomalies?hours=24
GET /health
```

## Development

### Running Tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests (requires running database)
pytest tests/integration/ -v

# With coverage report
pytest --cov=src --cov-report=html
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint
ruff check src/ tests/

# Type checking
mypy src/

# All checks
bash scripts/lint.sh
```

### Docker Build

```bash
# Build image
docker build -t cygnet-energy:latest .

# Run container
docker run -p 8000:8000 \
  -e DB_HOST=postgres \
  -e ENTSO_API_KEY=your_key \
  cygnet-energy:latest
```

## Monitoring

### Prometheus Metrics

Key metrics for monitoring:

- `entso_api_requests_total` - API call count (success/failure)
- `entso_api_request_duration_seconds` - Collection latency
- `database_insertion_lag_seconds` - Data freshness
- `data_freshness_seconds` - Age of latest record per zone
- `collection_job_duration_seconds` - Collection job performance
- `api_query_latency_seconds` - REST API response time

### Alerting Rules

```yaml
# Data Staleness Alert
- alert: DataStaleness
  expr: data_freshness_seconds > 3600
  for: 10m
  annotations:
    summary: "Zone {{ $labels.bidding_zone }} stale for >1 hour"

# API Error Rate
- alert: APIErrorRate
  expr: rate(entso_api_requests_total{status=~"5.."}[5m]) > 0.1
  annotations:
    summary: "ENTSO-E API error rate >10%"

# Collection Delay
- alert: SlowCollection
  expr: collection_job_duration_seconds > 300
  annotations:
    summary: "Collection job exceeds 5 minutes"
```

## Project Phases

### Phase 1: MVP (Current)
- [x] Single country (Germany) data collection
- [x] Database schema & TimescaleDB setup
- [x] ENTSO-E API integration
- [x] Basic FastAPI endpoints
- [ ] Unit & integration tests (80%+ coverage)
- [ ] Docker containerization

### Phase 2: Multi-Country
- [ ] Extend to 39 countries
- [ ] SMARD fallback (German data redundancy)
- [ ] Advanced analytics & aggregations
- [ ] Grafana dashboard
- [ ] CI/CD pipeline (GitHub Actions)

### Phase 3: Intelligence
- [ ] Weather integration (wind/solar forecasting)
- [ ] Machine learning anomaly detection
- [ ] ARIMA/Prophet demand forecasting
- [ ] Carbon intensity calculation

### Phase 4: Scalability
- [ ] Kubernetes deployment
- [ ] Distributed scheduler (Celery + Redis)
- [ ] Event streaming (WebSocket, <1-min latency)
- [ ] Multi-region support

### Phase 5: Production
- [ ] Enterprise security (OAuth2, mTLS)
- [ ] Usage billing & quotas
- [ ] SLA monitoring
- [ ] Regulatory compliance (GDPR, energy regulations)

## Troubleshooting

### Data Collection Not Running

```bash
# Check logs
tail -f logs/collector.log

# Verify database connection
python -c "from src.db.connection import test_connection; test_connection()"

# Test ENTSO-E API connectivity
curl -I "https://web-api.tp.entsoe.eu/api/GL_GenerationActual_A?securityToken=YOUR_KEY"
```

### Database Connection Issues

```bash
# Test PostgreSQL connection
psql -h localhost -U postgres -d cygnet_energy -c "SELECT version();"

# Check TimescaleDB extension
psql -d cygnet_energy -c "SELECT * FROM pg_extension WHERE extname = 'timescaledb';"

# Verify hypertables
psql -d cygnet_energy -c "SELECT * FROM timescaledb_information.hypertables;"
```

### Performance Optimization

```sql
-- Check index usage
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;

-- Analyze query performance
EXPLAIN ANALYZE
SELECT * FROM generation_actual
WHERE bidding_zone_mrid = 'DE'
  AND time > now() - interval '24 hours'
ORDER BY time DESC;
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
