from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from src.services.generation_metrics import build_demo_generation_data, compute_renewable_stats_from_df


def test_build_demo_generation_data_emits_expected_psr_types() -> None:
    start = datetime(2025, 12, 1)
    end = start + timedelta(days=2)

    df = build_demo_generation_data(start, end)

    assert not df.empty
    assert {"time", "psr_type", "actual_generation_mw"} <= set(df.columns)
    assert {"B18", "B19", "B20", "B04", "B14"} <= set(df["psr_type"].unique())


def test_compute_renewable_stats_from_df_splits_renewable_and_fossil() -> None:
    df = pd.DataFrame(
        [
            {"time": datetime(2025, 12, 1, 0), "psr_type": "B18", "actual_generation_mw": 300.0},
            {"time": datetime(2025, 12, 1, 0), "psr_type": "B19", "actual_generation_mw": 500.0},
            {"time": datetime(2025, 12, 1, 0), "psr_type": "B04", "actual_generation_mw": 700.0},
        ]
    )

    stats = compute_renewable_stats_from_df(df)

    assert stats == {
        "total_gen": 1500.0,
        "renewable_gen": 800.0,
        "fossil_gen": 700.0,
    }
