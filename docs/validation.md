# Decision & Validation Notes

## Decision Context
This project is a decision-support tool for grid carbon and market stress insights. It is not a dispatch or trading engine.

## What the System Assumes
- ENTSO-E data represents the ground-truth operational picture.
- Hourly aggregation is sufficient for regime classification.
- Price pressure can be approximated with linear models per regime.

## What Fails / Where It Breaks
- Missing or delayed ENTSO-E data can distort regime labels.
- Structural shifts (policy changes, fuel price shocks) may invalidate learned regimes.
- Low-confidence regimes (transition hours) are less reliable and require review.

## Out-of-Scope
- Intraday dispatch optimization.
- Asset-level dispatch or plant-level constraints.
- Real-time trading automation.

## Generalization Boundaries
- Models are expected to generalize within the same market structure and data quality regime.
- Cross-year validity must be verified with time-split evaluation.

## Validation Artifacts
- `scripts/benchmark.py` produces reproducible evaluation summaries.
- Model card: `docs/model_card.md`.
