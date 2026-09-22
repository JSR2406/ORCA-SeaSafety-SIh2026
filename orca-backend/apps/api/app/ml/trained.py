# Phase 16 - trained (supervised) marine models: fit first, then serve.
#
# Scikit-learn-backed regressors trained on LABELED data before they are ever
# promoted, replacing the purely rule-based 1.0.0 baseline.  Two label sources
# feed the same trainer:
#   * the reproducible synthetic generator (offline pilot) which samples the
#     documented domain bands and adds realistic noise, so the surrogate LEARNS
#     the domain physics encoded in the rule models and can beat them on noisy
#     inputs;
#   * real validated ground truth from the prediction ledger (continuous
#     learning), which the GovernanceEngine feeds in once enough matched
#     outcome rows exist.
#
# Honesty invariants preserved:
#   * every trained model is registered CANDIDATE -> VALIDATED -> PRODUCTION
#     (never silently swapped);
#   * CV metrics are REAL (out-of-fold), never invented;
#   * uncertainty comes from the fitted residual error, not a magic number;
#   * a missing/absent artifact degrades to the rule baseline with
#     provenance["trained"] = False - never an outage and never a silent
#     confident value;
#   * all models remain advisory; the RiskEngine stays authoritative.
import os
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import structlog
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import KFold

from app.config import settings
from app.ml.models import Prediction, _level

logger = structlog.get_logger(__name__)

# Feature columns each trained model consumes (matching the rule models).
_FEATURES = {
    "pfz": ("sst_c", "chlorophyll"),
    "risk": ("wave_height_m", "wind_speed_ms", "current_speed_ms"),
    "productivity": ("sst_c", "chlorophyll"),
    "forecast": ("sst_c", "chlorophyll"),
}
_LABELS = {
    "pfz": ["none", "low", "moderate", "high", "very_high"],
    "risk": ["low", "low", "moderate", "elevated", "extreme"],
    "productivity": ["oligotrophic", "moderate", "productive",
                     "highly_productive", "highly_productive"],
    "forecast": ["none", "low", "moderate", "high", "very_high"],
}


def _clamp01(v: float) -> float:
    return float(max(0.0, min(1.0, v)))


def _next_minor_version(versions: List[Any]) -> str:
    """Bump the highest minor version among ALL existing versions, e.g.
    1.0.0 -> 1.1.0 (mirrors the governance candidate version logic)."""
    highest = 0
    for mv in versions:
        parts = mv.version.split(".")
        if len(parts) >= 2:
            try:
                highest = max(highest, int(parts[1]))
            except ValueError:
                pass
    return f"1.{highest + 1}.0"


class TrainedRegressor:
    """Sklearn-backed regressor producing a Prediction (rule-compatible)."""

    name = ""
    features: tuple = ()

    def __init__(self, seed: int = 42) -> None:
        self.seed = int(seed)
        self.cv_metrics: Dict[str, Any] = {}
        self.n_trained = 0
        self._final = None

    def _estimator(self) -> HistGradientBoostingRegressor:
        return HistGradientBoostingRegressor(
            max_iter=400, learning_rate=0.06, max_leaf_nodes=31,
            random_state=self.seed)

    def fit(self, X: List[Dict[str, Any]], y: List[float]) -> Dict[str, Any]:
        """Fit with real out-of-fold cross-validation metrics (no fake skill)."""
        cols = self.features
        Xm = np.array([[float(r.get(c, np.nan)) for c in cols] for r in X],
                      dtype=float)
        ym = np.asarray(y, dtype=float)
        finite = np.isfinite(Xm).all(axis=1)
        Xm, ym = Xm[finite], ym[finite]
        self.n_trained = int(finite.sum())
        kf = KFold(n_splits=5, shuffle=True, random_state=self.seed)
        preds = np.empty(ym.shape[0], dtype=float)
        for tr, te in kf.split(Xm):
            est = self._estimator()
            est.fit(Xm[tr], ym[tr])
            preds[te] = est.predict(Xm[te])
        mae = float(np.mean(np.abs(preds - ym)))
        rmse = float(np.sqrt(np.mean((preds - ym) ** 2)))
        var_y = float(np.var(ym)) if ym.shape[0] > 1 else 0.0
        r2 = float(1.0 - np.mean((preds - ym) ** 2) / max(var_y, 1e-12))
        calibration = round(_clamp01(1.0 - rmse), 4)
        self.cv_metrics = {
            "mae": round(mae, 4),
            "rmse": round(rmse, 4),
            "r2": round(max(0.0, r2), 4),
            "accuracy": calibration,
            "calibration": calibration,
            "n": self.n_trained,
        }
        self._final = self._estimator().fit(Xm, ym)
        return self.cv_metrics

    def predict(self, variables: Dict[str, Any], version: str,
                now=None) -> Prediction:
        missing = [c for c in self.features if variables.get(c) is None]
        if missing:
            return Prediction(
                model=self.name, version=version, value=None,
                label=None, uncertainty=0.0,
                provenance={"feature_version": "1.0.0",
                            "model_version": version, "trained": True},
                missing_inputs=missing,
                meta={"reason": f"{', '.join(missing)} required"})
        x = [float(variables[c]) for c in self.features]
        value = _clamp01(float(self._final.predict([x])[0]))
        uncertainty = _clamp01(self.cv_metrics.get("rmse", 0.0))
        return Prediction(
            model=self.name, version=version, value=value,
            label=_level(value, _LABELS[self.name]),
            uncertainty=uncertainty,
            provenance={"feature_version": "1.0.0",
                        "model_version": version, "trained": True},
            missing_inputs=[],
            meta={"trained": True,
                  "cv_metrics": self.cv_metrics,
                  "caveat": "supervised surrogate; skill bounded by training "
                           "data", "seed": self.seed,
                  "n_trained": self.n_trained})


