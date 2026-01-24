#!/usr/bin/env python
"""Baseline smoke checks for ingestion, model execution, and app boot."""

import argparse
import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.load_csv_to_db import load_csv_to_db
from src.services.carbon_service import CarbonIntensityService


def check_ingestion(csv_path: Path, zone: str) -> dict:
    stats = load_csv_to_db(str(csv_path), bidding_zone=zone, dry_run=True)
    if not stats.get("generation_cols"):
        raise RuntimeError("No generation columns detected during ingestion check")
    return stats


def check_model() -> None:
    service = CarbonIntensityService(db_connection=None)
    result = service.calculate_charging_impact(num_evs=1, daily_charging_mwh=1.0)
    required_keys = {"scenario_peak", "scenario_green", "monthly_savings", "annual_savings"}
    if not required_keys.issubset(result.keys()):
        raise RuntimeError("Model execution check returned incomplete results")

    intensity = service._calculate_intensity({"B04": 100, "B19": 100}, 200)
    if intensity <= 0:
        raise RuntimeError("Model intensity check returned non-positive value")


def check_app(app_paths: list[Path]) -> None:
    for path in app_paths:
        if path.exists():
            py_compile.compile(str(path), doraise=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run baseline smoke checks")
    parser.add_argument(
        "--csv-path",
        default=str(ROOT / "data" / "samples" / "time_series_60min_singleindex.csv"),
        help="Path to sample CSV",
    )
    parser.add_argument("--zone", default="DE", help="Bidding zone code")
    parser.add_argument("--skip-ingestion", action="store_true", help="Skip CSV ingestion check")
    parser.add_argument("--skip-model", action="store_true", help="Skip model execution check")
    parser.add_argument("--skip-app", action="store_true", help="Skip app boot check")

    args = parser.parse_args()

    if not args.skip_ingestion:
        csv_path = Path(args.csv_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV not found: {csv_path}")
        stats = check_ingestion(csv_path, args.zone)
        print(f"Ingestion check OK: {len(stats['generation_cols'])} generation columns")

    if not args.skip_model:
        check_model()
        print("Model execution check OK")

    if not args.skip_app:
        app_paths = [ROOT / "main_app.py"]
        check_app(app_paths)
        print("App boot check OK (py_compile)")

    print("\nAll smoke checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
