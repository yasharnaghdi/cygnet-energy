# Model Card: Regime Detection & Stress Testing

## Overview
CYGNET Energy uses an unsupervised clustering model to label hourly grid conditions into operating regimes (e.g., Normal, Stressed, RES-Dominant) and a per-regime linear model to estimate price pressure under stress scenarios.

## Intended Use
- Identify short-term operating regimes for European bidding zones.
- Provide interpretable stress-test outputs for scenario analysis.
- Support decision support workflows (not automated trading or dispatch).

## Data Inputs
- Hourly generation data by PSR type from ENTSO-E.
- Derived state variables (per zone per hour):
  - `res_penetration`
  - `net_import`
  - `price_volatility`
  - Optional: `load_tightness`, `interconnect_saturation` (depending on model training).

## Model Components
- **RegimeDetector**: KMeans clustering on state variables.
- **RegimeModelEnsemble**: per-regime Ridge regression for price pressure response.
- **StressTester**: counterfactual perturbations for scenario analysis.

## Key Assumptions
- ENTSO-E data is accurate and complete for the selected period.
- Hourly aggregation captures the dominant regime signals.
- Linear response models are acceptable approximations within the regime.

## Known Limitations
- Regime labels are unsupervised; they require human interpretation.
- Stress tests are sensitivity-based and do not model system constraints end-to-end.
- Results may degrade outside the training period or during structural market changes.

## Evaluation & Monitoring
- Track regime stability, confidence, and per-regime model metrics (R², MAE, RMSE).
- Perform time-split validation (train → validation → test across years).
- Monitor data completeness and schema drift in ENTSO-E XML parsing.

## Ethical & Operational Considerations
- Not intended for real-time market trading without governance.
- Human oversight required for regime labeling and scenario interpretation.

## Contacts
- Maintainers: CYGNET Energy team