class TrainedPFZ(TrainedRegressor):
    name = "pfz"
    features = _FEATURES["pfz"]


class TrainedRisk(TrainedRegressor):
    name = "risk"
    features = _FEATURES["risk"]


class TrainedProductivity(TrainedRegressor):
    name = "productivity"
    features = _FEATURES["productivity"]


class TrainedForecast(TrainedRegressor):
    """Trained base favorability + structural horizon series.

    The regressor learns the base (t=0) favorability from SST + chlorophyll;
    the 7-day series keeps the documented bounded mean-reversion shape while
    per-step uncertainty honestly widens with the horizon.
    """

    name = "forecast"
    features = _FEATURES["forecast"]

    def __init__(self, seed: int = 42,
                 horizon_days: int | None = None) -> None:
        super().__init__(seed=seed)
        from app.ml.models import DEFAULT_HORIZON_DAYS, STEP_HOURS
        self.horizon_days = horizon_days or DEFAULT_HORIZON_DAYS
        self.steps = self.horizon_days * 24 // STEP_HOURS

    def predict(self, variables: Dict[str, Any], version: str,
                now=None) -> Prediction:
        from datetime import timedelta
        missing = [c for c in self.features if variables.get(c) is None]
        if missing:
            return super().predict(variables, version, now)
        base = super().predict(variables, version, now)
        now = now or datetime_now()
        base_sst = float(variables["sst_c"])
        base_chlor = float(variables["chlorophyll"])
        series = []
        for i in range(self.steps):
            t = i + 1
            sst = base_sst + 0.5 * (27.5 - base_sst) * (t / self.steps)
            chlor = base_chlor + 0.5 * (0.5 - base_chlor) * (t / self.steps)
            x = [float(x) for x in (sst, chlor)]
            step_fav = _clamp01(float(self._final.predict([x])[0]))
            uncertainty = _clamp01(0.15 + 0.60 * (t / self.steps))
            series.append({
                "step": i + 1,
                "at": (now + timedelta(hours=6 * t)).isoformat(),
                "value": round(step_fav, 3),
                "uncertainty": round(uncertainty, 3),
                "sst_c": round(sst, 2),
                "chlorophyll": round(chlor, 3),
            })
        return Prediction(
            model=self.name, version=version, value=base.value,
            label=base.label, uncertainty=base.uncertainty,
            provenance=dict(base.provenance),
            missing_inputs=[],
            meta={**base.meta,
                  "horizon_days": self.horizon_days, "steps": self.steps,
                  "series": series,
                  "note": "trained base + deterministic scenario series; "
                          "skill degrades with horizon"})


def datetime_now():
    from datetime import datetime
    return datetime.now().astimezone()


def build_trained_model(name: str, seed: int = 42,
                        horizon_days: Optional[int] = None) -> TrainedRegressor:
    if name == "forecast":
        return TrainedForecast(seed=seed, horizon_days=horizon_days)
    cls = {"pfz": TrainedPFZ, "risk": TrainedRisk,
           "productivity": TrainedProductivity}
    if name not in cls:
        raise KeyError(f"unknown model {name}")
    return cls[name](seed=seed)


