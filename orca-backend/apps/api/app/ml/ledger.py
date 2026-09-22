# Phase 13 - prediction ledger, observed outcomes and prediction->outcome matching.
#
# Every production ML prediction is recorded in a bounded, versioned ledger so
# it can be matched, later, against an observed outcome.  Ground truth is never
# assumed to exist: outcomes carry a quality grade and a validation status
# (UNVERIFIED | VALIDATED | REJECTED); only VALIDATED ground truth may enter a
# production training dataset.  Matching is deterministic and geometry-driven
# (spatial proximity + temporal window + prediction horizon + target type).
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog

from app.ml.features import FEATURES_V1

logger = structlog.get_logger(__name__)

_HOURS = 3600.0
_KMS_PER_DEG = 111.0  # ~111 km/degree (used for a cheap spatial window)


def ground_truth_status_defaults() -> List[str]:
    return ["UNVERIFIED", "VALIDATED", "REJECTED"]


@dataclass
class LedgerPrediction:
    prediction_id: str
    model_name: str
    model_version: str
    feature_version: str
    location: Dict[str, float]                 # {"lat", "lon"}
    prediction_time: datetime
    target_time: Optional[datetime]
    horizon_hours: Optional[float]
    value: Optional[float]
    confidence: float
    uncertainty: float
    input_snapshot: Dict[str, Any]
    source_metadata: Dict[str, Any] = field(default_factory=dict)
    state: str = "recorded"                    # recorded|matched|evaluated
    created_at: datetime = field(default_factory=lambda: datetime.now().astimezone())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prediction_id": self.prediction_id,
            "model": {"name": self.model_name, "version": self.model_version,
                      "feature_version": self.feature_version},
            "location": self.location,
            "prediction_time": self.prediction_time.isoformat(),
            "target_time": self.target_time.isoformat() if self.target_time else None,
            "horizon_hours": self.horizon_hours,
            "prediction": self.value,
            "confidence": self.confidence,
            "uncertainty": self.uncertainty,
            "input_snapshot": self.input_snapshot,
            "source_metadata": self.source_metadata,
            "state": self.state,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LedgerPrediction":
        model = data.get("model") or {}
        return cls(
            prediction_id=data["prediction_id"],
            model_name=model.get("name", ""),
            model_version=model.get("version", ""),
            feature_version=model.get("feature_version", FEATURES_V1),
            location=data.get("location") or {},
            prediction_time=datetime.fromisoformat(data["prediction_time"]),
            target_time=(datetime.fromisoformat(data["target_time"])
                         if data.get("target_time") else None),
            horizon_hours=data.get("horizon_hours"),
            value=data.get("prediction"),
            confidence=data.get("confidence", 0.0),
            uncertainty=data.get("uncertainty", 0.0),
            input_snapshot=data.get("input_snapshot") or {},
            source_metadata=data.get("source_metadata") or {},
            state=data.get("state", "recorded"),
            created_at=(datetime.fromisoformat(data["created_at"])
                        if data.get("created_at") else datetime.now().astimezone()),
        )


@dataclass
class ObservedOutcome:
    outcome_id: str
    prediction_id: Optional[str]
    observation_type: str                 # wave_height_m|productivity|pfz|...
    observed_value: float
    observed_at: datetime
    location: Dict[str, float]
    source: str
    quality: float                        # 0..1 (higher = more trustworthy)
    status: str = "UNVERIFIED"           # UNVERIFIED|VALIDATED|REJECTED
    validation_note: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now().astimezone())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outcome_id": self.outcome_id,
            "prediction_id": self.prediction_id,
            "observation_type": self.observation_type,
            "observed_value": self.observed_value,
            "observed_at": self.observed_at.isoformat(),
            "location": self.location,
            "source": self.source,
            "quality": self.quality,
            "status": self.status,
            "validation_note": self.validation_note,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ObservedOutcome":
        return cls(
            outcome_id=data["outcome_id"],
            prediction_id=data.get("prediction_id"),
            observation_type=data["observation_type"],
            observed_value=data["observed_value"],
            observed_at=datetime.fromisoformat(data["observed_at"]),
            location=data.get("location") or {},
            source=data.get("source", ""),
            quality=data.get("quality", 0.9),
            status=data.get("status", "UNVERIFIED"),
            validation_note=data.get("validation_note", ""),
            created_at=(datetime.fromisoformat(data["created_at"])
                        if data.get("created_at") else datetime.now().astimezone()),
        )


