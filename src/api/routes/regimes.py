from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.api.middleware.auth import verify_token
from src.api.middleware.rate_limit import limiter
from src.api.models.schemas import RegimeQuery, RegimeResponse
from src.db.connection import get_connection
from src.models.modules_2_regime_detector import RegimeDetector

router = APIRouter(
    prefix="/regimes",
    tags=["Regimes"],
    dependencies=[Depends(verify_token)],
)

REGIME_MAP = {
    0: "NORMAL",
    1: "HIGH_RES",
    2: "STRESSED",
    3: "IMPORT_HEAVY",
}


@lru_cache
def _get_detector() -> RegimeDetector:
    detector = RegimeDetector()
    model_path = Path(__file__).resolve().parents[2] / "models" / "trained" / "regime_detector.pkl"
    detector.load(str(model_path))
    return detector


@router.get("/current", response_model=RegimeResponse)
@limiter.limit("100/hour")
def get_current_regime(
    request: Request,
    query: RegimeQuery = Depends(),
) -> RegimeResponse:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT time,
                   load_tightness,
                   res_penetration,
                   net_import,
                   interconnect_saturation,
                   price_volatility
            FROM regime_states
            WHERE zone = %s
              AND time >= NOW() - (%s || ' days')::interval
            ORDER BY time DESC
            LIMIT 1
            """,
            (query.zone.value, query.date_range),
        )
        row = cursor.fetchone()
        cursor.close()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No regime state data found",
            )

        timestamp, load_tightness, res_penetration, net_import, _, price_volatility = row
        if (
            load_tightness is None
            or res_penetration is None
            or net_import is None
            or price_volatility is None
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incomplete regime state data",
            )

        detector = _get_detector()
        prediction = detector.predict_regime(
            float(res_penetration),
            float(net_import),
            float(price_volatility),
        )

        regime_name = REGIME_MAP.get(prediction["regime_id"], "NORMAL")

        return RegimeResponse(
            timestamp=timestamp,
            zone=query.zone,
            regime=regime_name,
            confidence=float(prediction["confidence"]),
            res_penetration=float(res_penetration),
            load_tightness=float(load_tightness),
            net_import=float(net_import),
        )
    finally:
        conn.close()
