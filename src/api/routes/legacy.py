from __future__ import annotations

from datetime import datetime
from typing import Optional

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException

from src.api.middleware.auth import verify_token
from src.db.connection import get_connection

router = APIRouter(tags=["Legacy"], dependencies=[Depends(verify_token)])


def _table_has_column(conn, table_name: str, column_name: str) -> bool:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND column_name = %s
            LIMIT 1
            """,
            (table_name, column_name),
        )
        return cur.fetchone() is not None
    finally:
        cur.close()


def _fallback_history_from_generation_records(
    conn,
    bidding_zone: str,
    start_date: Optional[str],
    end_date: Optional[str],
    hours: int,
) -> list[dict]:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        if start_date and end_date:
            cur.execute(
                """
                WITH base AS (
                    SELECT
                        timestamp AS time,
                        wind_mw,
                        solar_mw,
                        hydro_mw,
                        GREATEST(
                            total_mw
                            - COALESCE(wind_mw, 0)
                            - COALESCE(solar_mw, 0)
                            - COALESCE(hydro_mw, 0),
                            0
                        ) AS fossil_mw
                    FROM generation_records
                    WHERE zone = %s
                      AND timestamp >= %s
                      AND timestamp <= %s
                )
                SELECT
                    time,
                    psr_type,
                    actual_generation_mw,
                    'A'::text AS quality_code
                FROM (
                    SELECT time, 'B19'::text AS psr_type, wind_mw AS actual_generation_mw FROM base
                    UNION ALL
                    SELECT time, 'B16'::text AS psr_type, solar_mw AS actual_generation_mw FROM base
                    UNION ALL
                    SELECT time, 'B11'::text AS psr_type, hydro_mw AS actual_generation_mw FROM base
                    UNION ALL
                    SELECT time, 'B04'::text AS psr_type, fossil_mw AS actual_generation_mw FROM base
                ) expanded
                WHERE actual_generation_mw IS NOT NULL
                ORDER BY time DESC, psr_type
                """,
                (bidding_zone, start_date, end_date),
            )
        else:
            cur.execute(
                """
                WITH base AS (
                    SELECT
                        timestamp AS time,
                        wind_mw,
                        solar_mw,
                        hydro_mw,
                        GREATEST(
                            total_mw
                            - COALESCE(wind_mw, 0)
                            - COALESCE(solar_mw, 0)
                            - COALESCE(hydro_mw, 0),
                            0
                        ) AS fossil_mw
                    FROM generation_records
                    WHERE zone = %s
                      AND timestamp >= NOW() - (%s * INTERVAL '1 hour')
                )
                SELECT
                    time,
                    psr_type,
                    actual_generation_mw,
                    'A'::text AS quality_code
                FROM (
                    SELECT time, 'B19'::text AS psr_type, wind_mw AS actual_generation_mw FROM base
                    UNION ALL
                    SELECT time, 'B16'::text AS psr_type, solar_mw AS actual_generation_mw FROM base
                    UNION ALL
                    SELECT time, 'B11'::text AS psr_type, hydro_mw AS actual_generation_mw FROM base
                    UNION ALL
                    SELECT time, 'B04'::text AS psr_type, fossil_mw AS actual_generation_mw FROM base
                ) expanded
                WHERE actual_generation_mw IS NOT NULL
                ORDER BY time DESC, psr_type
                """,
                (bidding_zone, hours),
            )
        return cur.fetchall()
    except (psycopg2.errors.UndefinedTable, psycopg2.errors.UndefinedColumn):
        return []
    finally:
        cur.close()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "1.0.1", "timestamp": datetime.utcnow()}


@router.get("/generation/current")
async def get_current_generation(bidding_zone: str = "DE"):
    """
    Get latest generation data for specified zone.

    Args:
        bidding_zone: Country code (default: DE)

    Returns:
        List of current generation by PSR type
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    has_quality_code = _table_has_column(conn, "generation_actual", "quality_code")

    try:
        quality_select = "quality_code" if has_quality_code else "'A'::text AS quality_code"
        cur.execute(
            f"""
            SELECT DISTINCT ON (psr_type)
                   time, psr_type, actual_generation_mw, {quality_select}
            FROM generation_actual
            WHERE bidding_zone_mrid = %s
            ORDER BY psr_type, time DESC
            """,
            (bidding_zone,),
        )
        rows = cur.fetchall()
    except (psycopg2.errors.UndefinedTable, psycopg2.errors.UndefinedColumn) as exc:
        raise HTTPException(status_code=404, detail=f"No data for zone {bidding_zone}") from exc
    finally:
        cur.close()
        conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail=f"No data for zone {bidding_zone}")

    return [dict(row) for row in rows]


