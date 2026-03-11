# Recent Developments - 2026-03-11

This document summarizes the changes currently carried by the `feat/frontend-llm-selection-docs` branch relative to `feature/llm-backend-toggle-docker-setup`.

## Summary

The branch introduces a new React frontend, aligns backend report-generation behavior with that frontend, and adds pull-request CI coverage so the combined stack can be validated before merge.

## Frontend Delivery

- Added a Vite + React + TypeScript application under `frontend/`.
- Introduced app shell, sidebar, top bar, and route structure for:
  - Generation
  - Ingestion
  - AI Insights
- Added a shared Zustand session store so zone, date range, persona, and scenario selections stay consistent across pages.
- Added frontend API clients and hooks for generation, ingestion, and report workflows.
- Added chart and report presentation components, including generation trend charts, renewable share gauge, report history drawer, and persona selector.
- Added environment-specific frontend config, Dockerfile, and local developer guide.

## AI Insights And Reporting

- Added UI controls for explicit LLM backend and model selection.
- Wired frontend requests to pass backend/model overrides into the backend reports API.
- Hardened report fallback behavior in `src/services/llm_client.py` and `src/api/routes/reports.py` so report generation remains usable when a preferred provider is unavailable.
- Added tests covering backend override propagation, model override propagation, and fallback execution paths.

## Backend Compatibility Work

- Added `src/services/generation_metrics.py` and related tests to provide generation summary calculations consumed by the new frontend.
- Updated legacy API route behavior to support the new dashboard flow while preserving compatibility with existing data access patterns.
- Adjusted FastAPI app wiring and report generation defaults to support the new UI and backend-selection workflow.

## Developer Workflow And Operations

- Added `frontend/package.json`, Vite config, Vitest setup, MSW handlers, and the initial frontend test suite.
- Added `Cygnet Full Stack CI` in `.github/workflows/cygnet-full.yml` with:
  - backend Python tests
  - frontend production build
  - frontend test run
- Updated Docker and startup assets so the frontend can be built and served as part of local stack work.
- Added `coverage/` to `frontend/.gitignore` to keep generated frontend test artifacts out of commits.

## Validation Used On This Branch

The current branch has been validated with:

```bash
poetry run pytest -v tests
cd frontend && npm run build
cd frontend && npm run test:run
```

## Files Of Interest

- `frontend/README.md`
- `.github/workflows/cygnet-full.yml`
- `src/api/routes/reports.py`
- `src/services/llm_client.py`
- `src/services/generation_metrics.py`
- `tests/api/test_reports.py`
- `frontend/tests/GenerationPage.test.tsx`
