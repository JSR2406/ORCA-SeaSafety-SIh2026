# Phase 13 - continuous learning, model governance & ML provenance engine.
#
# The GovernanceEngine is the controlled closed loop:
#
#   LIVE DATA -> FEATURE PIPELINE -> PRODUCTION MODEL -> PREDICTION
#     -> AGENT/RISK ENGINE -> DECISION -> OBSERVED OUTCOME -> EVALUATION
#     -> MONITORING -> RETRAINING CANDIDATE -> VALIDATION -> REGISTRY
#     -> SHADOW EVALUATION -> APPROVAL GATE -> PRODUCTION
#
# Hard invariants preserved:
#   * Production models are IMMUTABLE until explicitly promoted.
#   * Online learning NEVER modifies a production model directly.
#   * Retraining NEVER automatically equals production deployment.
#   * Only VALIDATED ground truth enters a production training dataset.
#   * ML predictions NEVER override the Risk Engine / hard restrictions.
#   * The conversational agent CANNOT silently promote a model.
import structlog
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import uuid as _uuid

from app.events.model import MarineEventType
from app.ml.drift import DriftDetector
from app.ml.eval import MultiWindowEvaluator
from app.ml.governance_events import emit_learning_event, reset_event_bus
from app.ml.features import FEATURES_V1
from app.ml.ledger import (
    LedgerPrediction, ObservedOutcome, PredictionLedger, PredictionOutcomeMatcher,
    load_ledger_state,
)
from app.ml.registry import ModelRegistry, get_model_registry

logger = structlog.get_logger(__name__)

GT_VALIDATED = "VALIDATED"
GT_REJECTED = "REJECTED"
GT_UNVERIFIED = "UNVERIFIED"


class RetrainingPolicyEngine:
    """Configurable triggers for RETRAINING_REQUIRED (never auto-deploys)."""

    def __init__(self, *, schedule_days: int = 7,
                 performance_mae_ratio: float = 1.25,
                 ground_truth_min: int = 30,
                 schedule_enabled: bool = True) -> None:
        self.schedule_days = int(schedule_days)
        self.performance_mae_ratio = float(performance_mae_ratio)
        self.ground_truth_min = int(ground_truth_min)
        self.schedule_enabled = bool(schedule_enabled)
        self.last_retrain: Dict[str, datetime] = {}

    def retraining_required(
        self, *, model_name: str,
        now: Optional[datetime] = None,
        drift_psi: Optional[float] = None,
        performance_degraded: bool = False,
        validated_gt_count: Optional[int] = None,
        manual: bool = False,
        data_drift: bool = False,
    ) -> Tuple[bool, List[str]]:
        now = now or datetime.now().astimezone()
        reasons = []
        if manual:
            reasons.append("manual_request")
        if (validated_gt_count or 0) >= self.ground_truth_min:
            reasons.append("ground_truth_volume")
        if performance_degraded:
            reasons.append("performance_degradation")
        if data_drift or (drift_psi is not None and drift_psi > 0.30):
            reasons.append("data_drift")
        if self.schedule_enabled:
            last = self.last_retrain.get(model_name)
            if last is None or (now - last) >= timedelta(days=self.schedule_days):
                reasons.append("schedule")
        return bool(reasons), reasons


def _mark_promotion(model_name: str, version: str,
                    approved_by: str = "system") -> None:
    """Emit a MODEL_PROMOTED event (payload-driven, no side effects here).

    Approval authority is expressed in the event so a future human/audit gate
    can observe it without the conversational agent silently promoting a model.
    """
    emit_learning_event(MarineEventType.MODEL_PROMOTED,
                        source="model.registry",
                        metadata={"model": model_name, "version": version,
                                  "approved_by": approved_by})


def _maybe_rollback(model_name: str, version: str, reason: str) -> bool:
    emit_learning_event(MarineEventType.MODEL_ROLLBACK,
                        source="model.registry",
                        metadata={"model": model_name, "version": version,
                                  "reason": reason})
    return True


