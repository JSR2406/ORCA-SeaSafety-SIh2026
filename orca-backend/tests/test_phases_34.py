"""Phase 3+4 tests: gateway source labels, preprocess, time-split dataset. No network."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from datetime import datetime


def test_gateway_labels_sources_without_network(monkeypatch):
    from ml.data_pipeline import gateway
    # Force both upstream tiers offline: THREDDS errors, Open-Meteo stubbed.
    import ml.data_pipeline.scrapers.incois_thredds as th
    monkeypatch.setattr(th, "extract_point",
                        lambda lat, lon, timeout_s=12.0: (_ for _ in ()).throw(RuntimeError("offline")))
    import ml.data_pipeline.weather as w
    monkeypatch.setattr(w, "fetch_marine_fallback",
                        lambda lat, lon, vt, timeout_s=8.0: {
                            "lat": lat, "lon": lon, "source": "OPEN_METEO", "quality": "ok",
                            "wave_height_m": 1.2, "sst_c": 28.0})
    gateway._FEAT_CACHE.clear()
    from datetime import datetime
    out = gateway.get_marine_features(9.93, 76.27, datetime(2025, 6, 1, 6, 0))
    assert out["wave_height_m__source"] == "OPEN_METEO"  # fallback labeled, never silent
    assert out["official_warning__source"] == "IMD"
    assert any(r["source"] in ("INCOIS", "OPEN_METEO", "IMD") for r in out["records"])


def test_preprocess_drops_empty_and_dedups():
    from ml.fishing.preprocess import preprocess
    rows = [
        {"lat": 9.93111, "lon": 76.27111, "valid_time": "2025-01-01T06:00:00",
         "sst_c": None, "chlorophyll": None, "target": 1},
        {"lat": 9.93, "lon": 76.27, "valid_time": "2025-01-01T06:00:00",
         "sst_c": 28.4, "chlorophyll": 0.9, "target": 1},
        {"lat": 9.9301, "lon": 76.2701, "valid_time": "2025-01-01T06:00:00",
         "sst_c": 28.4, "chlorophyll": 0.9, "target": 1},
    ]
    out = preprocess(rows)
    assert len(out) == 1  # empty dropped, dup rounded+merged


def test_dataset_demo_split_writes_manifest(tmp_path):
    from ml.fishing.dataset import build
    rows = [{"lat": 9.9 + i * 0.01, "lon": 76.2, "valid_time": f"2025-0{(i % 9) + 1}-01T06:00:00",
             "sst_c": 28.0, "chlorophyll": 0.8, "target": i % 2} for i in range(8)]
    m = build(rows, str(tmp_path), demo=True)
    assert sum(m["counts"].values()) == 8 and "time-based split" in m["leakage_guards"][0]
