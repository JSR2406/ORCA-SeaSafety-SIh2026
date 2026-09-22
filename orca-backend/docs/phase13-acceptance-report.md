# Phase 13 — Acceptance Report: Continuous Learning, Model Governance & ML Provenance

## 1. Scope delivered

A controlled closed-loop learning system with full provenance, on top of the
Phase 12 production ML layer.  It adds:

- **Prediction ledger** — `app/ml/ledger.py`: bounded, versioned prediction +
  observed-outcome store with explicit validation status.
- **Matching** — `PredictionOutcomeMatcher`: deterministic type / spatial /
  temporal matching of predictions to VALIDATED ground truth.
- **Rolling evaluation** — `app/ml/eval.py`: MAE / RMSE / bias / coverage /
  calibration / precision / recall / F1, daily / weekly / monthly.
- **Drift separation** — data drift / prediction drift / performance degradation
  emit **distinct** events (`DATA_DRIFT_DETECTED`, `PREDICTION_DRIFT_DETECTED`,
  `MODEL_PERFORMANCE_DEGRADED`, `MODEL_DRIFT`).
- **Retraining policy** — schedule / GT-volume / performance / data-drift /
  manual triggers; never auto-deploys.
- **Training datasets** — `app/ml/dataset.py`: reproducible `dataset_id` +
  sha256 + feature/time/spatial provenance, filtered to VALIDATED GT.
- **Candidate lifecycle** — `create_candidate` → `validate_candidate`
  (quality / offline / temporal / spatial / calibration / latency / safety) →
  `shadow_evaluate` (champion/challenger) → `promotion_gate` → `rollback_model`.
- **Model governance** — `GovernanceEngine`: promotion history, rollback history,
  model health, full status; candidate versions registered in the real registry.
- **Learning events** — `LearningEventBus` + new `MarineEventType` members.
- **Provenance API** — `GET /api/v1/ml/*` (7 read-only routes).
- **MCP governance tools** — 4 READ_ONLY `analytics_governance` tools (33 total).
- **Frontend contract + explainability** — `build_ml_provenance_contract()` and
  `build_structured_explanation()` (top_features / feature_contributions /
  confidence_factors / data_quality_factors / warnings).
- **Benchmark** — 12 deterministic Phase 13 governance cases + docs.

## 2. Honesty & safety invariants (verified)

- [x] Production models are **immutable until explicitly promoted** — candidate
  creation leaves production untouched.
- [x] **Online learning never modifies a production model directly.**
- [x] **Retraining never automatically equals production deployment** — a gated,
  deliberate promotion is required.
- [x] Only **VALIDATED** ground truth enters evaluation / training; UNVERIFIED and
  REJECTED observations are excluded (`run_matching` filters to VALIDATED).
- [x] ML predictions **never override** the Risk Engine / hard restrictions
  (`ML PREDICTION + LIVE RESTRICTION ACTIVE = RESTRICTED` holds).
- [x] A restricted area is **never relearned as "good"** from historical
  productivity.
- [x] The conversational agent **cannot promote** models — no `train_and_deploy`
  MCP tool; all governance tools are READ_ONLY; no promote HTTP endpoint.
- [x] Missing inputs are surfaced as warnings / `INPUT_DATA_UNAVAILABLE`, never
  fabricated; explainability is derived from model logic so it cannot
  contradict the output.
- [x] Promotion gate rejects on a mandatory failure (accuracy / calibration /
  latency / safety) and logs a `MODEL_VALIDATION_FAILED` event.
- [x] Rollback restores last-known-good and emits `MODEL_ROLLBACK`.

## 3. Verification evidence

- **Phase 13 unit/behavior tests** (`tests/test_phase13_ml.py`): **30 passed** —
  prediction ledger, outcomes + validation states, matching (spatial /
  temporal / type + unverified exclusion), rolling metrics, drift separation,
  datasets (reproducible sha), candidates, validation rejection,
  champion/challenger shadow, promotion gate (pass + mandatory-failure reject),
  rollback, retraining policy (never auto-deploys), provenance lineage,
  frontend contract, structured explanation, MCP tools (present, no
  train/deploy), API contracts (200/404), safety invariant.
- **Full regression**: **406 passed, 2 skipped** across all Phases 1–13.
- **MCP assembly**: `build_mcp_component()` registers **33 tools** (29 prior + 4
  governance).
- **ML provenance API**: all 7 `/api/v1/ml` routes verified via TestClient
  (200 for present, 404 for missing).
- **Benchmark**: 12 Phase 13 governance cases all succeed (ledger, GT matching,
  unverified exclusion, drift separation, reproducible dataset,
  champion/challenger, promotion gate, pinned production, rollback, confidence
  degradation on missing input, stale-features surfaced in health, provenance).

### Event types added

`MODEL_DRIFT`, `MODEL_PERFORMANCE_DEGRADED`, `GROUND_TRUTH_AVAILABLE`,
`RETRAINING_REQUIRED`, `MODEL_CANDIDATE_CREATED`, `MODEL_VALIDATION_FAILED`,
`MODEL_PROMOTED`, `MODEL_ROLLBACK`, `DATA_DRIFT_DETECTED`,
`PREDICTION_DRIFT_DETECTED`.

### Production models observed after gate

`seed_registry` → `1.0.0` for pfz / risk / productivity / forecast; candidate
`1.1.0` registered; promotion moves `pfz` to `1.1.0`; rollback restores `1.0.0`.

## 4. Files added/changed

**New**: `app/ml/{ledger,eval,dataset,governance,governance_events}.py`,
`app/routers/ml.py`, `app/mcp/tools_ml_governance.py`,
`tests/test_phase13_ml.py`, `docs/phase13-{continuous-learning,model-governance,
ml-provenance,acceptance-report}.md`.

**Changed**: `app/ml/__init__.py` (exports), `app/ml/governance.py`
(`seed_registry` made instance-consistent), `app/events/model.py`
(`MarineEventType`), `app/mcp/register.py` (governance tools → 33 total),
`app/main.py` (ml router + governance loop in lifespan), `app/config.py`
(Phase 13 settings block), `evaluation/benchmark.py` (Phase 13 cases + report).

## 5. Notes & follow-ups

- Ledger / evaluation / event bus are in-memory and bounded; a future DB-backed
  sink can be added behind the same seams without changing the loop.
- Candidate "training" is deterministic (rule-based model lineage); a future
  phase can attach learned estimators to the same candidate → validation →
  promotion pipeline.
- `seed_registry()` defaults to the engine's own registry so custom registries
  (tests, evaluation) behave identically to the app's global registry.
- Next: full Phase 13 regression (pytest + eval harness + benchmark), regenerate
  reports, then commit/push as `Phase 13: ...`.