@router.get("/generation/history")
async def get_generation_history(
    bidding_zone: str = "DE",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    hours: int = 24,
):
    """
    Get historical generation data.

    Args:
        bidding_zone: Country code (default: DE)
        start_date: ISO format start date (optional)
        end_date: ISO format end date (optional)
        hours: Hours to look back if dates not specified (default: 24)

    Returns:
        Time series of generation data
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    has_quality_code = _table_has_column(conn, "generation_actual", "quality_code")
    rows: list[dict]

    try:
        quality_select = "quality_code" if has_quality_code else "'A'::text AS quality_code"
        if start_date and end_date:
            query = f"""
                SELECT time, psr_type, actual_generation_mw, {quality_select}
                FROM generation_actual
                WHERE bidding_zone_mrid = %s
                  AND time >= %s
                  AND time <= %s
                ORDER BY time DESC, psr_type
            """
            params = (bidding_zone, start_date, end_date)
        else:
            query = f"""
                SELECT time, psr_type, actual_generation_mw, {quality_select}
                FROM generation_actual
                WHERE bidding_zone_mrid = %s
                  AND time >= NOW() - (%s * INTERVAL '1 hour')
                ORDER BY time DESC, psr_type
            """
            params = (bidding_zone, hours)

        cur.execute(query, params)
        rows = cur.fetchall()
        if not rows:
            rows = _fallback_history_from_generation_records(conn, bidding_zone, start_date, end_date, hours)
    except (psycopg2.errors.UndefinedTable, psycopg2.errors.UndefinedColumn) as exc:
        rows = _fallback_history_from_generation_records(conn, bidding_zone, start_date, end_date, hours)
        if not rows:
            raise HTTPException(status_code=404, detail="No data found") from exc
    finally:
        cur.close()
        conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail="No data found")

    return [dict(row) for row in rows]


@router.get("/analysis/renewable-fraction")
async def get_renewable_fraction(bidding_zone: str = "DE", hours: int = 24):
    """
    Calculate renewable energy percentage.

    Args:
        bidding_zone: Country code (default: DE)
        hours: Time window in hours (default: 24)

    Returns:
        Renewable percentage and breakdown
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    has_quality_code = _table_has_column(conn, "generation_actual", "quality_code")

    try:
        quality_filter = "AND quality_code = 'A'" if has_quality_code else ""
        cur.execute(
            f"""
            WITH generation_breakdown AS (
                SELECT
                    SUM(CASE WHEN psr_type IN ('B01', 'B18', 'B19', 'B20')
                        THEN actual_generation_mw ELSE 0 END) as renewable_gen,
                    SUM(actual_generation_mw) as total_gen
                FROM generation_actual
                WHERE bidding_zone_mrid = %s
                  AND time >= NOW() - (%s * INTERVAL '1 hour')
                  {quality_filter}
            )
            SELECT
                renewable_gen,
                total_gen,
                ROUND(renewable_gen / NULLIF(total_gen, 0) * 100, 1) as renewable_pct
            FROM generation_breakdown
            """,
            (bidding_zone, hours),
        )
        result = cur.fetchone()
    except (psycopg2.errors.UndefinedTable, psycopg2.errors.UndefinedColumn) as exc:
        raise HTTPException(status_code=404, detail="No data available") from exc
    finally:
        cur.close()
        conn.close()

    if not result or result["total_gen"] is None:
        raise HTTPException(status_code=404, detail="No data available")

    return dict(result)


@router.get("/load/current")
async def get_current_load(bidding_zone: str = "DE"):
    """Get latest load consumption."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    has_quality_code = _table_has_column(conn, "load_actual", "quality_code")

    try:
        quality_select = "quality_code" if has_quality_code else "'A'::text AS quality_code"
        cur.execute(
            f"""
            SELECT time, load_consumption_mw, {quality_select}
            FROM load_actual
            WHERE bidding_zone_mrid = %s
            ORDER BY time DESC
            LIMIT 1
            """,
            (bidding_zone,),
        )
        row = cur.fetchone()
    except (psycopg2.errors.UndefinedTable, psycopg2.errors.UndefinedColumn) as exc:
        raise HTTPException(status_code=404, detail=f"No load data for zone {bidding_zone}") from exc
    finally:
        cur.close()
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail=f"No load data for zone {bidding_zone}")

    return dict(row)
