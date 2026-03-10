from __future__ import annotations

import math
from datetime import datetime, timedelta

import pandas as pd

RENEWABLE_PSR_TYPES = {"B01", "B17", "B18", "B19", "B20"}


def build_demo_generation_data(start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    if end_dt <= start_dt:
        end_dt = start_dt + timedelta(days=1)
    horizon_days = min(14, max(1, (end_dt - start_dt).days))
    start = end_dt - timedelta(days=horizon_days)
    times = pd.date_range(start=start, end=end_dt, freq="h")
    rows: list[dict[str, object]] = []
    for ts in times:
        hour = ts.hour
        solar = max(0.0, math.sin((hour - 6) / 12 * math.pi)) * 8000
        wind_on = 5000 + 1500 * math.sin(2 * math.pi * hour / 24 + 0.7)
        wind_off = 3500 + 1200 * math.sin(2 * math.pi * hour / 24 + 1.4)
        gas = 10000 + 2000 * math.cos(2 * math.pi * hour / 24)
        nuclear = 8000
        rows.extend(
            [
                {"time": ts.to_pydatetime(), "psr_type": "B18", "actual_generation_mw": solar},
                {"time": ts.to_pydatetime(), "psr_type": "B19", "actual_generation_mw": wind_on},
                {"time": ts.to_pydatetime(), "psr_type": "B20", "actual_generation_mw": wind_off},
                {"time": ts.to_pydatetime(), "psr_type": "B04", "actual_generation_mw": gas},
                {"time": ts.to_pydatetime(), "psr_type": "B14", "actual_generation_mw": nuclear},
            ]
        )
    return pd.DataFrame(rows)


def compute_renewable_stats_from_df(df: pd.DataFrame) -> dict[str, float]:
    total_gen = float(df["actual_generation_mw"].sum())
    renewable_gen = float(
        df[df["psr_type"].isin(RENEWABLE_PSR_TYPES)]["actual_generation_mw"].sum()
    )
    fossil_gen = total_gen - renewable_gen
    return {
        "total_gen": total_gen,
        "renewable_gen": renewable_gen,
        "fossil_gen": fossil_gen,
    }