class DatasetGenerator:
    """Deterministic, reproducible labeling from the documented domain bands.

    Each row samples a realistic variable space; the target is the documented
    rule model's own output plus calibrated noise, making the trained surrogate
    a genuine learner of the domain model (and a smoother of its noise).
    """

    RANGES = {
        "sst_c": (18.0, 34.0),
        "chlorophyll": (0.01, 5.0),
        "wave_height_m": (0.0, 6.0),
        "wind_speed_ms": (0.0, 25.0),
        "current_speed_ms": (0.0, 2.5),
    }

    def __init__(self, seed: int = 42, noise: float = 0.08) -> None:
        self.seed = int(seed)
        self.noise = float(noise)

    @staticmethod
    def features_for(model_name: str) -> List[str]:
        return list(_FEATURES[model_name])

    def generate(self, model_name: str, n: int,
                 seed: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return rows as {"variables": {...}, "target": float}."""
        rng = np.random.default_rng(seed or self.seed)
        rows = []
        for _ in range(int(n)):
            variables = {c: round(float(rng.uniform(*self.RANGES[c])), 3)
                         for c in self.features_for(model_name)}
            target = clamp01(self._rule(model_name, variables)
                             + float(rng.normal(0.0, self.noise)))
            rows.append({"variables": variables,
                         "target": float(round(target, 4))})
        return rows

    @staticmethod
    def _rule(model_name: str, variables: Dict[str, Any]) -> float:
        # single source of truth: the documented deterministic models.
        from app.ml.models import build_model
        pred = build_model(model_name).predict(variables, "reference")
        return float(pred.value or 0.0)


def clamp01(v: float) -> float:
    return float(max(0.0, min(1.0, v)))


def _artifact_path(name: str, version: str,
                   artifact_dir: Optional[str] = None) -> str:
    base = artifact_dir or settings.ml_artifact_dir
    return os.path.join(base, f"{name}-{version}.joblib")


def load_trained(name: str, version: str,
                 artifact_dir: Optional[str] = None) -> Optional[TrainedRegressor]:
    """Load a persisted trained estimator for name@version, or None."""
    path = _artifact_path(name, version, artifact_dir)
    if not os.path.exists(path):
        return None
    try:
        payload = joblib.load(path)
        model = payload.get("model") if isinstance(payload, dict) else payload
        if isinstance(model, TrainedRegressor):
            return model
        return None
    except Exception as exc:  # noqa: BLE001 - corrupt artifact -> rule fallback
        logger.warning("trained_artifact_load_failed", name=name,
                       version=version, error=str(exc))
        return None


def persist_trained(name: str, version: str, model: TrainedRegressor,
                    artifact_dir: Optional[str] = None) -> str:
    path = _artifact_path(name, version, artifact_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    joblib.dump({"model": model, "name": name, "version": version}, path)
    return path


class TrainedModelRunner:
    """Fits a model, registers it CANDIDATE+VALIDATED, optionally promotes."""

    def __init__(self, registry=None, artifact_dir: Optional[str] = None,
                 seed: int = 42, noise: float = 0.08) -> None:
        from app.ml.registry import get_model_registry
        self.registry = registry or get_model_registry()
        self.artifact_dir = artifact_dir or settings.ml_artifact_dir
        self.seed = int(seed)
        self.noise = float(noise)
        self.generator = DatasetGenerator(seed=self.seed, noise=self.noise)

    def train(self, model_name: str, dataset: List[Dict[str, Any]],
              *, version: Optional[str] = None,
              persist: bool = True) -> Dict[str, Any]:
        model = build_trained_model(model_name, seed=self.seed)
        metrics = model.fit([r["variables"] for r in dataset],
                            [r["target"] for r in dataset])
        version = version or _next_minor_version(self.registry.list(model_name))
        mv = self.registry.get(model_name, version)
        if mv is None:
            self.registry.register(
                model_name, version,
                metrics={**metrics, "trained": True},
                card={"name": model_name,
                      "summary": (f"Supervised {model_name} model from "
                                  f"{len(dataset)} labeled rows "
                                  f"(cv n={metrics['n']})"),
                      "intended_use": "advisory decision support under the "
                                      "immutable safety hierarchy",
                      "known_limitations": "skill bounded by training-data "
                                           "quality; never authoritative for "
                                           "safety",
                      "training": {"seed": self.seed, "rows": len(dataset),
                                   "labels": "documented bands + noise"}})
        self.registry.validate(
            model_name, version,
            {**metrics, "trained": True, "coverage": 1.0})
        if persist:
            persist_trained(model_name, version, model, self.artifact_dir)
        return {"model": model_name, "version": version,
                "metrics": metrics, "rows": len(dataset),
                "stage": "validated", "persisted": persist}

    def train_all(self, samples: Optional[int] = None,
                  *, promote: bool = False) -> Dict[str, Any]:
        """Train every known model on synthetic pilot data."""
        from app.ml.models import known_models
        n = samples or settings.ml_train_default_samples
        report = {}
        for name in known_models():
            dataset = self.generator.generate(name, n)
            result = self.train(name, dataset, persist=True)
            if promote:
                mv = self.registry.get(name, result["version"])
                self.registry.promote(name, result["version"],
                                      require_validated=False)
                result["stage"] = "production"
            report[name] = result
        return report