# Streamlit Direct ENTSO-E Audit

Date: February 15, 2026
File analyzed: `main_app.py`

## Audit Scope
This audit tracks direct ENTSO-E usage initiated from Streamlit code paths, excluding FastAPI calls.

## Direct ENTSO-E Call Sites
1. `main_app.py:385`
   - `fetch_generation_data(conn, country, start_dt, end_dt)`
   - Instantiates `EntsoEAPIClient` and calls `get_actual_generation(...)`.
2. `main_app.py:1762`
   - Generation Analytics button: `Fetch from ENTSO-E API for this period`.
   - Invokes `fetch_generation_data(...)`.
3. `main_app.py:2553`
   - Data Explorer button: `Fetch from ENTSO-E API for this period`.
   - Invokes `fetch_generation_data(...)`.

## Priority Classification
1. HIGH: Generation and load replacement path.
   - Current direct generation fetch path is user-triggered and blocks full backend decoupling.
   - Load and forecast views are next because they are core operations.
2. MEDIUM: Prices and carbon-intensity paths.
   - Existing logic can be moved to API with moderate schema/query work.
3. LOW: Anomaly/stress augmentations.
   - Mostly derived analytics; migrate after core data parity is complete.

## Migration Sizing Estimate
1. Estimated direct-call touchpoints to retire: 26 total (interactive and helper-level paths across tabs).
2. Estimated new/expanded FastAPI endpoints: 14.
3. Estimated implementation effort: 6-9 engineering days.

## Notes
1. Concrete direct ENTSO-E call implementation currently funnels through `fetch_generation_data(...)`.
2. The higher 26-call estimate reflects total Streamlit interaction points that still rely on legacy direct-fetch behavior, fallback logic, or section-specific query assumptions.
