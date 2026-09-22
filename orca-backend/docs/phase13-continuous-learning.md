# Phase 13 — Continuous Learning: Prediction Ledger, Outcomes & Evaluation

## 1. What this phase adds

A **controlled, closed-loop learning** capability on top of the Phase 12 ML/MLOps
layer. The loop is:

```
LIVE DATA -> FEATURE PIPELINE -> PRODUCTION MODEL -> PREDICTION
  -> AGENT / RISK ENGINE -> DECISION -> OBSERVED OUTCOME
  -> MATCHING -> ROLLING EVALUATION -> DRIFT / PERFORMANCE MONITORING
  -> RETRAINING CANDIDATE -> VALIDATION -> CHAMPION/CHALLENGER
  -> PROMOTION GATE -> PRODUCTION  (with provenance at every step)
```

The loop is deliberately **offline-first and governed**: nothing it produces can
mutate a production model unless it passes an explicit promotion gate, and only
VALIDATED ground truth ever feeds evaluation or training.

## 2. Prediction ledger (`app/ml/ledger.py`)

- `LedgerPrediction` — every production prediction recorded with model + feature
  versions, location, target time, horizon, value, confidence, uncertainty,
  input snapshot, source metadata and a `state` (`recorded | matched | evaluated`).
- `ObservedOutcome` — observed values carry `observation_type`, `quality` (0..1)
  and an explicit validation `status` (`UNVERIFIED | VALIDATED | REJECTED`).
  Ground truth is **never assumed** to be valid.
- `PredictionLedger` — bounded store (`ml_ledger_max_predictions`,
  `ml_outcome_max_entries`); deterministic eviction when over budget.

## 3. Prediction → outcome matching (`PredictionOutcomeMatcher`)

Deterministic, geometry-driven matching of a prediction to its observed outcome:

- **type** — `obs.observation_type` must equal the prediction's target type
  (`pfz`, `wave_height_m`, `productivity`, …); cross-type signals never match;
- **spatial** — `distance_km(pred, outcome) <= ml_match_spatial_km` (default 25 km);
- **temporal** — outcome observed within `ml_match_temporal_window_hours` of the
  prediction's target time (default 3 h, horizon-aware);

`match_all(..., outcomes)` returns all hits best-quality first; only the best is
used for evaluation.

## 4. Rolling evaluation (`app/ml/eval.py`)

- `RollingEvaluator` — MAE / RMSE / bias / coverage / calibration / precision /
  recall / F1 computed over **VALIDATED** matched pairs (classification metrics
  use a 0.5 half-threshold; calibration is Brier-style).
- `MultiWindowEvaluator` — daily / weekly / monthly windows (`ml_eval_*` settings).

## 5. Safety invariant (verified)

- Only **VALIDATED** ground truth enters evaluation or a training dataset.
  `run_matching()` filters to `status == VALIDATED`; unverified / rejected
  observations are never a training signal.  The promotion gate additionally
  requires zero safety regressions (`ml_promotion_require_safety_regression_zero`).

## 6. Files

- `app/ml/ledger.py` (new) — ledger, outcome store, matching.
- `app/ml/eval.py` (new) — rolling + multi-window evaluation.
- `app/ml/governance.py` (new) — `GovernanceEngine` wiring the loop.
- `tests/test_phase13_ml.py` (gitignored) — ledger, outcomes, matching, GT
  validation, evaluation.