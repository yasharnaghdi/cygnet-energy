# Streamlit -> FastAPI Backend Migration Plan

## Current Streamlit Direct ENTSO-E Dependency

Primary direct-fetch execution path in `main_app.py`:
- `fetch_generation_data(...)` creates `EntsoEAPIClient` and calls `get_actual_generation(...)`.
- Triggered from:
  - Generation Analytics fetch button
  - Data Explorer fetch button

Broader migration scope (all tabs and helper paths):
- Estimated direct-call touchpoints: 26
- Estimated new endpoints required: 14
- Estimated implementation effort: 6-9 days

## Migration Strategy

### Phase 1 (Done): Proof of Concept
- Added API-backed renewable fraction chart.
- Added backend status indicator in Streamlit sidebar.
- Kept legacy direct calls available for fallback behavior.

### Phase 2 (Next 2-3 days): Core Analytics
- Replace Generation Analytics direct-fetch dependencies.
- Add/expand FastAPI endpoints:
  - `GET /api/analytics/generation-mix`
  - `GET /api/analytics/load-actual`
  - `GET /api/analytics/load-forecast`
- Keep legacy fallback behind feature flag.

### Phase 3 (Week 2): Full Migration
- Replace remaining direct fetches in carbon, price, and indicator views.
- Remove ENTSO-E client dependency from Streamlit runtime path.
- Add API caching (in-memory first, Redis optional).

### Phase 4 (Week 3): Deprecation and Hardening
- Remove legacy direct ENTSO-E code paths from Streamlit.
- Streamlit becomes a pure visualization/UI client.
- Lock down production auth and disable dev bypass.

## Rollback Strategy
- Feature flag: `USE_API_BACKEND=true|false`
- If endpoint parity issue occurs:
  1. Set `USE_API_BACKEND=false`
  2. Restart Streamlit
  3. Continue with legacy behavior while fixing API parity
