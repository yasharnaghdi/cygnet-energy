# Changelog

All notable changes to the Cygnet Energy baseline are documented here.

## v1.1.0 - 2026-02-08
- Added production-focused documentation set under `docs/` (`QUICKSTART`, `DEPLOYMENT_SECURE`, `SECURITY`) and a docs index.
- Added secure deployment artifacts with nginx + oauth2-proxy routing and hardened environment template defaults.
- Added OIDC/JWT API security controls, subject-aware rate limiting, and health/readiness probes.
- Restructured setup documentation by replacing `SETUP_GUIDE.md` with focused docs pages.

## v1.0.1 - 2026-01-24
- Removed legacy `app.py` from the root and refreshed the README for the current baseline.
- Aligned baseline config defaults and updated smoke checks to target `main_app.py`.
- Bumped baseline metadata to v1.0.1.
- Removed unused stub modules (`src/collector`, `tests/unit`, `tests/integration`).

## v1.0.0 - 2026-01-24
- Established the reproducible baseline release contract and version metadata.
- Documented reproducibility assumptions and execution order.
- Added minimal smoke checks and separated experimental prototypes.
