"""Unit tests for ML foundation schemas + risk engine + route (no training, no network)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ml.common.schemas import FishingFeatureVector, RiskFeatureVector
from ml.risk_engine.rules import decide
from ml.route.cost import cell_cost
from ml.route.graph import astar
from ml.fishing.predict import predict_fishing
from ml.risk.predict import predict_risk


def test_fishing_vector_order_matches_training_list():
    from ml.common.schemas import FISHING_FEATURES
    fv = FishingFeatureVector(lat=9.9, lon=76.2, sst_c=28.4, chlorophyll=0.9)
    assert len(fv.ordered()) == len(FISHING_FEATURES) == 14


def test_risk_vector_order_matches_training_list():
    from ml.common.schemas import RISK_FEATURES
    rv = RiskFeatureVector(wave_height_m=1.4)
    assert len(rv.ordered()) == len(RISK_FEATURES) == 12


def test_official_warning_overrides_low_ml():
    d = decide(ml_risk=0.1, official_warning=True)
    assert d.status == "OFFICIAL_WARNING" and "official warning overrides ML" in d.overrides


def test_geofence_overrides_everything():
    d = decide(ml_risk=0.05, geofence_hit="SECTOR_BRAVO")
    assert d.status == "HARD_RESTRICTION"


def test_stale_data_never_safe():
    d = decide(ml_risk=0.05, data_fresh=False)
    assert d.status == "UNKNOWN"


def test_route_cost_modes():
    assert cell_cost(mode="SHORTEST") < cell_cost(mode="SAFEST", wave_risk=5.0)


def test_astar_avoids_blocked():
    grid = {(0, 0): 1.0, (0, 1): 1.0, (1, 0): 1.0, (1, 1): 1.0}
    assert astar(grid, (0, 0), (1, 1)) != []


def test_baseline_predictors_run():
    fp = predict_fishing(FishingFeatureVector(lat=9.9, lon=76.2, sst_c=28.4, chlorophyll=0.9))
    rp = predict_risk(RiskFeatureVector(wave_height_m=1.4))
    assert 0.0 <= fp.probability <= 1.0 and 0.0 <= rp.probability <= 1.0
