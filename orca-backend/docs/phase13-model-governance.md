# Phase 13 — Model Governance: Candidates, Validation, Shadow & Promotion

## 1. Why governance matters

Automated retraining is risky: an online update that quietly reshapes a live
model can turn a previously safe decision unsafe.  FloatChat therefore makes the
entire retrain → promote lifecycle **explicit, human-auditable and gate-guarded**.

Immutable rules (see §5):

- Production models are **immutable until explicitly promoted**.
- **Online learning never modifies a production model directly.**
- **Retraining never automatically equals production deployment.**
- The conversational agent **cannot silently promote** a model (no
  `train_and_deploy` MCP tool exists; all governance tools are READ_ONLY).

## 2. Retraining policy (`RetrainingPolicyEngine`)

Deterministic triggers for a `RETRAINING_REQUIRED` event (never auto-deploys):

- **schedule** — `ml_retrain_schedule_days` since last retrain;
- **ground-truth volume** — ≥ `ml_retrain_min_ground_truth` VALIDATED pairs;
- **performance** — current MAE vs baseline ratio ≥
  `ml_retrain_performance_degrade_mae_ratio` (default 1.25×);
- **data drift** — PSI above `ml_drift_threshold`;
- **manual** — explicit request.

## 3. Candidate lifecycle (`GovernanceEngine`)

1. **Dataset** — `DatasetBuilder` builds a reproducible
   `TrainingDataset` (`dataset_id`, sha256, feature_version, time/spatial range,
   row count, quality stats) from VALIDATED ground truth (`DatasetBuilder` filters
   to `quality >= 0.5`).
2. **Candidate** — `create_candidate()` registers a new registry version
   (`1.1.0`, …) as a candidate with training period, dataset_id and config
   signature; emits `MODEL_CANDIDATE_CREATED`.  It starts `TRAINING` and is
   **never** the production model.
3. **Validation** — `validate_candidate()` requires ALL of: data quality OK,
   offline `valid` + accuracy, temporal `valid`, spatial `valid`,
   calibration ≥ `ml_promotion_min_calibration`, latency ≤
   `ml_promotion_max_latency_ms`, and **zero safety regressions**
   (`ml_promotion_require_safety_regression_zero`).  Missing any → `REJECTED` +
   `MODEL_VALIDATION_FAILED`.
4. **Shadow / champion-challenger** — `shadow_evaluate()` records a challenger's
   predictions alongside the champion's *without* affecting decisions; only the
   champion (production) drives outcomes.
5. **Promotion gate** — `promotion_gate()` checks accuracy / calibration /
   latency / safety against thresholds.  On `PASSED` the candidate's own version
   is promoted in the **real registry**, a `MODEL_PROMOTED` event is emitted, and
   the promotion is appended to `promotion_history`.  On any mandatory-failure → `REJECTED`.
6. **Rollback** — `rollback_model()` restores the last-known-good version and
   emits `MODEL_ROLLBACK`; recorded in `rollback_history`.

## 4. Drift & performance separation

`GovernanceEngine` distinguishes three signals (each emits a **distinct** event):

- **data drift** → `DATA_DRIFT_DETECTED`;
- **prediction drift** → `PREDICTION_DRIFT_DETECTED`;
- **performance degradation** → `MODEL_PERFORMANCE_DEGRADED`.

`ModelHealth` surfaces `status` / `drift` / `performance` for an operational
dashboard.

## 5. Decision precedence (immutable)

```
LIVE HARD CONSTRAINT > RISK ENGINE > VERIFIER > ML PREDICTION > RAG > LLM SYNTHESIS
```

A restricted area is never relearned as "good" from historical productivity —
ground truth for training is restricted to VALIDATED observations and the ML
prediction result `ML PREDICTION (94%) + LIVE RESTRICTION ACTIVE = RESTRICTED`
holds regardless of any learning activity.

## 6. Files

- `app/ml/governance.py` (new) — `GovernanceEngine`, `RetrainingPolicyEngine`,
  promotion / rollback gates, model health.
- `app/ml/dataset.py` (new) — reproducible training dataset builder.
- `app/ml/governance_events.py` (new) — `LearningEventBus` emitting lifecycle
  events.
- `app/ml/registry.py` (extended Phase 12) — candidate/production lifecycle.
- `tests/test_phase13_ml.py` (gitignored) — candidates, validation,
  champion/challenger, shadow, promotion gate, rollback, drift.