class PredictionLedger:
    """Bounded, in-memory prediction ledger + outcome store (persistence hooks
    optional).  Deliberately DB-light so the learning loop is testable offline."""

    def __init__(self, max_predictions: int = 2000, max_outcomes: int = 2000) -> None:
        self._max_predictions = max_predictions
        self._max_outcomes = max_outcomes
        self.predictions: Dict[str, LedgerPrediction] = {}
        self.outcomes: Dict[str, ObservedOutcome] = {}
        self._pred_order: List[str] = []

    # ------------------------------------------------------------- predictions
    def record_prediction(
        self,
        model_name: str,
        model_version: str,
        location: Dict[str, float],
        prediction_time: Optional[datetime] = None,
        target_time: Optional[datetime] = None,
        horizon_hours: Optional[float] = None,
        value: Optional[float] = None,
        confidence: float = 0.0,
        uncertainty: float = 0.0,
        input_snapshot: Optional[Dict[str, Any]] = None,
        source_metadata: Optional[Dict[str, Any]] = None,
        feature_version: str = FEATURES_V1,
        prediction_id: Optional[str] = None,
    ) -> LedgerPrediction:
        prediction_time = prediction_time or datetime.now().astimezone()
        prediction_id = prediction_id or f"pred-{uuid.uuid4().hex[:12]}"
        rec = LedgerPrediction(
            prediction_id=prediction_id,
            model_name=model_name, model_version=model_version,
            feature_version=feature_version,
            location={"lat": float(location.get("lat")), "lon": float(location.get("lon"))},
            prediction_time=prediction_time,
            target_time=target_time,
            horizon_hours=horizon_hours,
            value=value, confidence=confidence, uncertainty=uncertainty,
            input_snapshot=input_snapshot or {},
            source_metadata=source_metadata or {},
        )
        self.predictions[prediction_id] = rec
        self._pred_order.append(prediction_id)
        if len(self._pred_order) > self._max_predictions:
            drop = self._pred_order[0]
            self.predictions.pop(drop, None)
            self._pred_order = self._pred_order[1:]
        return rec

    def get_prediction(self, prediction_id: str) -> Optional[LedgerPrediction]:
        return self.predictions.get(prediction_id)

    def recent_predictions(self, limit: int = 100) -> List[LedgerPrediction]:
        out = [self.predictions[k] for k in self._pred_order if k in self.predictions]
        out.sort(key=lambda p: p.created_at, reverse=True)
        return out[:limit]

    # ---------------------------------------------------------------- outcomes
    def record_outcome(
        self,
        observation_type: str,
        observed_value: float,
        observed_at: datetime,
        location: Dict[str, float],
        source: str,
        prediction_id: Optional[str] = None,
        quality: Optional[float] = None,
        outcome_id: Optional[str] = None,
    ) -> ObservedOutcome:
        if quality is None:
            from app.config import settings
            quality = settings.ml_ground_truth_default_quality
        outcome_id = outcome_id or f"out-{uuid.uuid4().hex[:12]}"
        rec = ObservedOutcome(
            outcome_id=outcome_id,
            prediction_id=prediction_id,
            observation_type=observation_type,
            observed_value=float(observed_value),
            observed_at=observed_at,
            location={"lat": float(location.get("lat")), "lon": float(location.get("lon"))},
            source=source,
            quality=max(0.0, min(1.0, float(quality))),
        )
        self.outcomes[outcome_id] = rec
        if len(self.outcomes) > self._max_outcomes:
            # drop oldest un-matched/oldest entry deterministically
            oldest = min(self.outcomes, key=lambda k: self.outcomes[k].created_at)
            self.outcomes.pop(oldest, None)
        return rec

    def get_outcome(self, outcome_id: str) -> Optional[ObservedOutcome]:
        return self.outcomes.get(outcome_id)

    def outcomes_for_prediction(self, prediction_id: str) -> List[ObservedOutcome]:
        return [o for o in self.outcomes.values() if o.prediction_id == prediction_id]

    def set_outcome_status(self, outcome_id: str, status: str,
                           validation_note: str = "") -> Optional[ObservedOutcome]:
        rec = self.outcomes.get(outcome_id)
        if rec is None:
            return None
        rec.status = status
        rec.validation_note = validation_note
        return rec

    def stats(self) -> Dict[str, Any]:
        validated = sum(1 for o in self.outcomes.values() if o.status == "VALIDATED")
        return {
            "predictions": len(self.predictions),
            "outcomes": len(self.outcomes),
            "validated_ground_truth": validated,
            "rejected_ground_truth": sum(
                1 for o in self.outcomes.values() if o.status == "REJECTED"),
        }

    # ------------------------------------------------------- state persistence
    def to_snapshot(self) -> Dict[str, Any]:
        """JSON-serializable ledger state (ordered predictions + outcomes)."""
        return {
            "predictions": [self.predictions[k].to_dict()
                            for k in self._pred_order if k in self.predictions],
            "outcomes": [self.outcomes[k].to_dict()
                         for k in sorted(self.outcomes.keys())],
        }

    @classmethod
    def from_snapshot(cls, snapshot: Dict[str, Any],
                      max_predictions: int = 2000,
                      max_outcomes: int = 2000) -> "PredictionLedger":
        """Reconstruct a ledger from a persisted snapshot."""
        ledger = cls(max_predictions=max_predictions, max_outcomes=max_outcomes)
        for data in snapshot.get("predictions") or []:
            try:
                rec = LedgerPrediction.from_dict(data)
            except Exception:  # noqa: BLE001 - skip corrupt rows
                continue
            ledger.predictions[rec.prediction_id] = rec
            ledger._pred_order.append(rec.prediction_id)
        for data in snapshot.get("outcomes") or []:
            try:
                ledger.outcomes[data["outcome_id"]] = ObservedOutcome.from_dict(data)
            except Exception:  # noqa: BLE001 - skip corrupt rows
                continue
        return ledger

    def persist(self, path: Optional[str] = None) -> Optional[str]:
        """Write the ledger snapshot to disk (best-effort, returns path/None)."""
        import json
        import os
        if path is None:
            from app.config import settings
            path = getattr(settings, "ml_ledger_path", None)
        if not path:
            return None
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(self.to_snapshot(), fh, indent=2, default=str)
            return path
        except Exception:  # noqa: BLE001 - observability never fails the loop
            logger.warning("ledger persist failed: %s", path)
            return None


