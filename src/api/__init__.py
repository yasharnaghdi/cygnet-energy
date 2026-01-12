"""FastAPI application for Cygnet Energy."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from datetime import datetime, timedelta
import psycopg2.extras

from src.db.connection import get_connection

app = FastAPI(
    title="Cygnet Energy API",
    version="0.1.0",
    description="European grid intelligence platform - Real-time electricity data"
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0", "timestamp": datetime.utcnow()}


@app.get("/generation/current")
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

    cur.execute("""
        SELECT DISTINCT ON (psr_type)
               time, psr_type, actual_generation_mw, quality_code
        FROM generation_actual
        WHERE bidding_zone_mrid = %s
        ORDER BY psr_type, time DESC
    """, (bidding_zone,))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail=f"No data for zone {bidding_zone}")

    return [dict(row) for row in rows]


@app.get("/generation/history")
async def get_generation_history(
    bidding_zone: str = "DE",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    hours: int = 24
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

    if start_date and end_date:
        query = """
            SELECT time, psr_type, actual_generation_mw, quality_code
            FROM generation_actual
            WHERE bidding_zone_mrid = %s
              AND time >= %s
              AND time <= %s
            ORDER BY time DESC, psr_type
        """
        params = (bidding_zone, start_date, end_date)
    else:
        query = """
            SELECT time, psr_type, actual_generation_mw, quality_code
            FROM generation_actual
            WHERE bidding_zone_mrid = %s
              AND time >= NOW() - INTERVAL '%s hours'
            ORDER BY time DESC, psr_type
        """
        params = (bidding_zone, hours)

    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail="No data found")

    return [dict(row) for row in rows]


@app.get("/analysis/renewable-fraction")
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

    cur.execute("""
        WITH generation_breakdown AS (
            SELECT
                SUM(CASE WHEN psr_type IN ('B01', 'B18', 'B19', 'B20')
                    THEN actual_generation_mw ELSE 0 END) as renewable_gen,
                SUM(actual_generation_mw) as total_gen
            FROM generation_actual
            WHERE bidding_zone_mrid = %s
              AND time >= NOW() - INTERVAL '%s hours'
              AND quality_code = 'A'
        )
        SELECT
            renewable_gen,
            total_gen,
            ROUND(renewable_gen / NULLIF(total_gen, 0) * 100, 1) as renewable_pct
        FROM generation_breakdown
    """, (bidding_zone, hours))

    result = cur.fetchone()
    cur.close()
    conn.close()

    if not result or result["total_gen"] is None:
        raise HTTPException(status_code=404, detail="No data available")

    return dict(result)


@app.get("/load/current")
async def get_current_load(bidding_zone: str = "DE"):
    """Get latest load consumption."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT time, load_consumption_mw, quality_code
        FROM load_actual
        WHERE bidding_zone_mrid = %s
        ORDER BY time DESC
        LIMIT 1
    """, (bidding_zone,))

    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail=f"No load data for zone {bidding_zone}")

    return dict(row)
