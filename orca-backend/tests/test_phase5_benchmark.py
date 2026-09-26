"""Phase 5 tests: metric contract + benchmark ranking on tiny separable data."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_compute_metrics_contract():
    from ml.fishing.evaluate import compute_metrics, REQUIRED_METRICS
    m = compute_metrics([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9])
    for k in REQUIRED_METRICS:
        assert k in m
    assert m["roc_auc"] > 0.9 and len(m["calibration"]) > 0


def test_benchmark_selects_best_by_pr_auc(tmp_path):
    import pandas as pd
    from ml.fishing.train import run
    cols = ["lat", "lon", "sst_c", "chlorophyll", "wind_speed_ms", "wind_direction_deg",
            "current_speed_ms", "current_direction_deg", "wave_height_m", "depth_m",
            "distance_from_coast_km", "month", "season_idx", "hour", "target"]
    def mk(n, sep):
        import numpy as np
        r = np.random.default_rng(0)
        sst = r.normal(28.3, 0.5, n) + sep * 0.0
        y = ([0] * (n // 2) + [1] * (n - n // 2))
        d = {c: r.uniform(0, 1, n) for c in cols if c != "target"}
        d.update({"sst_c": sst, "chlorophyll": [0.3 if v == 0 else 1.2 for v in y],
                  "target": y})
        return pd.DataFrame(d)
    tr, va, te = str(tmp_path / "tr.pq"), str(tmp_path / "va.pq"), str(tmp_path / "te.pq")
    mk(60, 0).to_parquet(tr)
    mk(30, 0).to_parquet(va)
    mk(30, 0).to_parquet(te)
    rep = run(tr, va, te)
    assert rep["best"] in ("logreg", "random_forest", "xgboost", "lightgbm")
    assert set(rep["ranking_by_pr_auc"]) <= set(rep["candidates"])
    assert "metrics_test" in rep["results"][rep["best"]]
