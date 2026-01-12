from datetime import datetime
from pydantic import BaseModel
from typing import Dict, List, Optional


class GenerationReading(BaseModel):
    time: datetime
    bidding_zone_mrid: str
    psr_type: str
    actual_generation_mw: float
    quality_code: str = "A"


class LoadReading(BaseModel):
    time: datetime
    bidding_zone_mrid: str
    load_consumption_mw: float
    quality_code: str = "A"


# ============ STATE VARIABLES ============

class StateVariable(BaseModel):
    """System state gauge at one hour"""
    time: datetime
    zone: str
    load_tightness: float
    res_penetration: float
    net_import: float
    interconnect_saturation: float
    price_volatility: float


class SystemState(BaseModel):
    """Full system state snapshot"""
    time: datetime
    zones: Dict[str, StateVariable]


# ============ REGIMES ============

class RegimePrediction(BaseModel):
    """Predicted operating mode"""
    regime_id: int
    regime_name: str
    confidence: float
    state_vector: List[float]


class RegimeProfile(BaseModel):
    """Centroid of a regime cluster"""
    regime_id: int
    regime_name: str
    res_penetration: float
    net_import: float
    price_volatility: float


# ============ BEHAVIOR MODELS ============

class ModelCoefficients(BaseModel):
    """Fitted coefficients for regime model"""
    regime_id: int
    regime_name: str
    intercept: float
    coefficients: Dict[str, float]
    r2_score: float
    mae: float
    n_samples: int


class ModelPrediction(BaseModel):
    """Output of regime-specific model"""
    regime_id: int
    regime_name: str
    prediction: float
    features_used: List[str]


# ============ STRESS TESTING ============

class StressResult(BaseModel):
    """Single stress test outcome"""
    scenario: str
    regime_id: int
    regime_name: str
    baseline_pred: float
    shocked_pred: float
    delta_pred: float
    pct_change: float
    feature_shocked: Optional[str] = None
    perturbation_size: Optional[float] = None
    narrative: Optional[str] = None


class CombinedStressResult(BaseModel):
    """Multiple simultaneous shocks"""
    scenario: str
    regime_id: int
    regime_name: str
    baseline_pred: float
    shocked_pred: float
    delta_pred: float
    pct_change: float
    perturbations: Dict[str, float]
    individual_effects: Dict[str, Dict[str, float]]


class SensitivityCurve(BaseModel):
    """Sensitivity sweep (feature range -> output)"""
    feature: str
    regime_id: int
    baseline_pred: float
    points: List[Dict[str, float]]


# ============ CROSS-BORDER ============

class CrossBorderState(BaseModel):
    """State variables for country pair"""
    time: datetime
    zone_pair: str
    res_asymmetry: float
    demand_diff: float
    volatility_spread: float


class SpreadPrediction(BaseModel):
    """Price spread prediction under regime"""
    zone_pair: str
    regime_id: int
    regime_name: str
    baseline_spread: float
    shocked_spread: float
    delta_spread: float
    drivers: Dict[str, float]
