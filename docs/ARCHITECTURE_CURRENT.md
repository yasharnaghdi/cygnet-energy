# Cygnet Energy - Current Architecture (Feb 2026)

## System Components

### 1. Data Ingestion (Background)
- Service: `src/services/ingestion.py`
- Schedule: Every 15 minutes (manual trigger currently used)
- Sources: ENTSO-E Transparency API
- Zones: DE, FR, ES (expandable)
- Storage: PostgreSQL (`generation_records`, `load_records`, `price_records`)

### 2. FastAPI Backend
- Port: `8001` (or configured by `CYGNET_API_URL`)
- Auth: OIDC/JWT, with local bypass supported via `AUTH_BYPASS_DEV=true`
- Endpoints:
  - `GET /healthz` (liveness)
  - `GET /readyz` (readiness + Postgres check)
  - `GET /api/whoami` (token verification)
  - `GET /api/analytics/renewable-fraction` (time-series renewable %)
  - `GET /api/analytics/tight-hours` (grid stress proxy)
  - `GET /api/metrics` (Prometheus metrics)

### 3. Streamlit Frontend
- Port: `8501`
- Mode: Hybrid (legacy direct ENTSO-E + new FastAPI queries)
- New integration:
  - Sidebar backend status indicator
  - FastAPI-backed renewable fraction chart in Generation Analytics
  - Port conflict warning for `:8000`

### 4. Database
- Type: PostgreSQL 15
- Core tables:
  - `generation_records` (`zone`, `timestamp`, `wind_mw`, `solar_mw`, ...)
  - `load_records`
  - `price_records`
- Indexes: composite `(zone, timestamp)`
- Optional: TimescaleDB hypertables for larger retention windows

## Data Flow

```text
ENTSO-E API
    ↓
Ingestion Service (15m) → PostgreSQL
    ↓                        ↓
[New] FastAPI Backend ← Streamlit [Legacy direct calls]
    ↓
Streamlit UI (hybrid mode)
```

## Current State
- FastAPI backend operational
- Database populated for pilot zones
- Streamlit connected to backend for renewable fraction chart
- Ingestion still manual
- Most Streamlit charts still rely on direct ENTSO-E calls

## Next Phase
- Move all Streamlit direct ENTSO-E requests behind FastAPI endpoints
- Schedule ingestion automatically (cron/systemd/Kubernetes CronJob)
- Disable auth bypass in production
