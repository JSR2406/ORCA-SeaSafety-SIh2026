"""Phase 6 production: Fishing XGBoost with tuning, early stopping, calibration, SHAP.

Time-based only: fit on train, early-stop + select on valid, report once on test.
Saves models/fishing/{fishing_xgb.joblib, fishing_xgb_booster.json, features.json,
metadata.json, shap_importance.json}. SHAP falls back to gain importance when the
shap package is missing/broken (e.g. numpy-2 incompatibility).

Usage:
    python -m ml.fishing.train_production --train ml/data/processed/fishing_training_train.parquet \\
        --valid ml/data/processed/fishing_training_valid.parquet \\
        --test ml/data/processed/fishing_training_test.parquet --version v1
"""
import argparse, json, os
from datetime import datetime


def _load(path):
    import pandas as pd
    try:
        return pd.read_parquet(path)
    except Exception:
        return pd.read_csv(path)


def _fit_params():
    import inspect
    from xgboost import XGBClassifier
    sig = inspect.signature(XGBClassifier.fit)
    return set(sig.parameters)


def train_one(Xtr, ytr, Xva, yva, depth, lr, pos_weight):
    from xgboost import XGBClassifier
    m = XGBClassifier(n_estimators=200, max_depth=depth, learning_rate=lr,
                      subsample=0.9, colsample_bytree=0.9, eval_metric="logloss",
                      scale_pos_weight=pos_weight, random_state=7, n_jobs=-1)
    kw = {"eval_set": [(Xva, yva)], "verbose": False}
    try:
        m.fit(Xtr, ytr, early_stopping_rounds=20, **kw)
    except TypeError:
        m.fit(Xtr, ytr, **kw)  # xgb 3.x without early_stopping_rounds kw
    return m


def shap_or_gain(model, Xsample, feats):
    try:
        import shap
        ex = shap.TreeExplainer(model)
        sv = ex.shap_values(Xsample[:100])
        import numpy as np
        sv = sv[0] if isinstance(sv, list) else sv
        imp = {f: round(float(np.abs(sv[:, i]).mean()), 5) for i, f in enumerate(feats)}
        return {"method": "shap_tree", "importance": imp}
    except Exception as e:
        try:
            imp = {f: round(float(v), 5) for f, v in
                   zip(feats, model.feature_importances_)}
        except Exception:
            imp = {}
        return {"method": f"gain_fallback ({type(e).__name__})", "importance": imp}


def run(train_p, valid_p, test_p, version="v1", out_dir="models/fishing", target="target",
        train_period="2019-2023", valid_period="2024", test_period="2025"):
    import numpy as np
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.metrics import average_precision_score, brier_score_loss
    from ml.common.schemas import FISHING_FEATURES
    from ml.fishing.evaluate import compute_metrics
    tr, va, te = _load(train_p), _load(valid_p), _load(test_p)
    feats = [f for f in FISHING_FEATURES if f in tr.columns]
    Xtr, ytr = tr[feats].fillna(0).values, tr[target].astype(int).values
    Xva, yva = va[feats].fillna(0).values, va[target].astype(int).values
    Xte, yte = te[feats].fillna(0).values, te[target].astype(int).values
    neg, pos = int((ytr == 0).sum()), int((ytr == 1).sum())
    pw = neg / max(pos, 1)
    best, best_auc, best_cfg = None, -1, {}
    for depth in (4, 6):
        for lr in (0.05, 0.1):
            m = train_one(Xtr, ytr, Xva, yva, depth, lr, pw if pos and neg / pos > 1.5 else 1.0)
            auc = average_precision_score(yva, m.predict_proba(Xva)[:, 1])
            if auc > best_auc:
                best, best_auc, best_cfg = m, auc, {"max_depth": depth, "learning_rate": lr}
    pv = best.predict_proba(Xva)[:, 1]
    brier_raw = brier_score_loss(yva, pv)
    cal = CalibratedClassifierCV(best, method="sigmoid", cv="prefit")
    cal.fit(Xva, yva)
    brier_cal = brier_score_loss(yva, cal.predict_proba(Xva)[:, 1])
    calibrated = bool(brier_cal < brier_raw)
    final = cal if calibrated else best
    pt = final.predict_proba(Xte)[:, 1]
    m_valid = compute_metrics(yva.tolist(), [float(x) for x in
                             (cal.predict_proba(Xva)[:, 1] if calibrated else pv)])
    m_test = compute_metrics(yte.tolist(), [float(x) for x in pt])
    os.makedirs(out_dir, exist_ok=True)
    import joblib
    joblib.dump({"model": final, "version": version, "features": feats,
                 "calibrated": calibrated, "params": best_cfg}, os.path.join(out_dir, "fishing_xgb.joblib"))
    try:
        base = best.get_booster()
        base.save_model(os.path.join(out_dir, "fishing_xgb_booster.json"))
    except Exception:
        pass
    with open(os.path.join(out_dir, "features.json"), "w") as f:
        json.dump(feats, f, indent=2)
    shap_info = shap_or_gain(best, Xtr, feats)
    with open(os.path.join(out_dir, "shap_importance.json"), "w") as f:
        json.dump(shap_info, f, indent=2)
    meta = {"model": "fishing_suitability", "version": version, "estimator": "XGBClassifier",
            "training_period": train_period, "validation_period": valid_period,
            "test_period": test_period, "feature_list": feats,
            "target_definition": "0=unsuitable,1=potentially suitable (INCOIS PFZ-derived)",
            "class_balance": {"neg": neg, "pos": pos, "scale_pos_weight": round(float(pw), 3)},
            "best_params": best_cfg, "calibrated": calibrated,
            "metrics_valid": m_valid, "metrics_test": m_test,
            "dataset_version": "fishing_training v1", "training_timestamp": datetime.utcnow().isoformat()}
    with open(os.path.join(out_dir, "metadata.json"), "w") as f:
        json.dump(meta, f, indent=2)
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", required=True); ap.add_argument("--valid", required=True)
    ap.add_argument("--test", required=True); ap.add_argument("--version", default="v1")
    ap.add_argument("--out", default="models/fishing")
    a = ap.parse_args()
    print(json.dumps({k: v for k, v in run(a.train, a.valid, a.test, a.version, a.out).items()
                      if k in ("version", "best_params", "calibrated", "metrics_test")}, indent=2))


if __name__ == "__main__":
    main()
