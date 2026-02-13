"""
Fetch EIA retail electricity price data and store it in canonical_metrics.

Examples:
    poetry run python scripts/fetch_eia_data.py --states CA TX NY --start 2024-01 --end 2025-12
    poetry run python scripts/fetch_eia_data.py --from-config --start 2024-01 --end 2025-12
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import yaml

# Add repository root to import path when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db.connection import get_connection  # noqa: E402
from src.services.eia_adapter import EIAAdapter  # noqa: E402


CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "config.yaml"
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def _load_config(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _default_months() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    this_month = now.strftime("%Y-%m")
    return this_month, this_month


def _unique(values: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for value in values:
        value = value.strip().upper()
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch EIA retail price series and upsert rows into canonical_metrics."
    )
    parser.add_argument(
        "--states",
        nargs="+",
        help=(
            "US state IDs (e.g., CA TX NY). If omitted, states are discovered from "
            "EIA facet metadata (or config via --from-config)."
        ),
    )
    parser.add_argument(
        "--sectors",
        nargs="+",
        default=None,
        help="EIA sector IDs (e.g., ALL RES COM IND). Default from config or ALL.",
    )
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="Start month in YYYY-MM format.",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="End month in YYYY-MM format.",
    )
    parser.add_argument(
        "--from-config",
        action="store_true",
        help=(
            "Read sectors/default date range from config/config.yaml. If eia.states "
            "is ALL (or empty), discovers canonical states from EIA facet metadata."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=CONFIG_PATH,
        help=f"Path to config file (default: {CONFIG_PATH}).",
    )
    return parser.parse_args()


def _should_discover_all_states(config_states: List[str]) -> bool:
    if not config_states:
        return True
    normalized = {value.strip().upper() for value in config_states if value}
    return "ALL" in normalized or "ALL_STATES" in normalized


def _ingested_state_count() -> int:
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT COUNT(DISTINCT region_id)
            FROM canonical_metrics
            WHERE source = 'EIA'
              AND dataset = 'electricity/retail-sales'
              AND metric_name = 'retail_price'
            """
        )
        return int(cur.fetchone()[0] or 0)
    finally:
        cur.close()
        conn.close()


def main() -> int:
    _load_env_file(ENV_PATH)
    args = parse_args()
    cfg = _load_config(args.config)
    eia_cfg = cfg.get("eia", {})
    adapter = EIAAdapter()

    states: List[str] = []
    if args.states:
        states = _unique(args.states)
    elif args.from_config:
        config_states = _unique(eia_cfg.get("states", []))
        if _should_discover_all_states(config_states):
            states = adapter.fetch_retail_state_ids()
        else:
            states = config_states
    else:
        states = adapter.fetch_retail_state_ids()

    if not states:
        raise SystemExit(
            "No states resolved. Use --states CA TX ... or ensure EIA state facet discovery works."
        )

    if args.sectors:
        sectors = _unique(args.sectors)
    elif args.from_config and eia_cfg.get("sectors"):
        sectors = _unique(eia_cfg.get("sectors", []))
    else:
        sectors = ["ALL"]

    default_start, default_end = _default_months()
    start = args.start or (eia_cfg.get("default_start") if args.from_config else None) or default_start
    end = args.end or (eia_cfg.get("default_end") if args.from_config else None) or default_end

    inserted = adapter.ingest_retail_prices(
        state_ids=states,
        sector_ids=sectors,
        start=start,
        end=end,
    )
    canonical_states = adapter.fetch_retail_state_ids()
    total_states = len(canonical_states)
    ingested_states = _ingested_state_count()
    coverage_pct = (ingested_states / total_states * 100.0) if total_states else 0.0

    print(
        "EIA ingestion completed | "
        f"states={','.join(states)} | sectors={','.join(sectors)} | "
        f"range={start}..{end} | rows_upserted={inserted} | "
        f"coverage={ingested_states}/{total_states} ({coverage_pct:.1f}%)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
