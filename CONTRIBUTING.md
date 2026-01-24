# Contributing

Thanks for helping improve Cygnet Energy. This guide focuses on the exact commands to get a working dev environment and validate changes.

## Development setup (local)
1. Clone and enter the repo:
   - `git clone https://github.com/yasharnaghdi/cygnet-energy.git`
   - `cd cygnet-energy`
2. Create your branch:
   - `git checkout -b feature/short-description`
3. Create local config files (one-time per machine):
   - `cp .env.example .env`
   - `cp config/config.yaml.example config/config.yaml`
   - Update `.env` with `API_TOKEN` and `DATABASE_URL`
   - Update `config/config.yaml` with DB credentials
4. Install dependencies (only when `pyproject.toml` or `poetry.lock` changes):
   - `poetry install`

## Database setup
Start PostgreSQL using one of the following:
- Local PostgreSQL service, or
- Docker Compose:
  - `docker compose up -d postgres`

Initialize schema and load the baseline dataset:
- `poetry run python scripts/init_db.py`
- `poetry run python scripts/load_csv_to_db.py --csv-path data/samples/time_series_60min_singleindex.csv`

If the sample CSV is missing, download `time_series_60min_singleindex.csv` from Open Power System Data and place it at `data/samples/`.

## Smoke checks and tests
Run the baseline smoke checks (no DB writes in ingestion check):
- `poetry run python scripts/smoke_check.py`

Run the full test suite:
- `poetry run pytest`

## Run the dashboard
- `poetry run streamlit run main_app.py`

## Versioning and releases
- main is always deployable.
- Do not reuse tags. If `v1.0.0` exists, bump to `v1.0.1` or later.
- Release workflow details: `RELEASE_POLICY.md`.
