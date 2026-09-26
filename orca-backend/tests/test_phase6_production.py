"""Phase 6 tests: production artifacts + loaded inference (uses demo splits)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_production_artifacts_exist():
    base = os.path.join(os.path.dirname(__file__), "..", "models", "fishing")
    for f in ("fishing_xgb.joblib", "features.json", "metadata.json", "shap_importance.json"):
        assert os.path.exists(os.path.join(base, f)), f"missing {f}"


def test_metadata_contract():
    from ml.fishing.predict import metadata
    m = metadata()
    for k in ("training_period", "validation_period", "test_period", "feature_list",
              "target_definition", "metrics_test", "training_timestamp"):
        assert k in m, f"metadata missing {k}"


def test_production_prediction_has_drivers():
    from ml.common.schemas import FishingFeatureVector
    from ml.fishing.predict import predict_fishing
    p = predict_fishing(FishingFeatureVector(lat=9.93, lon=76.27, sst_c=28.4, chlorophyll=0.9))
    assert p.version != "1.2.0-baseline"  # production artifact loaded
    assert 0.0 <= p.probability <= 1.0 and p.top_positive_features
