from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.services.generation_metrics import compute_renewable_stats_from_df

FIXTURE_PATH = Path(__file__).resolve().parents[2] / "frontend" / "tests" / "fixtures" / "generation_window.json"


def test_generation_equivalence_fixture_matches_frontend_summary() -> None:
    rows = json.loads(FIXTURE_PATH.read_text())
    df = pd.DataFrame(rows)
    df["actual_generation_mw"] = df["actual_generation_mw"].astype(float)

    stats = compute_renewable_stats_from_df(df)
    renewable_pct = round(stats["renewable_gen"] / stats["total_gen"] * 100, 1)

    assert stats["total_gen"] == 3150.0
    assert stats["renewable_gen"] == 2400.0
    assert stats["fossil_gen"] == 750.0
    assert renewable_pct == 76.2
