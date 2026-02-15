# Documentation Index

Current phase status: **Phase 1 complete** ✅

## Phase Documentation
1. `docs/PHASE1_SUCCESS_REPORT.md`:
   - Phase 1 delivery summary.
   - Evidence of API-backed Streamlit chart behavior.
   - Current limitations and completion criteria.
2. `docs/STREAMLIT_ENTSO_AUDIT.md`:
   - Direct ENTSO-E call audit in `main_app.py`.
   - Priority classification and migration sizing estimate.
3. `docs/PHASE2_MIGRATION_PLAN.md`:
   - Day-by-day backend migration plan.
   - Rollback strategy via `USE_API_BACKEND` feature flag.

## Existing Docs
1. `docs/QUICKSTART.md`: local development prerequisites, startup commands, smoke checks, and healthy output expectations.
2. `docs/DEPLOYMENT_SECURE.md`: hardened deployment using `docker-compose.secure.yml`, required environment variables, and troubleshooting.
3. `docs/SECURITY.md`: authentication model, secret-handling rules, rotation guidance, and rate-limit/security-header notes.
4. `docs/INGESTION_ANALYSIS.md`: ingestion design and operational notes.

## Developer Quick Start
1. Start FastAPI on `127.0.0.1:8001` (recommended in this repo state).
2. Start Streamlit on `localhost:8501`.
3. Set API target:
   - `CYGNET_API_URL=http://127.0.0.1:8001`
4. For local development auth bypass:
   - `AUTH_BYPASS_DEV=true`
5. Basic health checks:
   - `curl http://127.0.0.1:8001/healthz`
   - `curl -I http://localhost:8501`
