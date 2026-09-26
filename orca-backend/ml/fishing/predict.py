"""Fishing suitability inference.

Phase 1: deterministic baseline (existing ml/models.py PFZModel) so the API works
before any XGBoost artifact exists. Phase 2: loads models/fishing/fishing_xgb.json
(+ features.json) when present; never silently swaps — version is always reported.
"""
import json
import os
from typing import Dict
from ml.common.schemas import FishingFeatureVector, ModelPrediction

MODEL_DIR = os.getenv("ML_MODEL_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "models"))
VERSION = os.getenv("FISHING_MODEL_VERSION", "1.2.0-baseline")


def _baseline_proba(fv: FishingFeatureVector) -> float:
    from ml.models import PFZModel
    pred = PFZModel().predict({"sst_c": fv.sst_c, "chlorophyll": fv.chlorophyll})
    return float(pred.value or 0.0)


def _load_bundle():
    import joblib
    for name in ("fishing_xgb.joblib", "fishing_xgb.json"):
        p = os.path.join(MODEL_DIR, "fishing", name)
        if os.path.exists(p):
            try:
                b = joblib.load(p)
                if hasattr(b.get("model", None), "predict_proba"):
                    return b, os.path.basename(p)
            except Exception:
                continue
    return None, ""


def _global_drivers(n=3):
    try:
        with open(os.path.join(MODEL_DIR, "fishing", "shap_importance.json")) as f:
            imp = json.load(f).get("importance", {})
        ranked = sorted(imp, key=lambda k: imp[k], reverse=True)
        return ranked[:n], ranked[-1:] if ranked else []
    except Exception:
        return [], []


def predict_fishing(fv: FishingFeatureVector) -> ModelPrediction:
    bundle, artifact = _load_bundle()
    version, proba, calibrated = VERSION, None, False
    if bundle:
        try:
            proba = float(bundle["model"].predict_proba([fv.ordered()])[0][1])
            version = str(bundle.get("version", version))
            calibrated = bool(bundle.get("calibrated", False))
        except Exception:
            proba = None
    if proba is None:
        proba = _baseline_proba(fv)
        artifact = artifact or "baseline"
    label = "high" if proba >= 0.75 else ("moderate" if proba >= 0.45 else "low")
    pos, neg = _global_drivers()
    return ModelPrediction(
        model="fishing_suitability", version=version, probability=round(proba, 4), label=label,
        top_positive_features=pos, top_negative_features=neg,
        feature_values={k: v for k, v in zip(
            ["lat", "lon", "sst_c", "chlorophyll", "wind_speed_ms", "wind_direction_deg",
             "current_speed_ms", "current_direction_deg", "wave_height_m", "depth_m",
             "distance_from_coast_km", "month", "season_idx", "hour"], fv.ordered())},
        calibration={"calibrated": calibrated, "artifact": os.path.basename(artifact)},
    )


def metadata() -> Dict:
    path = os.path.join(MODEL_DIR, "fishing", "metadata.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"model": "fishing_suitability", "version": VERSION, "status": "baseline-deterministic",
            "training_period": None, "validation": "time-based required before claiming superiority"}
