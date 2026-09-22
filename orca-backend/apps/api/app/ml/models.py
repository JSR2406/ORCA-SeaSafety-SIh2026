# Phase 12 - production ML models: PFZ, risk, productivity, scenario forecast.
#
# Each model returns a Prediction with:
#   * point estimate           - the primary value, or None when inputs are
#                                insufficient (a value is never invented);
#   * uncertainty               - 0..1 (higher = less confident), derived from
#                                real input coverage / conflict, not fabricated;
#   * provenance               - feature version + the model version that produced it;
#   * missing_inputs           - which features were absent;
#   * graceful failure modes   - MODEL_UNAVAILABLE / INPUT_DATA_UNAVAILABLE /
#                                PREDICTION_UNCERTAIN surfaced by the service.
#
# These are deterministic, threshold/documentation-driven models (no external
# training infra required) whose skill ceiling is explicitly bounded.  They are
# advisory only and never override the Risk Engine or hard restrictions.
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import fmean
from typing import Any, Dict, List, Optional

from app.ml.features import _NORM

# A scenario/forecast model can be computed for a series of timesteps; horizon
# is measured in days.
DEFAULT_HORIZON_DAYS = 7
STEP_HOURS = 6
STEPS = DEFAULT_HORIZON_DAYS * 24 // STEP_HOURS


@dataclass
class Prediction:
    model: str
    version: str
    value: Optional[float]
    label: Optional[str] = None
    uncertainty: float = 0.0
    provenance: Dict[str, Any] = field(default_factory=dict)
    missing_inputs: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "version": self.version,
            "value": self.value,
            "label": self.label,
            "uncertainty": round(self.uncertainty, 3),
            "provenance": self.provenance,
            "missing_inputs": self.missing_inputs,
            "meta": self.meta,
        }


def _have(variables: Dict[str, Any], *names) -> bool:
    return all(variables.get(n) is not None for n in names)


def _required(*features) -> List[str]:
    return list(_COMBO_REQUIRED.get((features), ()))


# Which features each model needs to produce a non-None estimate.
_REQUIRED = {
    "pfz": ("sst_c", "chlorophyll"),
    "productivity": ("sst_c", "chlorophyll"),
    "risk": ("wave_height_m", "wind_speed_ms"),
    "forecast": ("sst_c", "chlorophyll"),
}
_COMBO_REQUIRED: Dict[Any, tuple] = {}


class _Model:
    name = ""

    def predict(self, variables: Dict[str, Any], version: str) -> Prediction:
        raise NotImplementedError

    def _pred(self, variables, version, value, label=None, meta=None,
              uncertainty=0.0) -> Prediction:
        required = _REQUIRED.get(self.name, ())
        missing = [f for f in required if variables.get(f) is None]
        return Prediction(
            model=self.name, version=version, value=value, label=label,
            uncertainty=uncertainty,
            provenance={"feature_version": "1.0.0", "model_version": version},
            missing_inputs=missing,
            meta=meta or {})


class PFZModel(_Model):
    """Potential Fishing Zone: favorability from SST + chlorophyll."""

    name = "pfz"

    def predict(self, variables: Dict[str, Any], version: str) -> Prediction:
        sst = variables.get("sst_c")
        chlor = variables.get("chlorophyll")
        if not _have(variables, "sst_c", "chlorophyll"):
            return self._pred(variables, version, None,
                              meta={"reason": "sst_c and chlorophyll required"})
        sst_f = _score01(float(sst), 25.0, 30.0)
        chlor_f = _score01(float(chlor), 0.15, 1.00)
        value = _clamp01(0.6 * sst_f + 0.4 * chlor_f)
        # Uncertainty rises when a key variable sits at band edge (ambiguous).
        uncertainty = 0.5 * (_edge_penalty(float(sst), 25.0, 30.0)
                             + _edge_penalty(float(chlor), 0.15, 1.00))
        return self._pred(variables, version, value,
                          label=_level(value, ["none", "low", "moderate",
                                               "high", "very_high"]),
                          uncertainty=uncertainty,
                          meta={"caveat": "rule-based favorability, not a catch "
                                          "forecast", "sst_c": sst, "chlorophyll": chlor})


class RiskModel(_Model):
    """Transparent risk score from wave + wind (+ current)."""

    name = "risk"

    def predict(self, variables: Dict[str, Any], version: str) -> Prediction:
        if not _have(variables, "wave_height_m", "wind_speed_ms"):
            return self._pred(variables, version, None,
                              meta={"reason": "wave_height_m and wind_speed_ms "
                                              "required"})
        wave = float(variables["wave_height_m"])
        wind = float(variables["wind_speed_ms"])
        wave_r = _bounded_01(wave, 1.5, 5.0)   # 0 at safe, 1 at extreme
        wind_r = _bounded_01(wind, 8.0, 22.0)
        current = variables.get("current_speed_ms")
        current_r = _bounded_01(float(current), 0.5, 2.0) if current is not None else 0.0
        value = _clamp01(max(wave_r, wind_r, current_r))  # adversarial: max
        uncertainty = 0.3 * (0 if current is not None else 1.0)
        return self._pred(variables, version, value,
                          label=_level(value, ["low", "low", "moderate",
                                               "elevated", "extreme"],
                                       ascending=True),
                          uncertainty=uncertainty,
                          meta={"note": "advisory risk proxy; the RiskEngine "
                                        "remains authoritative"})


