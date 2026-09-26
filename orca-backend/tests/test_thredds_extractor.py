"""THREDDS extractor tests: offline math + group contracts (no network)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_wind_dir_math():
    from ml.data_pipeline.scrapers.incois_thredds import _wind_dir_deg, _current_dir_deg
    assert _wind_dir_deg(None, 1.0) is None
    assert _wind_dir_deg(0.0, -1.0) == 0.0  # southward wind comes FROM north
    assert 80.0 <= _wind_dir_deg(-1.0, 0.0) <= 100.0  # eastward wind FROM east
    assert _current_dir_deg(0.0, -1.0) == 180.0  # current flows TOWARD south


def test_groups_contract():
    from ml.data_pipeline.scrapers.incois_thredds import GROUPS, SOURCE
    assert SOURCE == "INCOIS-THREDDS"
    assert set(GROUPS) >= {"wave", "winds", "sst"}
    assert "SWH" in GROUPS["wave"]["vars"] and "SST" in GROUPS["sst"]["vars"]


def test_query_group_handles_no_dataset(monkeypatch):
    import ml.data_pipeline.scrapers.incois_thredds as th
    monkeypatch.setattr(th, "_latest_urlpath", lambda g, t=15.0: None)
    out = th._query_group("wave", 9.93, 76.27)
    assert "_error" in out


def test_gateway_prefers_thredds(monkeypatch):
    from datetime import datetime
    import ml.data_pipeline.gateway as gw
    fake = {"lat": 9.93, "lon": 76.27, "source": "INCOIS-THREDDS", "quality": "ok",
            "wave_height_m": 1.1, "wave_period_s": 12.0, "wind_speed_ms": 3.0,
            "wind_direction_deg": 45.0, "current_speed_ms": None,
            "current_direction_deg": None, "sst_c": 28.5, "chlorophyll": None}
    monkeypatch.setattr("ml.data_pipeline.scrapers.incois_thredds.extract_point",
                        lambda lat, lon, timeout_s=12.0: fake)
    import ml.data_pipeline.weather as w
    monkeypatch.setattr(w, "fetch_marine_fallback",
                        lambda lat, lon, vt, timeout_s=8.0: {"source": "OPEN_METEO",
                        "quality": "ok", "current_speed_ms": 0.4})
    out = gw.get_marine_features(9.93, 76.27, datetime(2026, 9, 26, 12, 0))
    assert out["wave_height_m__source"] == "INCOIS-THREDDS"
    assert out["current_speed_ms__source"] == "OPEN_METEO"
    assert out["freshness"] == "live"
