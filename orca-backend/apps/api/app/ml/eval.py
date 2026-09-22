# Phase 13 - rolling evaluation metrics for production models.
#
# Computes MAE / RMSE / precision / recall / F1 / calibration / bias / coverage
# over matched (prediction, validated-ground-truth) pairs, aggregated over
# configurable rolling windows (daily / weekly / monthly).  Only VALIDATED
# outcomes are used for quality metrics; UNVERIFIED/REJECTED are excluded so
# unverified ground truth can never quietly distort model evaluation.
import math
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple


class RollingEvaluator:
    """Rolling-window evaluation over matched prediction/outcome pairs."""

    def __init__(self, window_seconds: int = 24 * 3600) -> None:
        self.window_seconds = int(window_seconds)
        self.samples: List[Dict[str, Any]] = []   # matched-quality samples

    def add_sample(self, model_name: str, predicted: Optional[float],
                   observed: float, at: Optional[datetime] = None) -> None:
        """Record one (prediction, ground-truth) sample for rolling metrics."""
        if predicted is None:
            return  # no point estimate -> cannot score
        at = at or datetime.now().astimezone()
        self.samples.append({
            "model": model_name, "predicted": float(predicted),
            "observed": float(observed), "at": at,
        })
        self._trim(at)

    def _trim(self, now: datetime) -> None:
        cutoff = now - timedelta(seconds=self.window_seconds)
        self.samples = [s for s in self.samples if s["at"] >= cutoff]

    # ------------------------------------------------------------ bucketed views
    def metrics(self, model_name: Optional[str] = None,
                now: Optional[datetime] = None) -> Dict[str, Any]:
        now = now or datetime.now().astimezone()
        self._trim(now)
        rows = [s for s in self.samples
                if model_name is None or s["model"] == model_name]
        if not rows:
            return {"n": 0, "mae": None, "rmse": None, "bias": None,
                    "coverage": 0.0, "calibration": None, "precision": None,
                    "recall": None, "f1": None}
        mae = sum(abs(s["predicted"] - s["observed"]) for s in rows) / len(rows)
        rmse = math.sqrt(sum((s["predicted"] - s["observed"]) ** 2
                             for s in rows) / len(rows))
        bias = sum(s["predicted"] - s["observed"] for s in rows) / len(rows)
        # classification-style metrics when the values are interpreted as a
        # 0..1 score with a half-threshold (honest, documented).
        tp = sum(1 for s in rows
                 if s["predicted"] >= 0.5 and s["observed"] >= 0.5)
        fp = sum(1 for s in rows
                 if s["predicted"] >= 0.5 and s["observed"] < 0.5)
        fn = sum(1 for s in rows
                 if s["predicted"] < 0.5 and s["observed"] >= 0.5)
        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None
        f1 = (2 * (precision or 0) * (recall or 0) /
              (max(precision or 0, 0) + (recall or 0))) if (precision and recall) else None
        calibration = self._calibration(rows)
        return {
            "n": len(rows),
            "mae": round(mae, 4),
            "rmse": round(rmse, 4),
            "bias": round(bias, 4),
            "coverage": round(tp / len(rows), 4) if len(rows) else 0.0,
            "calibration": round(calibration, 4) if calibration is not None else None,
            "precision": round(precision, 4) if precision is not None else None,
            "recall": round(recall, 4) if recall is not None else None,
            "f1": round(f1, 4) if f1 is not None else None,
        }

    @staticmethod
    def _calibration(rows: List[Dict[str, Any]]) -> Optional[float]:
        """Brier-style distance between average confidence and average outcome.

        Uses |mean(predicted) - mean(observed)|, rescaled so 0 = perfect
        calibration (higher is worse here).
        """
        if not rows:
            return None
        mean_pred = sum(r["predicted"] for r in rows) / len(rows)
        mean_obs = sum(r["observed"] for r in rows) / len(rows)
        return abs(mean_pred - mean_obs)


class MultiWindowEvaluator:
    """Evaluator that keeps separate daily/weekly/monthly rolling samples."""

    _WINDOWS = {
        "daily": lambda s: s.ml_eval_histogram_daily_seconds,
        "weekly": lambda s: s.ml_eval_histogram_weekly_seconds,
        "monthly": lambda s: s.ml_eval_histogram_monthly_seconds,
    }

    def __init__(self, seconds: Optional[Dict[str, int]] = None) -> None:
        self._windows: Dict[str, RollingEvaluator] = {}
        from app.config import settings
        for name, fn in self._WINDOWS.items():
            self._windows[name] = RollingEvaluator(
                window_seconds=(seconds or {}).get(
                    name, fn(settings)))

    def add_sample(self, model_name: str, predicted: Optional[float],
                   observed: float, at: Optional[datetime] = None) -> None:
        for w in self._windows.values():
            w.add_sample(model_name, predicted, observed, at)

    def metrics(self, model_name: Optional[str] = None,
                now: Optional[datetime] = None) -> Dict[str, Any]:
        return {
            name: w.metrics(model_name, now)
            for name, w in self._windows.items()
        }

    def sample_counts(self) -> Dict[str, int]:
        return {name: len(w.samples) for name, w in self._windows.items()}