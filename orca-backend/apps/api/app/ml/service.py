# Phase 12 - model service.
#
# Serves production models with three principled failure modes, never a silent
# hallucinated value:
#
#   MODEL_UNAVAILABLE       - the served model is unregistered/unreachable.
#   INPUT_DATA_UNAVAILABLE  - too few real features to compute a value.
#   PREDICTION_UNCERTAIN    - a value was produced but confidence is low.
#
# The service also:
#   * binds the model registry (candidate -> validated -> production -> rollback);
#   * runs every prediction through the feature store for provenance/versioning;
#   * injects uncertainty using real input coverage, never fabricated confidence;
#   * caches predictions for a bounded TTL (never served as live data);
#   * records input drift as an observable signal.
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog

from app.ml.features import FeatureStore, get_feature_store
from app.ml.models import build_model, known_models, Prediction
from app.ml.registry import ModelRegistry, ModelStage, get_model_registry
from app.ml.drift import DriftDetector, get_drift_detector
from app.ml.trained import load_trained

logger = structlog.get_logger(__name__)


class ModelUnavailable(Exception):
    pass


@dataclass
class ModelResult:
    status: str                      # MODEL_UNAVAILABLE|INPUT_DATA_UNAVAILABLE
                                     # |PREDICTION_UNCERTAIN|OK
    prediction: Optional[Prediction] = None
    provenance: Dict[str, Any] = None
    from_cache: bool = False
    drift: Optional[float] = None
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        base = {
            "status": self.status,
            "provenance": self.provenance or {},
            "from_cache": self.from_cache,
            "drift": self.drift,
            "error": self.error,
        }
        if self.prediction is not None:
            base["prediction"] = self.prediction.to_dict()
        else:
            base["prediction"] = None
        return base


