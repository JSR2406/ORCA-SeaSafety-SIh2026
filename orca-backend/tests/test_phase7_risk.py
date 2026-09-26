"""Phase 7 tests: risk artifacts + production inference separates calm vs storm."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_risk_artifacts_exist():
    base = os.path.join(os.path.dirname(__file__), "..", "models", "risk")
    for f in ("risk_xgb.joblib", "features.json", "metadata.json", "shap_importance.json"):
        assert os.path.exists(os.path.join(base, f)), f"missing {f}"


def test_risk_separates_calm_storm():
    from ml.common.schemas import RiskFeatureVector
    from ml.risk.predict import predict_risk
    calm = predict_risk(RiskFeatureVector(wave_height_m=1.0, wind_speed_ms=3.0))
    storm = predict_risk(RiskFeatureVector(wave_height_m=4.0, wind_speed_ms=16.0))
    assert storm.probability > calm.probability
    assert storm.label in ("HIGH", "VERY_HIGH") and calm.label in ("LOW", "MODERATE")
    assert storm.top_positive_features
