"""Evaluation: ROC-AUC, PR-AUC, F1, precision, recall, Brier, calibration, confusion matrix."""
from typing import Any, Dict, List
import numpy as np
from ml.common.metrics import REQUIRED_METRICS, empty_report

__all__ = ["REQUIRED_METRICS", "empty_report", "compute_metrics"]


def compute_metrics(y_true: List[int], y_proba: List[float]) -> Dict[str, Any]:
    from sklearn.metrics import (average_precision_score, brier_score_loss, confusion_matrix,
                                 f1_score, precision_score, recall_score, roc_auc_score)
    yt = np.array(y_true, dtype=int)
    yp = np.array(y_proba, dtype=float)
    pred = (yp >= 0.5).astype(int)
    # calibration: 5-bin mean predicted vs observed
    bins, cal = [], []
    for lo, hi in ((0, .2), (.2, .4), (.4, .6), (.6, .8), (.8, 1.01)):
        m = (yp >= lo) & (yp < hi)
        if m.any():
            bins.append({"bin": [lo, hi], "mean_pred": round(float(yp[m].mean()), 3),
                         "mean_obs": round(float(yt[m].mean()), 3), "n": int(m.sum())})
    return {
        "roc_auc": round(float(roc_auc_score(yt, yp)) if len(set(yt)) > 1 else 0.5, 4),
        "pr_auc": round(float(average_precision_score(yt, yp)) if len(set(yt)) > 1 else 0.0, 4),
        "f1": round(float(f1_score(yt, pred, zero_division=0)), 4),
        "precision": round(float(precision_score(yt, pred, zero_division=0)), 4),
        "recall": round(float(recall_score(yt, pred, zero_division=0)), 4),
        "brier": round(float(brier_score_loss(yt, yp)), 4),
        "confusion_matrix": confusion_matrix(yt, pred).tolist(),
        "calibration": bins,
    }
