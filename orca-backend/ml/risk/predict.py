"""Risk inference: baseline RiskModel today, production XGBoost when registered."""
import json
import os
from ml.common.schemas import ModelPrediction, RiskFeatureVector

MODEL_DIR = os.getenv("ML_MODEL_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "models"))
VERSION = os.getenv("RISK_MODEL_VERSION", "1.2.0-baseline")


def _baseline_proba(rv: RiskFeatureVector) -> float:
    from ml.models import RiskModel
    return float(RiskModel().predict({
        "wave_height_m": rv.wave_height_m, "wind_speed_ms": rv.wind_speed_ms,
        "current_speed_ms": rv.current_speed_ms}).value or 0.0)


def _drivers(n=3):
    try:
        with open(os.path.join(MODEL_DIR, "risk", "shap_importance.json")) as f:
            imp = json.load(f).get("importance", {})
        ranked = sorted(imp, key=lambda k: imp[k], reverse=True)
        return ranked[:n], ranked[-1:] if ranked else []
    except Exception:
        return [], []


def predict_risk(rv: RiskFeatureVector) -> ModelPrediction:
    version, proba, calibrated, artifact = VERSION, None, False, ""
    for name in ("risk_xgb.joblib", "risk_xgb.json"):
        p = os.path.join(MODEL_DIR, "risk", name)
        if os.path.exists(p):
            try:
                import joblib
                b = joblib.load(p)
                proba = float(b["model"].predict_proba([rv.ordered()])[0][1])
                version = str(b.get("version", version))
                calibrated = bool(b.get("calibrated", False))
                artifact = os.path.basename(p)
                break
            except Exception:
                continue
    if proba is None:
        proba = _baseline_proba(rv)
    label = "VERY_HIGH" if proba >= 0.8 else ("HIGH" if proba >= 0.6 else ("MODERATE" if proba >= 0.35 else "LOW"))
    pos, neg = _drivers()
    return ModelPrediction(model="marine_risk", version=version, probability=round(proba, 4),
                           label=label, top_positive_features=pos, top_negative_features=neg,
                           feature_values={"wave_height_m": rv.wave_height_m,
                           "wind_speed_ms": rv.wind_speed_ms, "wave_period_s": rv.wave_period_s,
                           "cyclone_distance_km": rv.cyclone_distance_km,
                           "lightning_flag": rv.lightning_flag},
                           calibration={"calibrated": calibrated, "artifact": artifact or "baseline"})
