# Cygnet Energy Iteration Retrospective and Stabilization Report

Date: 2026-02-20
Branch: `feature/llm-backend-toggle-docker-setup`
Baseline reference: `main` at `ed02861` (2026-02-08)

## 1) Scope of this report
This document captures:
- The full sequence of implementation iterations (Docker setup, local mode, report history, context-aware reports, bug-fix loops).
- Why failures occurred, not just what failed.
- Gaps that were not addressed before implementation started.
- A concrete recovery and next-steps plan to move from unstable iteration to a production-ready workflow.

## 2) High-level outcome
The project moved from a stable but narrower baseline (`v1.1.0 secure infrastructure`) into a fast iteration cycle with broad feature expansion:
- Added LLM backend selection (OpenAI/Ollama/HuggingFace/fallback).
- Added report history persistence and APIs.
- Added context-aware report generation from multi-tab Streamlit state.
- Added ingest-on-demand endpoint and Streamlit integration.
- Added one-command startup scripts for Docker and local mode.

Most regressions were caused by **coordination and contract gaps**, not isolated code mistakes.

## 3) Iteration timeline with root-cause analysis

### Iteration A: Full Docker recovery and startup unification
Objective:
- Recover from Docker credential failures and make stack startup deterministic.

Key changes:
- Added `Makefile` targets (`start`, `stop`, `status`, `logs`, `migrate`).
- Added `scripts/start_docker.sh` and `scripts/stop_docker.sh`.
- Standardized Docker env template via `.env.docker.example`.
- Updated `docker-compose.yml` to modernize image usage and health checks.

Observed failures:
- Docker auth error: `docker-credential-desktop: executable file not found`.
- Container startup cascaded into DB/API not ready.

Why it failed:
- Local Docker client config depended on Desktop credential helper not present in execution environment.
- Recovery steps were initially manual and brittle.

What was missing beforehand:
- A preflight script validating Docker config, daemon status, and env completeness.
- A documented fallback for credential helper issues.

---

### Iteration B: Rollback + minimal local mode
Objective:
- Avoid heavy multi-GB Docker builds by running only Postgres in Docker and API/Streamlit locally.

Key changes:
- Added `docker-compose.minimal.yml` for Postgres-only container.
- Added `start_local.sh` / `stop_local.sh` convenience scripts.
- Added `README_LOCAL.md` runbook.

Observed failures:
- Multiple parallel run modes caused confusion (`make start` vs `./start_local.sh` vs ad-hoc commands).
- Port collisions between stale local processes and container-proxied ports.

Why it failed:
- Both full Docker and hybrid local workflows existed without strict mode boundaries.
- No startup gate to detect and kill stale listeners before boot.

What was missing beforehand:
- A single supported “golden path” and explicit mode selection contract.
- Startup ownership of ports (`8001`, `8501`, `5433`) with collision detection.

---

### Iteration C: Phase B report history implementation
Objective:
- Persist generated reports with metadata, then expose list/detail/update/delete history APIs.

Key changes:
- Migration added `report_sessions` and `report_history`.
- ORM models added in `src/db/models.py`.
- History endpoints added in `src/api/routes/reports.py`.

Observed failures:
- `404` on `/api/reports/history` even though route existed in code.

Why it failed:
- Host port `8001` was served by an outdated local API process without the new route.
- New process and old process competed, producing inconsistent behavior.

What was missing beforehand:
- Start script should have asserted process identity (binary + args + PID file integrity).
- Health check should have included contract checks on required endpoints.

---

### Iteration D: Context-aware report generation (multi-tab session context)
Objective:
- Include scenario context from all Streamlit tabs in report generation and save it with each report.

Key changes:
- Global analysis context tracked in Streamlit session state.
- `session_context` accepted by reports API and merged into data summary/prompting.
- Prompt templates updated for cross-tab context references.

Observed failures:
- Navigation/tab jumps and page state instability after widget changes.

Why it failed:
- Streamlit rerun model was not fully accounted for.
- Mutable session keys were updated in ways that interfered with active navigation widget state.

What was missing beforehand:
- A dedicated state model design for Streamlit rerun behavior.
- Guardrails against writing widget-backed keys after widget instantiation.

---

### Iteration E: Generation Analytics SQL/schema regressions
Objective:
- Remove invalid `quality_code` assumptions and restore generation analytics reliability.

Observed failures:
- `quality_code` column missing in one table.
- `InFailedSqlTransaction` after query errors.
- Data not appearing despite fetch attempts.

Why it failed:
- Schema assumptions differed across environments/tables (`generation_actual` vs `generation_records`).
- Query failures left transaction state aborted when rollback/autocommit handling was incomplete.

Fixes applied:
- Added schema-adaptive inserts/queries (check columns and table availability).
- Added rollback protection and autocommit connection behavior in Streamlit DB access path.
- Added ingest API call path from Streamlit for deterministic fetch-on-demand.

What was missing beforehand:
- Explicit schema compatibility matrix and runtime table detection strategy.
- Integration tests against both legacy and current schema variants.

---

### Iteration F: Regimes tab runtime failure
Objective:
- Keep Regimes page usable when `regime_states` table is absent.