class ProductivityModel(_Model):
    """SRP productivity proxy from chlorophyll + SST."""

    name = "productivity"

    def predict(self, variables: Dict[str, Any], version: str) -> Prediction:
        if not _have(variables, "sst_c", "chlorophyll"):
            return self._pred(variables, version, None,
                              meta={"reason": "sst_c and chlorophyll required"})
        chlor = variables.get("chlorophyll")
        sst = variables.get("sst_c")
        chlor_f = _score01(float(chlor), 0.20, 2.00)
        sst_f = _score01(float(sst), 25.0, 30.0)
        value = _clamp01(0.6 * chlor_f + 0.4 * sst_f)
        uncertainty = 0.4 * _edge_penalty(float(chlor), 0.20, 2.00)
        label = "oligotrophic" if value < 0.25 else (
            "moderate" if value < 0.50 else (
                "productive" if value < 0.75 else "highly_productive"))
        return self._pred(variables, version, value, label=label,
                          uncertainty=uncertainty,
                          meta={"note": "satellite-inferred productivity proxy"})


class ForecastModel(_Model):
    """Scenario forecast: extrapolate present variables over a horizon.

    Produces a bounded series over the horizon; each step keeps its own
    uncertainty so far-future steps are honestly less certain.  It never
    invents a value when inputs are missing - it returns unavailable.
    """

    name = "forecast"

    def __init__(self, horizon_days: int = DEFAULT_HORIZON_DAYS) -> None:
        self.horizon_days = horizon_days
        self.steps = horizon_days * 24 // STEP_HOURS

    def predict(self, variables: Dict[str, Any], version: str,
                now: Optional[datetime] = None) -> Prediction:
        if not _have(variables, "sst_c", "chlorophyll"):
            return self._pred(variables, version, None,
                              meta={"reason": "sst_c and chlorophyll required",
                                    "horizon_days": self.horizon_days})
        now = now or datetime.now().astimezone()
        base_sst = float(variables["sst_c"])
        base_chlor = float(variables["chlorophyll"])
        base = _score01(base_sst, 25.0, 30.0) * 0.5 + \
            _score01(base_chlor, 0.15, 1.00) * 0.5
        series = []
        for i in range(self.steps):
            t = i + 1
            # deterministic mild mean-reversion toward the ideal band; the
            # farther out, the wider the honest uncertainty.
            sst = base_sst + 0.5 * (27.5 - base_sst) * (t / self.steps)
            chlor = base_chlor + 0.5 * (0.5 - base_chlor) * (t / self.steps)
            step_fav = _clamp01(0.6 * _score01(sst, 25.0, 30.0) +
                                0.4 * _score01(chlor, 0.15, 1.00))
            uncertainty = _clamp01(0.15 + 0.60 * (t / self.steps))
            series.append({
                "step": i + 1,
                "at": (now + timedelta(hours=STEP_HOURS * (i + 1))).isoformat(),
                "value": round(step_fav, 3),
                "uncertainty": round(uncertainty, 3),
                "sst_c": round(sst, 2),
                "chlorophyll": round(chlor, 3),
            })
        return self._pred(
            variables, version, base, label=_level(base, ["none", "low",
                                                          "moderate", "high",
                                                          "very_high"]),
            uncertainty=_clamp01(0.2 + 0.5 * _edge_penalty(base_sst, 25.0, 30.0)),
            meta={"horizon_days": self.horizon_days, "steps": self.steps,
                  "series": series, "note": "deterministic scenario forecast; "
                                            "skill degrades with horizon"})


def _score01(value: float, ideal_lo: float, ideal_hi: float) -> float:
    if ideal_lo <= value <= ideal_hi:
        return 1.0 - _edge_penalty(value, ideal_lo, ideal_hi) * 0.5
    lo_span = ideal_lo
    hi_span = 1.0 - ideal_hi + 1.0  # nominal far side
    if value < ideal_lo:
        return _clamp01((value - 0.0) / max(lo_span, 1e-6) * 0.5)
    # value > ideal_hi
    return _clamp01(1.0 - (value - ideal_hi) / max(hi_span, 1e-6) * 0.5)


def _edge_penalty(value: float, lo: float, hi: float) -> float:
    """0 in the middle of the band, growing to 0.5 at either edge."""
    mid = (lo + hi) / 2.0
    half = max((hi - lo) / 2.0, 1e-6)
    return _clamp01(abs(value - mid) / half) * 0.5


def _bounded_01(value: float, safe: float, extreme: float) -> float:
    if value <= safe:
        return 0.0
    if value >= extreme:
        return 1.0
    return _clamp01((value - safe) / (extreme - safe))


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def _level(value: float, labels: List[str], ascending: bool = False) -> str:
    if value is None:
        return None
    idx = int(value * len(labels))
    idx = min(len(labels) - 1, idx)
    return labels[idx]


# ------------------------------------------------------------------ models map
_MODELS = {
    "pfz": PFZModel(),
    "risk": RiskModel(),
    "productivity": ProductivityModel(),
    "forecast": ForecastModel(horizon_days=DEFAULT_HORIZON_DAYS),
}


def build_model(name: str):
    """Construct a model instance by name (fresh, for registry binding)."""
    if name == "forecast":
        return ForecastModel(horizon_days=DEFAULT_HORIZON_DAYS)
    cls = {"pfz": PFZModel, "risk": RiskModel, "productivity": ProductivityModel}
    if name not in cls:
        raise KeyError(f"unknown model {name}")
    return cls[name]()


def known_models() -> List[str]:
    return ["pfz", "risk", "productivity", "forecast"]