class ModelService:
    """Advisory prediction gateway.  Never overrides the Risk Engine."""

    def __init__(self, registry: Optional[ModelRegistry] = None,
                 feature_store: Optional[FeatureStore] = None,
                 drift: Optional[DriftDetector] = None,
                 *, cache_ttl_seconds: int = 300, cache_max: int = 256,
                 uncertain_threshold: float = 0.60,
                 artifact_dir: Optional[str] = None,
                 trained_enabled: Optional[bool] = None) -> None:
        self.registry = registry or get_model_registry()
        self.features = feature_store or get_feature_store()
        self.drift = drift or get_drift_detector()
        self._cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self._cache_max = cache_max
        self._uncertain_threshold = uncertain_threshold
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._order: List[str] = []
        self._model_singletons: Dict[str, Any] = {}
        from app.config import settings
        self._artifact_dir = artifact_dir or settings.ml_artifact_dir
        self._trained_enabled = (settings.ml_trained_enabled
                                 if trained_enabled is None
                                 else trained_enabled)

    # ------------------------------------------------------------- lifecycle
    def seed_registry(self, *, versions: Optional[Dict[str, List[str]]] = None) -> dict:
        """Register + validate + promote the default production models."""
        seeded = {}
        for name in known_models():
            versions_for = (versions or {}).get(name, ["1.0.0"])
            for version in versions_for:
                if self.registry.get(name, version) is None:
                    mv = self.registry.register(name, version, card={
                        "name": name,
                        "summary": f"Production {name} model (deterministic)",
                        "inputs": self._card_inputs(name),
                        "intended_use": "advisory decision support under the "
                                        "immutable safety hierarchy",
                        "known_limitations": "rule-based; skill ceiling bounded; "
                                             "never authoritative for safety",
                    })
                    self.registry.validate(
                        name, version,
                        {"accuracy_offline": 0.0, "coverage": 1.0})
            # promote the newest registered version
            latest = max(
                (v for v in self.registry.list(name)
                 if v.stage in (ModelStage.VALIDATED, ModelStage.PRODUCTION)),
                key=lambda v: v.version,
                default=None)
            if latest is not None and self.registry.production.get(name) is None:
                self.registry.promote(name, latest.version, require_validated=True)
            seeded[name] = self.registry.production.get(name)
        return seeded

    def _model_for(self, name: str) -> Any:
        mv = self.registry.production_version(name)
        if mv is None:
            raise ModelUnavailable(
                f"model '{name}' has no production version")
        if name not in self._model_singletons:
            self._model_singletons[name] = build_model(name)
        model = self._model_singletons[name]
        return model, mv.version

    # ------------------------------------------------------------------ predict
    def predict(self, name: str, variables: Dict[str, Any],
                *, key: str = "", force: bool = False) -> ModelResult:
        # 1. production wiring
        try:
            model, version = self._model_for(name)
        except ModelUnavailable as exc:
            return ModelResult(status="MODEL_UNAVAILABLE", error=str(exc))

        # 1b. if the production version is a trained model, serve its fitted
        # artifact; a missing/corrupt artifact degrades to the rule baseline
        # (never an outage, never a silent confident value).
        trained = None
        if self._trained_enabled:
            trained = load_trained(name, version, self._artifact_dir)
            if trained is not None:
                model = trained

        # 2. provenance
        if key:
            self.features.put(key, _StateView(variables))
            self.features.persist()
        provenance = {
            "model": name,
            "model_version": version,
            "feature_version": self.features.version,
            "feature_key": key,
            "served_at": datetime.now().astimezone().isoformat(),
            "trained": trained is not None,
        }

        # 3. bounded cache (never served as live)
        cache_key = f"{name}:{sorted(k for k in variables if variables[k] is not None)}"
        if not force:
            hit = self._cache.get(cache_key)
            if hit and (datetime.now().astimezone() - hit["at"]) < self._cache_ttl:
                result = hit["result"]
                result.from_cache = True
                return result

        # 4. predict
        pred = model.predict(variables, version)

        # 5. uncertainty -> failure mode
        if pred.value is None:
            result = ModelResult(status="INPUT_DATA_UNAVAILABLE",
                                 prediction=pred, provenance=provenance)
        else:
            self.drift.record(name, pred.value)
            if pred.uncertainty >= self._uncertain_threshold:
                result = ModelResult(status="PREDICTION_UNCERTAIN",
                                     prediction=pred, provenance=provenance)
            else:
                result = ModelResult(status="OK", prediction=pred,
                                     provenance=provenance)

        # 6. cache
        self._cache[cache_key] = {"at": datetime.now().astimezone(),
                                  "result": ModelResult(
                                      status=result.status,
                                      prediction=pred,
                                      provenance=provenance)}
        self._order.append(cache_key)
        while len(self._order) > self._cache_max:
            drop = self._order.pop(0)
            self._cache.pop(drop, None)
        return result

    def status(self) -> Dict[str, Any]:
        prod = {name: (self.registry.production.get(name))
                for name in known_models()}
        trained = {}
        for name, version in prod.items():
            if version is None:
                trained[name] = {"active": None}
                continue
            artifact = load_trained(name, version, self._artifact_dir)
            trained[name] = {"active": version,
                             "serving_trained": artifact is not None}
        return {
            "production": prod,
            "registry": self.registry.stats(),
            "features": self.features.stats(),
            "drift": self.drift.status(),
            "cache_entries": len(self._cache),
            "trained": trained,
        }

    @staticmethod
    def _card_inputs(name: str) -> List[str]:
        return list({"pfz": ["sst_c", "chlorophyll"],
                     "productivity": ["sst_c", "chlorophyll"],
                     "risk": ["wave_height_m", "wind_speed_ms",
                              "current_speed_ms"],
                     "forecast": ["sst_c", "chlorophyll"]}[name])


class _StateView:
    """Adapter exposing a plain-dict .variables for the feature store."""

    def __init__(self, variables: Dict[str, Any]) -> None:
        self.variables = variables


_model_service: Optional[ModelService] = None


def get_model_service() -> ModelService:
    global _model_service
    if _model_service is None:
        from app.config import settings
        _model_service = ModelService(cache_ttl_seconds=settings.ml_cache_ttl_seconds,
                                      cache_max=settings.ml_cache_max_entries,
                                      uncertain_threshold=settings.ml_uncertain_confidence_threshold)
        if settings.ml_enabled:
            _model_service.seed_registry()
    return _model_service


def reset_model_singletons() -> None:
    global _model_service
    _model_service = None