Observed failures:
- `relation "regime_states" does not exist` hard crash.

Why it failed:
- Feature assumed model output table exists in all deployments.

Fix applied:
- Added existence check and graceful fallback UX with guidance/demo snapshot.

What was missing beforehand:
- Optional feature gating based on table/model availability.

## 4) Cross-cutting failure themes (retrospective)

1. Environment contract drift
- Full Docker mode and hybrid local mode were both active without strict boundaries.
- Result: endpoint/version mismatches and repeated process collisions.

2. Schema contract drift
- Code alternated between legacy and newer table shapes without centralized schema adapter.
- Result: column/table not found errors.

3. Insufficient startup validation
- Health checks validated liveness but not capability (route existence, migration level, active process identity).
- Result: system appeared “up” but critical features still failed.

4. Streamlit state architecture not hardened for reruns
- Session keys coupled to widgets were mutated improperly.
- Result: navigation resets and `StreamlitAPIException`.

5. Feature implementation outran regression test coverage
- New history/context/ingest paths were added faster than end-to-end tests and smoke tests.

## 5) What is currently implemented (as of this branch state)

Runtime and startup:
- One-command Docker workflow via `make start` (`scripts/start_docker.sh`).
- Hybrid local workflow via `./start_local.sh` and `./stop_local.sh`.
- Startup checks for service health and history endpoint reachability.

API and data:
- Report history migration and ORM (`report_sessions`, `report_history`).
- History CRUD endpoints in `src/api/routes/reports.py`.
- Ingest endpoint `POST /api/ingest/generation` in `src/api/routes/ingest.py`.
- API router registration in `src/api/main.py` and `src/api/routes/__init__.py`.

Streamlit app:
- Context buffer/session overlay for report context.
- Generation analytics schema-adaptive reads (`generation_actual`/`generation_records`).
- On-demand fetch via API ingest endpoint.
- Regimes tab graceful fallback when table is missing.

LLM:
- Runtime backend selection and forced backend/model execution support.

## 6) Gaps still open or partially mitigated

1. No single canonical run mode for all contributors
- Both Docker-full and hybrid-local are supported, but team process may still diverge.

2. Limited end-to-end smoke automation
- No single CI/local smoke command proving: startup -> ingest -> analytics page query -> report generate -> history read.

3. Optional module readiness policy not formalized
- Regimes and other advanced modules still rely on implicit prerequisites.

4. Documentation fragmentation
- Setup knowledge currently split across README, README_LOCAL, scripts, and ad-hoc troubleshooting.

## 7) Recommended next steps (execution plan)

### P0 (must do now)
1. Establish one canonical default run mode
- Recommendation: Docker-first (`make start`) as official baseline.
- Keep hybrid local mode as secondary, explicitly labeled for power users.
- Acceptance: all bug reports must specify mode and env file (`.env.docker` or `.env`).

2. Add startup contract checks
- Add checks for required routes (`/healthz`, `/readyz`, `/api/reports/history`, `/api/ingest/generation`) and migration head state.
- Acceptance: startup fails fast with actionable error if any contract check fails.

3. Add schema capability check command
- Script to print table/column capabilities used by analytics pages.
- Acceptance: one command clearly shows compatibility before app launch.

### P1 (next sprint)
1. Build end-to-end smoke test script
- Scenario: boot -> ingest 24h -> verify generation rows -> generate report -> verify history record.
- Acceptance: single command returns pass/fail and diagnostic output.

2. Stabilize Streamlit state model
- Formalize session keys and ownership (widget-bound vs app-owned keys).
- Acceptance: no tab jumps; no widget-state mutation exceptions under repeated interactions.

3. Add feature readiness badges in UI
- For optional modules (Regimes, advanced models), surface readiness state and exact missing prerequisites.

### P2 (hardening)
1. CI matrix for run modes
- Minimal tests for Docker mode and hybrid local mode.

2. Consolidated operator handbook
- Merge scattered operational docs into a single “Runbook + Incident Triage”.

## 8) Proposed stable operating workflow

For default product run:
1. `cp .env.docker.example .env.docker`
2. Fill tokens (`ENTSOE_API_TOKEN`, optional `OPENAI_API_KEY`)
3. `make start`
4. Validate:
   - `curl http://127.0.0.1:8001/healthz`
   - `curl http://127.0.0.1:8001/readyz`
   - `curl http://127.0.0.1:8001/api/reports/history?limit=1`
5. Open `http://127.0.0.1:8501`

For hybrid local development:
1. `cp .env.example .env`
2. `./start_local.sh`
3. Open app/API URLs printed by script.

## 9) Governance recommendation
To prevent another unstable iteration loop:
- Require a short RFC before cross-cutting changes that touch runtime mode, schema contract, or navigation state.
- Require “definition of done” to include startup command, migration plan, fallback behavior, and smoke verification commands.
- Require commit discipline by milestone (Phase A/B/C) to avoid long-lived uncommitted divergence from `main`.

## 10) Final summary
The failures were primarily systemic (mode drift, schema drift, missing startup contracts), not single-point defects. The branch now includes substantial fixes, but long-term stability depends on enforcing run-mode standards, schema capability checks, and smoke-test gates before additional feature expansion.
