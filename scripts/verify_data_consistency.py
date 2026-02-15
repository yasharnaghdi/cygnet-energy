"""Compare direct ENTSO-E fetch against FastAPI-backed renewable fraction."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pandas as pd
import requests

from src.api.client import EntsoEAPIClient
from src.api.parser import EntsoEXMLParser

RENEWABLE_TYPES = {"B01", "B17", "B18", "B19", "B20"}


def compute_direct_renewable_fraction(generation_df: pd.DataFrame) -> pd.DataFrame:
    if generation_df is None or generation_df.empty:
        return pd.DataFrame(columns=["timestamp", "direct_renewable_pct"])

    hourly = (
        generation_df.groupby("time", as_index=False)["actual_generation_mw"]
        .sum()
        .rename(columns={"actual_generation_mw": "total_mw"})
    )
    renewable_hourly = (
        generation_df[generation_df["psr_type"].isin(RENEWABLE_TYPES)]
        .groupby("time", as_index=False)["actual_generation_mw"]
        .sum()
        .rename(columns={"actual_generation_mw": "renewable_mw"})
    )
    merged = hourly.merge(renewable_hourly, on="time", how="left").fillna({"renewable_mw": 0.0})
    merged["direct_renewable_pct"] = (merged["renewable_mw"] / merged["total_mw"].replace(0, pd.NA)) * 100
    merged["timestamp"] = pd.to_datetime(merged["time"], utc=True, errors="coerce")
    return merged[["timestamp", "direct_renewable_pct"]].dropna()


def main() -> None:
    start = datetime(2026, 2, 14, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 2, 15, 0, 0, tzinfo=timezone.utc)

    print("Fetching from ENTSO-E directly...")
    client = EntsoEAPIClient(os.getenv("API_TOKEN"))
    xml = client.get_actual_generation("DE", start, end)
    if not xml:
        raise RuntimeError("Direct ENTSO-E call returned no payload.")

    direct_df = EntsoEXMLParser.parse_generation_xml(xml)
    if direct_df is None or direct_df.empty:
        raise RuntimeError("Could not parse ENTSO-E XML generation payload.")
    print(f"  Raw generation records: {len(direct_df)}")

    direct_pct = compute_direct_renewable_fraction(direct_df)
    print(f"  Hourly renewable points: {len(direct_pct)}")

    print("\nFetching from FastAPI...")
    api_url = "http://127.0.0.1:8001/api/analytics/renewable-fraction"
    params = {"zone": "DE", "start_date": "2026-02-14", "end_date": "2026-02-15"}
    resp = requests.get(api_url, params=params, timeout=20)
    resp.raise_for_status()
    api_rows = resp.json()
    print(f"  API records: {len(api_rows)}")

    api_df = pd.DataFrame(api_rows)
    if api_df.empty:
        raise RuntimeError("FastAPI returned no records for DE.")
    api_df["timestamp"] = pd.to_datetime(api_df["timestamp"], utc=True, errors="coerce")
    api_df["api_renewable_pct"] = pd.to_numeric(api_df["renewable_pct"], errors="coerce")
    api_df = api_df[["timestamp", "api_renewable_pct"]].dropna()

    comparison = api_df.merge(direct_pct, on="timestamp", how="left")

    print("\nSample comparison (first 3 API rows):")
    print(f"{'Time (UTC)':<25} {'FastAPI':<12} {'Direct ENTSO-E':<14}")
    print("-" * 56)
    for _, row in comparison.head(3).iterrows():
        ts = row["timestamp"].strftime("%Y-%m-%dT%H:%M:%SZ")
        api_pct = f"{row['api_renewable_pct']:.2f}%"
        direct_val = row.get("direct_renewable_pct")
        direct_pct_str = "N/A" if pd.isna(direct_val) else f"{float(direct_val):.2f}%"
        print(f"{ts:<25} {api_pct:<12} {direct_pct_str:<14}")

    print("\nBoth sources operational.")


if __name__ == "__main__":
    main()
