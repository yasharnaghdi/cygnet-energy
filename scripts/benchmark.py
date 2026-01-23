"""
Benchmark and validation report generator.

Outputs JSON + Markdown summaries of data coverage and model metrics.
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
import subprocess
from typing import Any, Dict

import psycopg2

from src.models.modules_3_regime_models import RegimeModelEnsemble


@dataclass
class ReportMetadata:
    generated_at: str
    git_commit: str


def get_git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except subprocess.SubprocessError:
        return "unknown"


def load_regime_metrics(model_dir: Path) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {}
    ensemble = RegimeModelEnsemble()
    if not model_dir.exists():
        return metrics

    ensemble.load(str(model_dir))
    for regime_id, model in ensemble.models.items():
        metrics[f"regime_{regime_id}"] = model.metrics

    return {
        "feature_names": ensemble.feature_names,
        "target_name": ensemble.target_name,
        "regime_metrics": metrics,
    }


def get_db_coverage(database_url: str) -> Dict[str, Any]:
    coverage: Dict[str, Any] = {}
    conn = psycopg2.connect(database_url)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            bidding_zone_mrid,
            COUNT(*) AS rows,
            MIN(time) AS min_time,
            MAX(time) AS max_time
        FROM generation_actual
        GROUP BY bidding_zone_mrid
        ORDER BY bidding_zone_mrid
        """
    )
    rows = cur.fetchall()

    for zone, count, min_time, max_time in rows:
        coverage[zone] = {
            "rows": int(count),
            "min_time": min_time.isoformat() if min_time else None,
            "max_time": max_time.isoformat() if max_time else None,
        }

    cur.close()
    conn.close()

    return coverage


def write_report(output_dir: Path, report: Dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "benchmark_report.json"
    md_path = output_dir / "benchmark_report.md"

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Benchmark Report",
        "",
        f"Generated at: {report['metadata']['generated_at']}",
        f"Git commit: {report['metadata']['git_commit']}",
        "",
        "## Data Coverage",
    ]

    coverage = report.get("data_coverage", {})
    if not coverage:
        lines.append("No database coverage available.")
    else:
        for zone, stats in coverage.items():
            lines.append(
                f"- {zone}: {stats['rows']} rows ({stats['min_time']} → {stats['max_time']})"
            )

    lines.append("")
    lines.append("## Regime Model Metrics")
    model_metrics = report.get("regime_model_metrics", {})
    if not model_metrics:
        lines.append("No regime model metrics available.")
    else:
        lines.append(f"Features: {model_metrics.get('feature_names')}")
        for regime, stats in model_metrics.get("regime_metrics", {}).items():
            lines.append(f"- {regime}: {stats}")

    md_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate validation benchmark report")
    parser.add_argument(
        "--output-dir",
        default="reports",
        help="Directory to write benchmark artifacts",
    )
    parser.add_argument(
        "--model-dir",
        default="src/models/trained/regime_models",
        help="Directory containing trained regime models",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", ""),
        help="Database URL for coverage checks",
    )
    args = parser.parse_args()

    metadata = ReportMetadata(
        generated_at=datetime.utcnow().isoformat(),
        git_commit=get_git_commit(),
    )

    report: Dict[str, Any] = {
        "metadata": asdict(metadata),
        "data_coverage": {},
        "regime_model_metrics": {},
    }

    if args.database_url:
        try:
            report["data_coverage"] = get_db_coverage(args.database_url)
        except Exception:
            report["data_coverage"] = {}
    else:
        report["data_coverage"] = {}

    report["regime_model_metrics"] = load_regime_metrics(Path(args.model_dir))

    write_report(Path(args.output_dir), report)


if __name__ == "__main__":
    main()
