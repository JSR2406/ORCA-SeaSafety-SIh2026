"""Phase 7 production: Marine Risk XGBoost. Same recipe as fishing (tuning,
early stopping, calibration, SHAP/gain, registry artifacts).

Outputs probability only — thresholds are validated, not universal; the
Deterministic Risk Engine owns the safety verdict.

Usage:
    python -m ml.risk.train_production --train ml/data/processed/risk_training_train.parquet \\
        --valid ml/data/processed/risk_training_valid.parquet \\
        --test ml/data/processed/risk_training_test.parquet --version v1
"""
import argparse, json, os
from datetime import datetime


def _load(path):
    import pandas as pd
    try:
        return pd.read_parquet(path)
    except Exception:
        return pd.read_csv(path)


def run(train_p, valid_p, test_p, version="v1", out_dir="models/risk", target="target",
        train_period="2019-2023", valid_period="2024", test_period="2025"):
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.metrics import average_precision_score, brier_score_loss
    from ml.common.schemas import RISK_FEATURES
    from ml.fishing.train_production import train_one, shap_or_gain
    from ml.fishing.evaluate import compute_metrics
    tr, va, te = _load(train_p), _load(valid_p), _load(test_p)
    feats = [f for f in RISK_FEATURES if f in tr.columns]
    Xtr, ytr = tr[feats].fillna(0).values, tr[target].astype(int).values
    Xva, yva = va[feats].fillna(0).values, va[target].astype(int).values
    Xte, yte = te[feats].fillna(0).values, te[target].astype(int).values
    neg, pos = int((ytr == 0).sum()), int((ytr == 1).sum())
    pw = neg / max(pos, 1)
    best, best_auc, best_cfg = None, -1, {}
    for depth in (3, 5):
        for lr in (0.05, 0.1):
            m = train_one(Xtr, ytr, Xva, yva, depth, lr, pw if pos and neg / pos > 1.5 else 1.0)
            auc = average_precision_score(yva, m.predict_proba(Xva)[:, 1])
            if auc > best_auc:
                best, best_auc, best_cfg = m, auc, {"max_depth": depth, "learning_rate": lr}
    pv = best.predict_proba(Xva)[:, 1]
    cal = CalibratedClassifierCV(best, method="sigmoid", cv="prefit")
    cal.fit(Xva, yva)
    calibrated = bool(brier_score_loss(yva, cal.predict_proba(Xva)[:, 1]) < brier_score_loss(yva, pv))
    final = cal if calibrated else best
    m_valid = compute_metrics(yva.tolist(), [float(x) for x in final.predict_proba(Xva)[:, 1]])
    m_test = compute_metrics(yte.tolist(), [float(x) for x in final.predict_proba(Xte)[:, 1]])
    os.makedirs(out_dir, exist_ok=True)
    import joblib
    joblib.dump({"model": final, "version": version, "features": feats,
                 "calibrated": calibrated, "params": best_cfg},
                os.path.join(out_dir, "risk_xgb.joblib"))
    try:
        best.get_booster().save_model(os.path.join(out_dir, "risk_xgb_booster.json"))
    except Exception:
        pass
    with open(os.path.join(out_dir, "features.json"), "w") as f:
        json.dump(feats, f, indent=2)
    with open(os.path.join(out_dir, "shap_importance.json"), "w") as f:
        json.dump(shap_or_gain(best, Xtr, feats), f, indent=2)
    meta = {"model": "marine_risk", "version": version, "estimator": "XGBClassifier",
            "training_period": train_period, "validation_period": valid_period,
            "test_period": test_period, "feature_list": feats,
            "target_definition": "0=low-risk,1=high-risk (demo rule; replace with incident history)",
            "class_balance": {"neg": neg, "pos": pos},
            "best_params": best_cfg, "calibrated": calibrated,
            "metrics_valid": m_valid, "metrics_test": m_test,
            "training_timestamp": datetime.utcnow().isoformat(),
            "safety_note": "probability only; verdict owned by Deterministic Risk Engine"}
    with open(os.path.join(out_dir, "metadata.json"), "w") as f:
        json.dump(meta, f, indent=2)
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", required=True); ap.add_argument("--valid", required=True)
    ap.add_argument("--test", required=True); ap.add_argument("--version", default="v1")
    ap.add_argument("--out", default="models/risk")
    a = ap.parse_args()
    print(json.dumps({k: v for k, v in run(a.train, a.valid, a.test, a.version, a.out).items()
                      if k in ("version", "best_params", "calibrated", "metrics_test")}, indent=2))


if __name__ == "__main__":
    main()