def _distance_km(la: Dict[str, float], lb: Dict[str, float]) -> float:
    dlat = abs(la["lat"] - lb["lat"]) * _KMS_PER_DEG
    dlon = abs(la["lon"] - lb["lon"]) * _KMS_PER_DEG
    return (dlat**2 + dlon**2) ** 0.5


class PredictionOutcomeMatcher:
    """Deterministic rule-based matching of a prediction to observed outcomes.

    A prediction with target_time T and horizon H is matched to an outcome with
    observed_at within [T - window, T + 2*window] (target-time centred), within
    `spatial_km` lateral distance, of the same target type, and of adequate data
    quality for the model being validated.
    """

    def __init__(self, spatial_km: float = 25.0,
                 temporal_window_hours: float = 3.0) -> None:
        self.spatial_km = float(spatial_km)
        self.temporal_window = timedelta(hours=float(temporal_window_hours))

    def match(self, prediction: LedgerPrediction,
              outcome: ObservedOutcome, target_type: Optional[str] = None) -> bool:
        # type match
        expected = target_type or prediction.model_name
        if outcome.observation_type != expected:
            # allow loose mapping: productivity<->pfz are distinct types
            return False
        # spatial match
        if _distance_km(prediction.location, outcome.location) > self.spatial_km:
            return False
        # temporal match centred on target_time (fall back to prediction_time)
        anchor = prediction.target_time or prediction.prediction_time
        if abs(outcome.observed_at - anchor) > self.temporal_window:
            return False
        return True

    def match_all(self, prediction: LedgerPrediction,
                  outcomes: List[ObservedOutcome] = None,
                  strategy: str = "best_quality") -> List[ObservedOutcome]:
        """Return outcomes matching this prediction, best quality first.

        Deterministic: spatial + temporal + type matching, then ordered by
        descending quality, then by ascending observed_at.
        """
        candidates = outcomes if outcomes is not None else []
        hits = [o for o in candidates if self.match(prediction, o)]
        hits.sort(key=lambda o: (-o.quality, o.observed_at))
        return hits


def _target_type_hint(model_name: str) -> str:
    return {
        "pfz": "pfz",
        "risk": "wave_height_m",
        "productivity": "productivity",
        "forecast": "forecast",
    }.get(model_name, model_name)


def load_ledger_state(path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Read a persisted ledger snapshot from disk (None if missing/corrupt)."""
    import json
    import os
    if path is None:
        from app.config import settings
        path = getattr(settings, "ml_ledger_path", None)
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict) or not isinstance(data.get("predictions"), list):
            return None
        return data
    except Exception:  # noqa: BLE001 - corrupt ledger is ignored, never fatal
        logger.warning("ledger load failed: %s", path)
        return None