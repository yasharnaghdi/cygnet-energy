# Phase 2 Migration Plan

Date: February 15, 2026

## Objective
Replace Streamlit direct ENTSO-E access with FastAPI-backed queries while preserving dashboard availability.

## Rollout Controls
1. Add feature flag: `USE_API_BACKEND=true|false`.
2. When `true`, Streamlit uses FastAPI endpoints only for migrated sections.
3. When `false`, Streamlit retains legacy direct-fetch fallback.
4. Rollback is immediate by toggling the flag and restarting Streamlit.

## Sprint 1 (Days 1-3): Core Generation + Load
1. Day 1
   - Implement `GET /api/analytics/generation-mix`.
   - Implement `GET /api/analytics/load-actual`.
   - Add API client wrappers in `main_app.py`.
2. Day 2
   - Implement `GET /api/analytics/load-forecast`.
   - Replace Generation Analytics direct data path with API response mapping.
3. Day 3
   - Replace Load Analytics charts/tables with API calls.
   - Add parity checks for hourly totals and missing-interval handling.

## Sprint 2 (Days 4-5): Price + Carbon
1. Day 4
   - Implement price endpoints for hourly and aggregate views.
   - Migrate price visualizations to API-backed data.
2. Day 5
   - Implement carbon-intensity endpoints.
   - Replace carbon-intelligence tab data source and validate parity.

## Sprint 3 (Days 6-9): Stress + Caching + Cleanup
1. Day 6
   - Add stress-score/tight-hours enriched API responses.
   - Migrate alerts/indicator dependencies.
2. Day 7
   - Add caching in FastAPI (in-memory first, Redis optional).
   - Add cache TTL and invalidation for ingestion refresh cadence.
3. Day 8
   - Remove dead direct-fetch code paths gated by `USE_API_BACKEND`.
   - Add regression tests for all migrated tabs.
4. Day 9
   - Final hardening, docs refresh, and release checklist.
   - Set default `USE_API_BACKEND=true`.

## Exit Criteria
1. All Streamlit analytical tabs read from FastAPI.
2. No direct ENTSO-E calls remain in UI execution paths.
3. Feature flag rollback tested and documented.
4. API latency and data freshness are visible in dashboard status.
