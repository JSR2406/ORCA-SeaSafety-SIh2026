"""Phase 5 benchmark: LogReg / RF / XGBoost / LightGBM on TIME splits.

Train → validate (select best by pr_auc) → test best once.
Never random-split-only. Saves reports/fishing_model_comparison.json.

Usage:
    python -m ml.fishing.train --train ml/data/processed/fishing_training_train.parquet \\
        --valid ml/data/processed/fishing_training_valid.parquet \\
        --test ml/data/processed/fishing_training_test.parquet
"""
import argparse, json, os
from datetime import datetime

CANDIDATES = ["logreg", "random_forest", "xgboost", "lightgbm"]


def _load(path):
    import pandas as pd
    if path.endswith((".parquet", ".pq")):
        return pd.read_parquet(path)
    try:
        return pd.read_parquet(path)
    except Exception:
        return pd.read_csv(path)


def _models():
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    ms = {"logreg": LogisticRegression(max_iter=500),
          "random_forest": RandomForestClassifier(n_estimators=100, random_state=7, n_jobs=-1)}
    try:
        from xgboost import XGBClassifier
        ms["xgboost"] = XGBClassifier(n_estimators=100, max_depth=5, learning_rate=0.08,
                                      subsample=0.9, eval_metric="logloss", random_state=7)
    except Exception as e:
        ms["_xgboost_skipped"] = str(e)
    try:
        from lightgbm import LGBMClassifier
        ms["lightgbm"] = LGBMClassifier(n_estimators=100, verbose=-1)
    except Exception as e:
        ms["_lightgbm_skipped"] = str(e)
    return ms


def run(train_p, valid_p, test_p, target="target"):
    from ml.common.schemas import FISHING_FEATURES
    from ml.fishing.evaluate import compute_metrics
    tr, va, te = _load(train_p), _load(valid_p), _load(test_p)
    feats = [f for f in FISHING_FEATURES if f in tr.columns]
    Xtr, ytr = tr[feats].fillna(0), tr[target].astype(int)
    Xva, yva = va[feats].fillna(0), va[target].astype(int)
    Xte, yte = te[feats].fillna(0), te[target].astype(int)
    results, probs = {}, {}
    for name, m in _models().items():
        if name.startswith("_"):
            results[name] = {"status": f"skipped: {m}"}
            continue
        m.fit(Xtr, ytr)
        pv = [float(x) for x in m.predict_proba(Xva)[:, 1]]
        probs[name] = m
        results[name] = {"metrics_valid": compute_metrics(yva.tolist(), pv), "features": feats}
    ranked = sorted([k for k in results if not k.startswith("_")],
                    key=lambda k: results[k]["metrics_valid"]["pr_auc"], reverse=True)
    best = ranked[0] if ranked else None
    if best:
        pt = [float(x) for x in probs[best].predict_proba(Xte)[:, 1]]
        from ml.fishing.evaluate import compute_metrics as cm
        results[best]["metrics_test"] = cm(yte.tolist(), pt)
    return {"candidates": CANDIDATES, "features": feats,
            "train_n": len(tr), "valid_n": len(va), "test_n": len(te),
            "split_policy": "time-based; random split alone insufficient",
            "ranking_by_pr_auc": ranked, "best": best, "results": results,
            "selected_claim": f"best validated={best}; deploy only with acceptable calibration",
            " Run_at": datetime.utcnow().isoformat()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", required=True); ap.add_argument("--valid", required=True)
    ap.add_argument("--test", required=True)
    ap.add_argument("--out", default="reports/fishing_model_comparison.json")
    a = ap.parse_args()
    rep = run(a.train, a.valid, a.test)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w") as f:
        json.dump(rep, f, indent=2)
    print(json.dumps({"best": rep["best"], "ranking": rep["ranking_by_pr_auc"],
                      "out": a.out}, indent=2))


if __name__ == "__main__":
    main()