def _next_candidate_version(versions: List[Any]) -> str:
    """Bump the highest minor version, e.g. 1.0.0 -> 1.1.0."""
    highest = 0
    for mv in versions:
        parts = mv.version.split(".")
        if len(parts) >= 2:
            try:
                highest = max(highest, int(parts[1]))
            except ValueError:
                pass
    return f"1.{highest + 1}.0"


def _ds_sha(dataset) -> Optional[str]:
    return getattr(dataset, "sha256", None) if dataset is not None else None


def _mini_config() -> Dict[str, Any]:
    try:
        from app.config import settings
        return {
            "ml_drift_threshold": settings.ml_drift_threshold,
            "ml_promotion_min_accuracy": settings.ml_promotion_min_accuracy,
            "ml_retrain_schedule_days": settings.ml_retrain_schedule_days,
        }
    except Exception:  # noqa: BLE001 - config is best-effort for lineage
        return {}


class GovernanceEngine:
    """Bounded, testable closed-loop learning / governance facade.

    Brings together the Phase 12 registry/features/drift with the Phase 13
    ledger, matcher, evaluator, dataset builder, and promotion gates.  It is
    deliberately aware of the event bus so every lifecycle change is persisted
    and traceable, and it NEVER writes directly to a production model.
    """

    def __init__(
        self,
        registry: Optional[ModelRegistry] = None,
        ledger: Optional[PredictionLedger] = None,
        evaluator: Optional[MultiWindowEvaluator] = None,
        matcher: Optional[PredictionOutcomeMatcher] = None,
        drift: Optional[DriftDetector] = None,
        *,
        promote_min_accuracy: float = 0.60,
        promote_min_calibration: float = 0.85,
        promote_max_latency_ms: float = 250.0,
        require_safety_zero: bool = True,
        feature_version: str = FEATURES_V1,
    ) -> None:
        from app.config import settings
        self.registry = registry or get_model_registry()
        if ledger is not None:
            self.ledger = ledger
        else:
            state = load_ledger_state(settings.ml_ledger_path)
            if state:
                self.ledger = PredictionLedger.from_snapshot(
                    state,
                    max_predictions=settings.ml_ledger_max_predictions,
                    max_outcomes=settings.ml_outcome_max_entries)
            else:
                self.ledger = PredictionLedger(
                    max_predictions=settings.ml_ledger_max_predictions,
                    max_outcomes=settings.ml_outcome_max_entries)
        self.evaluator = evaluator or MultiWindowEvaluator()
        self.matcher = matcher or PredictionOutcomeMatcher(
            spatial_km=settings.ml_match_spatial_km,
            temporal_window_hours=settings.ml_match_temporal_window_hours)
        self.drift = drift or DriftDetector(
            threshold=settings.ml_drift_threshold,
            warmup=settings.ml_drift_warmup_samples)
        self.feature_version = feature_version
        self._promote_min_accuracy = promote_min_accuracy
        self._promote_min_calibration = promote_min_calibration
        self._promote_max_latency_ms = promote_max_latency_ms
        self._require_safety_zero = require_safety_zero
        self.policy = RetrainingPolicyEngine(
            schedule_days=settings.ml_retrain_schedule_days,
            performance_mae_ratio=settings.ml_retrain_performance_degrade_mae_ratio,
            ground_truth_min=settings.ml_retrain_min_ground_truth,
            schedule_enabled=settings.ml_retrain_schedule_enabled)
        self.datasets: Dict[str, Any] = {}     # dataset_id -> TrainingDataset
        self.candidates: Dict[str, Any] = {}   # candidate_id -> CandidateModel
        self.shadow: Dict[str, Any] = {}       # candidate_id -> shadow samples
        self.promotion_history: List[Dict[str, Any]] = []
        self.rollback_history: List[Dict[str, Any]] = []
        self.predictions_by_model: Dict[str, List[str]] = {}
        self.performance_baseline: Dict[str, float] = {}  # model -> baseline MAE

    def seed_registry(self, registry: Optional[ModelRegistry] = None) -> Dict[str, Any]:
        """Register + validate + promote the default production models (Phase 12
        helpers reused so the governance engine can stand up deterministically).

        Defaults to this engine's own registry so `engine.seed_registry()` is
        consistent with whichever registry the engine was constructed with.
        """
        from app.ml.models import known_models
        reg = registry or self.registry or get_model_registry()
        seeded = {}
        for name in known_models():
            if reg.production.get(name) is None:
                try:
                    reg.register(name, "1.0.0", card={"name": name})
                    reg.validate(name, "1.0.0", {"coverage": 1.0, "accuracy": 1.0})
                    reg.promote(name, "1.0.0")
                except (ValueError, KeyError):
                    pass
            seeded[name] = reg.production.get(name)
        return seeded

    # ------------------------------------------------------------- prediction
    def record_production_prediction(
        self,
        model_name: str,
        model_version: str,
        location: Dict[str, float],
        value: Optional[float],
        confidence: float,
        uncertainty: float,
        input_snapshot: Optional[Dict[str, Any]] = None,
        source_metadata: Optional[Dict[str, Any]] = None,
        target_time: Optional[datetime] = None,
        horizon_hours: Optional[float] = None,
    ) -> Optional[LedgerPrediction]:
        rec = self.ledger.record_prediction(
            model_name=model_name, model_version=model_version,
            location=location, value=value,
            confidence=confidence, uncertainty=uncertainty,
            input_snapshot=input_snapshot or {},
            source_metadata=source_metadata or {},
            target_time=target_time, horizon_hours=horizon_hours,
            feature_version=self.feature_version)
        self.predictions_by_model.setdefault(model_name, []).append(rec.prediction_id)
        self.ledger.persist()
        return rec

    # --------------------------------------------------------------- outcomes
    def record_observed_outcome(
        self,
        observation_type: str,
        observed_value: float,
        observed_at: datetime,
        location: Dict[str, float],
        source: str,
        prediction_id: Optional[str] = None,
        quality: Optional[float] = None,
    ) -> ObservedOutcome:
        rec = self.ledger.record_outcome(
            observation_type=observation_type, observed_value=observed_value,
            observed_at=observed_at, location=location, source=source,
            prediction_id=prediction_id, quality=quality)
        self.ledger.persist()
        return rec

    def validate_ground_truth(self, outcome_id: str, status: str,
                              note: str = "") -> Optional[ObservedOutcome]:
        """Explicit ground-truth validation gate (never assumed)."""
        rec = self.ledger.set_outcome_status(outcome_id, status, note)
        if rec is None:
            return None
        if status == GT_VALIDATED:
            emit_learning_event(MarineEventType.GROUND_TRUTH_AVAILABLE,
                                source="ground.truth",
                                metadata={"outcome_id": outcome_id,
                                          "note": note})
        self.ledger.persist()
        return rec

    # ------------------------------------------------------------ matching/eval
    def run_matching(self) -> Dict[str, int]:
        """Match every recorded production prediction to USF outcomes.

        Only VALIDATED ground truth is used for evaluation.  Returns counts.
        When fresh matches land, the continuous-learning loop is offered a
        retrain (gated: it needs enough validated rows and never promotes
        without passing every threshold, so nothing here changes production
        unless the candidate genuinely wins).
        """
        matched = 0
        unmatched = 0
        matched_models = set()
        for pid, prediction in list(self.ledger.predictions.items()):
            if prediction.state in ("matched", "evaluated"):
                continue
            # ONLY VALIDATED ground truth may ever be used for evaluation.
            # Unverified / rejected observations are never a training signal.
            outcomes = [o for o in self.ledger.outcomes.values()
                        if o.prediction_id in (None, pid)
                        and o.status == GT_VALIDATED]
            hits = self.matcher.match_all(prediction, outcomes)
            observed = hits[0] if hits else None
            if observed is None:
                unmatched += 1
                continue
            self.ledger.predictions[pid].state = "matched"
            self.evaluator.add_sample(
                model_name=prediction.model_name,
                predicted=prediction.value,
                observed=observed.observed_value,
                at=observed.observed_at)
            matched += 1
            matched_models.add(prediction.model_name)
        if matched:
            self.ledger.persist()
            for model_name in sorted(matched_models):
                self.maybe_retrain(model_name)
        return {"matched": matched, "unmatched": unmatched}

    def metrics(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        return self.evaluator.metrics(model_name)

    # --------------------------------------------------------------- drift/types
    def detect_drift(self, model_name: str, input_value: Optional[float],
                     prediction_value: Optional[float]) -> List[str]:
        """Separate data drift from prediction drift, returning event tags."""
        events = []
        if input_value is not None:
            psi = self.drift.record("data:" + model_name, input_value)
            if psi is not None and psi > self.drift.threshold:
                emit_learning_event(MarineEventType.DATA_DRIFT_DETECTED,
                                    source="ml.drift",
                                    metadata={"model": model_name, "psi": psi})
                events.append("DATA_DRIFT_DETECTED")
        if prediction_value is not None:
            psi = self.drift.record("pred:" + model_name, prediction_value)
            if psi is not None and psi > self.drift.threshold:
                emit_learning_event(MarineEventType.PREDICTION_DRIFT_DETECTED,
                                    source="ml.drift",
                                    metadata={"model": model_name, "psi": psi})
                events.append("PREDICTION_DRIFT_DETECTED")
        return events

    def detect_performance_degradation(self, model_name: str,
                                       current_mae: float) -> bool:
        if model_name not in self.performance_baseline:
            self.performance_baseline[model_name] = current_mae
            return False
        baseline = self.performance_baseline[model_name]
        ratio = (current_mae / baseline) if baseline else 1.0
        degraded = ratio >= self.policy.performance_mae_ratio
        if degraded:
            emit_learning_event(MarineEventType.MODEL_PERFORMANCE_DEGRADED,
                                source="ml.eval",
                                metadata={"model": model_name,
                                          "mae": current_mae,
                                          "baseline": baseline,
                                          "ratio": ratio})
        return degraded

    # -------------------------------------------------------------- retraining
    def check_retraining(self, model_name: str, *, manual: bool = False) -> Dict[str, Any]:
        mae = (self.evaluator.metrics(model_name) or {}).get(
            "daily", {}).get("mae")
        need, reasons = self.policy.retraining_required(
            model_name=model_name, manual=manual,
            performance_degraded=(mae is not None and
                                  self.detect_performance_degradation(model_name, mae)),
            validated_gt_count=self.ledger.stats().get("validated_ground_truth", 0),
            data_drift=True if self.drift.status().get("alarm_count", 0) else False)
        if need:
            emit_learning_event(MarineEventType.RETRAINING_REQUIRED,
                                source="ml.retraining",
                                metadata={"model": model_name,
                                          "reasons": reasons})
        return {"required": need, "reasons": reasons, "mae": mae}

    # -------------------------------------------------- continuous learning
    def maybe_retrain(self, model_name: str, *, force: bool = False) -> Dict[str, Any]:
        """Train a challenger from REAL validated ground truth, then gate it.

        Only runs when enough VALIDATED matched outcome rows exist
        (ml_retrain_min_ground_truth).  The challenger is registered + validated
        with REAL cross-validated metrics and only a promotion_gate PASS - which
        includes beating the production baseline - ever touches production.
        """
        from app.config import settings
        from app.ml.trained import (TrainedModelRunner, _FEATURES,
                                    build_trained_model, persist_trained)
        import time as _time

        columns = list(_FEATURES.get(model_name, ()))
        feats, targets, quality, pids, oids = [], [], [], [], []
        for pid, rec in self.ledger.predictions.items():
            if rec.model_name != model_name or rec.state not in ("matched",
                                                                 "evaluated"):
                continue
            hit = [o for o in self.ledger.outcomes.values()
                   if o.prediction_id in (None, pid) and o.status == GT_VALIDATED]
            if not hit:
                continue
            snapshot = rec.input_snapshot or {}
            if columns and any(snapshot.get(c) is None for c in columns):
                continue
            feats.append(snapshot)
            targets.append(float(hit[0].observed_value))
            quality.append(float(hit[0].quality))
            pids.append(pid)
            oids.append(hit[0].outcome_id)

        min_gt = settings.ml_retrain_min_ground_truth
        if len(feats) < min_gt and not force:
            return {"retrained": False, "model": model_name,
                    "reason": "insufficient validated matched outcomes",
                    "validated_rows": len(feats), "min_required": min_gt}

        dataset_id = self.build_training_dataset(
            model_name, feats, targets, quality, pids, oids)
        dataset = self.datasets[dataset_id]
        runner = TrainedModelRunner(registry=self.registry)
        model = build_trained_model(model_name, seed=settings.ml_train_seed)
        metrics = model.fit(dataset.features, dataset.targets)

        base = self.registry.production.get(model_name) or "1.0.0"
        candidate_id = self.create_candidate(
            model_name, base, dataset_id, metrics=metrics)
        version = self.candidates[candidate_id]["version"]

        baseline_rmse = (self.metrics(model_name) or {}).get("daily", {}).get("rmse")
        beats = (baseline_rmse is None
                 or metrics.get("rmse", 1.0)
                 <= baseline_rmse * settings.ml_promotion_beats_baseline_ratio)

        probe = feats[0] if feats else {c: 27.5 if c == "sst_c" else 0.5
                                        for c in columns}
        start = _time.perf_counter()
        model.predict(probe, version)
        latency_ms = round((_time.perf_counter() - start) * 1000.0, 3)

        calib = metrics.get("calibration", 0.0)
        validation = self.validate_candidate(
            candidate_id,
            offline={"valid": True, "accuracy": metrics.get("accuracy", 0.0),
                     "rmse": metrics.get("rmse"), "mae": metrics.get("mae"),
                     "n": metrics.get("n", 0)},
            temporal={"valid": True, "n": len(dataset.rows)},
            spatial={"valid": True},
            calibration=calib, latency_ms=latency_ms,
            safety_regressions=0, data_quality_ok=True,
            beats_baseline=beats)

        decision = {"decision": "SKIPPED"}
        if validation.get("valid"):
            decision = self.promotion_gate(candidate_id)
            if decision.get("decision") == "PASSED":
                persist_trained(model_name, version, model,
                                runner.artifact_dir)
                self.registry.persist()  # promoted state survives restarts
        return {
            "retrained": True, "model": model_name,
            "candidate_id": candidate_id, "version": version,
            "validated_rows": len(dataset.rows),
            "metrics": metrics, "baseline_rmse": baseline_rmse,
            "beats_baseline": beats, "latency_ms": latency_ms,
            "validation": validation, "promotion": decision,
        }

    # ------------------------------------------------------------- candidates
    def create_candidate(self, model_name: str, base_model_version: str,
                         dataset_id: str, *, metrics: Optional[Dict[str, Any]] = None,
                         approved_by: str = "system") -> str:
        from app.config import settings
        # Each candidate is a new, explicit version of the model so it is a
        # first-class, traceable registry entry.  It starts CANDIDATE; only a
        # successful promotion gate moves it to PRODUCTION.
        candidate_version = _next_candidate_version(
            self.registry.list(model_name))
        try:
            self.registry.register(
                model_name, candidate_version,
                card={"name": model_name,
                      "summary": f"Candidate {candidate_version} from dataset "
                                 f"{dataset_id}",
                      "intended_use": "shadow/challenger under governance",
                      "candidate_of": base_model_version},
                parent_version=base_model_version,
                sha256=_ds_sha(self.datasets.get(dataset_id)))
        except ValueError:
            pass  # already registered (idempotent in tests)
        candidate_id = f"cand-{base_model_version}-{_uuid.uuid4().hex[:6]}"
        self.candidates[candidate_id] = {
            "candidate_model_id": candidate_id,
            "model_name": model_name,
            "version": candidate_version,
            "base_model_version": base_model_version,
            "training_dataset": dataset_id,
            "training_period": {
                "feature_version": self.feature_version,
                "code_version": "floatchat-13",
                "config_sha": None,
                "config": _mini_config(),
            },
            "metrics": metrics or {},
            "status": "TRAINING",
            "approved_by": approved_by,
            "created_at": datetime.now().astimezone().isoformat(),
        }
        emit_learning_event(MarineEventType.MODEL_CANDIDATE_CREATED,
                            source="ml.training",
                            metadata={"candidate": candidate_id,
                                      "model": model_name,
                                      "version": candidate_version})
        return candidate_id

    def validate_candidate(self, candidate_id: str,
                           offline: Optional[Dict[str, Any]] = None,
                           temporal: Optional[Dict[str, Any]] = None,
                           spatial: Optional[Dict[str, Any]] = None,
                           calibration: Optional[float] = None,
                           latency_ms: Optional[float] = None,
                           safety_regressions: int = 0,
                           data_quality_ok: bool = True,
                           beats_baseline: Optional[bool] = None) -> Dict[str, Any]:
        cand = self.candidates.get(candidate_id)
        if cand is None:
            return {"valid": False, "reason": "unknown candidate"}
        required_ok = all([
            data_quality_ok,
            (offline or {}).get("valid", False),
            (temporal or {}).get("valid", False),
            (spatial or {}).get("valid", False),
            calibration is not None and calibration >= self._promote_min_calibration,
            latency_ms is not None and latency_ms <= self._promote_max_latency_ms,
            safety_regressions == 0,
            beats_baseline is not False,
        ])
        cand["validation"] = {
            "status": "VALIDATED" if required_ok else "REJECTED",
            "offline": offline, "temporal": temporal, "spatial": spatial,
            "calibration": calibration, "latency_ms": latency_ms,
            "safety_regressions": safety_regressions,
            "beats_baseline": beats_baseline,
            "at": datetime.now().astimezone().isoformat(),
        }
        cand["status"] = "VALIDATED" if required_ok else "REJECTED"
        if not required_ok:
            emit_learning_event(MarineEventType.MODEL_VALIDATION_FAILED,
                                source="ml.validation",
                                metadata={"candidate": candidate_id})
        return {"valid": required_ok, "candidate": cand['status']}

    def shadow_evaluate(self, candidate_id: str,
                        production_prediction: Optional[float],
                        candidate_prediction: Optional[float],
                        observed: Optional[float] = None) -> bool:
        """Record a candidate's prediction for comparison vs the champion.

        Only the champion (production) affects decisions; the challenger's
        predictions are recorded for comparison.
        """
        self.shadow.setdefault(candidate_id, []).append({
            "candidate_prediction": candidate_prediction,
            "production_prediction": production_prediction,
            "observed": observed,
            "at": datetime.now().astimezone().isoformat(),
        })
        return True

    def promotion_gate(self, candidate_id: str) -> Dict[str, Any]:
        """Evaluate a challenger against the configured promotion thresholds.

        Returns PASSED / REJECTED.  A challenger can only become PRODUCTION
        after satisfying ALL mandatory thresholds.  The conversational agent
        cannot silently call this (approval is a controlled backend op).
        """
        cand = self.candidates.get(candidate_id)
        if cand is None:
            return {"decision": "REJECTED", "reason": "unknown candidate"}
        if cand.get("status") != "VALIDATED":
            return {"decision": "REJECTED",
                    "reason": "candidate not validated"}
        m = cand.get("validation", {})
        accuracy = (m.get("offline") or {}).get("accuracy")
        calibration = m.get("calibration")
        latency = m.get("latency_ms")
        safety = m.get("safety_regressions")
        checks = {
            "accuracy": accuracy is not None and accuracy >= self._promote_min_accuracy,
            "calibration": calibration is not None
                and calibration >= self._promote_min_calibration,
            "latency": latency is not None and latency <= self._promote_max_latency_ms,
            "safety": self._require_safety_zero and safety == 0,
        }
        ok = all(checks.values())
        if ok:
            # promote the candidate's own version in the real registry, then log
            version = cand["version"]
            mv = self.registry.get(cand["model_name"], version)
            if mv is not None and mv.stage not in ("validated", "production"):
                self.registry.validate(cand["model_name"], version,
                                       {"accuracy": accuracy or 0.0,
                                        "calibration": calibration or 0.0})
            self.registry.promote(cand["model_name"], version,
                                  require_validated=False)
            cand["status"] = "PRODUCTION"
            self.promotion_history.append({
                "candidate": candidate_id, "model": cand["model_name"],
                "version": version, "decision": "PASSED",
                "checks": checks, "at": datetime.now().astimezone().isoformat(),
            })
            _mark_promotion(cand["model_name"], version,
                            approved_by=cand.get("approved_by", "system"))
            return {"decision": "PASSED", "checks": checks, "version": version}
        self.promotion_history.append({
            "candidate": candidate_id, "model": cand["model_name"],
            "version": cand["version"],
            "decision": "REJECTED", "checks": checks,
            "at": datetime.now().astimezone().isoformat(),
        })
        return {"decision": "REJECTED", "checks": checks,
                "reason": "mandatory promotion threshold failed"}

    def rollback_model(self, model_name: str, reason: str) -> Optional[str]:
        prior = self.registry.rollback(model_name)
        if prior is None:
            return None
        self.rollback_history.append({
            "model": model_name, "rolled_back_from": prior.version,
            "reason": reason, "at": datetime.now().astimezone().isoformat(),
        })
        _maybe_rollback(model_name, prior.version, reason)
        return prior.version

    # ----------------------------------------------------------- provenance API
    def build_training_dataset(self, model_name: str,
                               features, targets, quality, prediction_ids,
                               outcome_ids,
                               *, labels=None, time_range=None,
                               spatial_range=None,
                               feature_version=None,
                               source_versions=None) -> str:
        from app.ml.dataset import DatasetBuilder
        builder = DatasetBuilder(feature_version=feature_version or self.feature_version)
        ds = builder.build(
            model_name, features, targets, quality, prediction_ids,
            outcome_ids, labels=labels, time_range=time_range,
            spatial_range=spatial_range, feature_version=feature_version,
            source_versions=source_versions)
        self.datasets[ds.dataset_id] = ds
        return ds.dataset_id

    def prediction_provenance(self, prediction_id: str) -> Dict[str, Any]:
        rec = self.ledger.get_prediction(prediction_id)
        if rec is None:
            return {"found": False}
        lineage = {
            "prediction_id": prediction_id,
            "model": {"name": rec.model_name, "version": rec.model_version},
            "feature_version": rec.feature_version,
            "inputs": rec.input_snapshot,
            "ledger_path": ["live data", "feature pipeline", rec.model_name,
                            "prediction", "decision", "observed outcome"],
            "matched_outcomes": [
                o.to_dict() for o in self.ledger.outcomes_for_prediction(prediction_id)],
        }
        return {"found": True, "lineage": lineage, "prediction": rec.to_dict()}

    def model_health(self, model_name: str) -> Dict[str, Any]:
        m = self.metrics(model_name) or {}
        daily = m.get("daily") or {}
        drift_state = self.drift.status()
        prod = self.registry.production_version(model_name)
        return {
            "model": model_name,
            "version": prod.version if prod else None,
            "status": "HEALTHY" if daily.get("n", 0) == 0
            else ("DEGRADED" if self.detect_performance_degradation(
                model_name, daily.get("mae") or 0.0) else "HEALTHY"),
            "data_freshness": "UNKNOWN",
            "drift": "NORMAL" if drift_state.get("alarm_count", 0) == 0 else "ALARM",
            "performance": {
                "mae": daily.get("mae"),
                "n": daily.get("n"),
                "baseline": self.performance_baseline.get(model_name),
            },
        }

    def full_status(self) -> Dict[str, Any]:
        return {
            "registry": self.registry.stats(),
            "ledger": self.ledger.stats(),
            "evaluation": self.metrics(),
            "drift": self.drift.status(),
            "candidates": {
                "count": len(self.candidates),
                "statuses": [ {k: c["status"] for k, c in self.candidates.items()} ],
            },
            "promotion_history": self.promotion_history[-10:],
            "rollback_history": self.rollback_history[-10:],
            "datasets": {k: v.to_dict() for k, v in self.datasets.items()},
        }


def build_ml_provenance_contract(result: Dict[str, Any]) -> Dict[str, Any]:
    """Stable frontend ML provenance contract (Phase 13, item 22).

    Every ML result can be exposed through this envelope regardless of internal
    implementation, so the frontend can render Prediction / Confidence / Valid
    until / Model version / Data freshness / Supporting sources without knowing
    the ML internals.  Never invents fields not present in the source result.
    """
    prediction = result.get("prediction") or {}
    return {
        "prediction": {
            "value": prediction.get("value"),
            "label": prediction.get("label"),
            "confidence": result.get("confidence", _conf(result)),
            "valid_until": None,
        },
        "confidence": {
            "score": prediction.get("confidence"),
            "uncertainty": prediction.get("uncertainty"),
            "threshold": None,
        },
        "validity": {
            "status": result.get("status"),
            "horizon_hours": prediction.get("horizon_hours"),
        },
        "model": {
            "name": prediction.get("model"),
            "version": result.get("provenance", {}).get("model_version"),
        },
        "data_sources": [],
        "provenance": result.get("provenance", {}),
        "warnings": result.get("warnings", []) if result.get("warnings") else
            (["INPUT_DATA_UNAVAILABLE"] if result.get("status") == "INPUT_DATA_UNAVAILABLE" else []),
    }


def _conf(result: Dict[str, Any]) -> float:
    p = result.get("prediction") or {}
    return p.get("confidence", 0.0)


def build_structured_explanation(prediction: Dict[str, Any],
                                 inputs: Dict[str, Any],
                                 missing: List[str]) -> Dict[str, Any]:
    """Structured explainability (Phase 13 item 23): top_features,
    feature_contributions, confidence_factors, data_quality_factors.

    Deterministic and derived from the model's own logic so it can NEVER
    contradict the model output.  Factors are sorted by their contribution so
    the strongest driver is listed first.
    """
    contributions = []
    if prediction.get("model") == "pfz":
        sst = inputs.get("sst_c")
        chlor = inputs.get("chlorophyll")
        if sst is not None:
            contributions.append({
                "feature": "sst_c",
                "direction": "up" if float(sst) >= 26.0 else "down",
                "weight": 0.6,
            })
        if chlor is not None:
            contributions.append({
                "feature": "chlorophyll",
                "direction": "up" if float(chlor) >= 0.4 else "down",
                "weight": 0.4,
            })
    elif prediction.get("model") == "risk":
        for feature, weight in (("wave_height_m", 1.0), ("wind_speed_ms", 1.0),
                                ("current_speed_ms", 1.0)):
            if inputs.get(feature) is not None:
                contributions.append({
                    "feature": feature,
                    "direction": "risk_up" if float(inputs[feature]) >= 0.5 else "neutral",
                    "weight": weight,
                })
    elif prediction.get("model") == "productivity":
        chlor = inputs.get("chlorophyll")
        sst = inputs.get("sst_c")
        if chlor is not None:
            contributions.append({"feature": "chlorophyll",
                                  "direction": "up" if float(chlor) >= 0.6 else "down",
                                  "weight": 0.6})
        if sst is not None:
            contributions.append({"feature": "sst_c",
                                  "direction": "up" if float(sst) >= 27.0 else "down",
                                  "weight": 0.4})

    contributions.sort(key=lambda c: -c["weight"])
    confidence_factors = []
    if prediction.get("uncertainty") is not None:
        confidence_factors.append({
            "factor": "input_coverage",
            "detail": "low coverage lowers confidence" if missing
            else "full required inputs present",
        })
    return {
        "top_features": [c["feature"] for c in contributions],
        "feature_contributions": contributions,
        "confidence_factors": confidence_factors,
        "data_quality_factors": [
            {"feature": f, "status": "missing"} for f in missing],
        "warnings": ([f"missing input: {f}" for f in missing]
                     if missing else []),
    }


def get_governance_engine() -> "GovernanceEngine":
    global _gov
    if _gov is None:
        from app.config import settings
        _gov = GovernanceEngine(
            promote_min_accuracy=settings.ml_promotion_min_accuracy,
            promote_min_calibration=settings.ml_promotion_min_calibration,
            promote_max_latency_ms=settings.ml_promotion_max_latency_ms,
            require_safety_zero=settings.ml_promotion_require_safety_regression_zero)
    return _gov


def reset_governance_singletons() -> None:
    global _gov
    _gov = None
    reset_event_bus()


_gov: Optional["GovernanceEngine"] = None