"""
Report storage abstraction.
Local: saves to PostgreSQL (current).
Cloud: saves JSON to S3 (when AWS_S3_BUCKET is set).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

S3_BUCKET = os.getenv("AWS_S3_BUCKET")
S3_PREFIX = os.getenv("AWS_S3_PREFIX", "reports")


def save_report_to_s3(report_id: str, report_data: dict[str, Any]) -> str | None:
    """
    Save report JSON to S3. Returns S3 URL or None if not configured.
    Called automatically after DB save when AWS_S3_BUCKET is set.
    """
    if not S3_BUCKET:
        return None

    try:
        import boto3

        s3 = boto3.client("s3")
        key = f"{S3_PREFIX}/{datetime.now(timezone.utc):%Y/%m/%d}/{report_id}.json"
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=json.dumps(report_data, indent=2, default=str),
            ContentType="application/json",
        )
        url = f"s3://{S3_BUCKET}/{key}"
        logger.info("Report saved to S3: %s", url)
        return url
    except Exception as exc:  # pragma: no cover - defensive optional integration
        logger.warning("S3 save failed (non-blocking): %s", exc)
        return None


def get_report_from_s3(report_id: str, date_prefix: str) -> dict[str, Any] | None:
    """Retrieve report JSON from S3 by report_id."""
    if not S3_BUCKET:
        return None

    try:
        import boto3

        s3 = boto3.client("s3")
        key = f"{S3_PREFIX}/{date_prefix}/{report_id}.json"
        obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
        return json.loads(obj["Body"].read())
    except Exception:  # pragma: no cover - best-effort retrieval helper
        return None
