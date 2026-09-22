# Phase 12 - drift detection for model inputs and predictions.
#
# Uses the Population Stability Index (PSI) approximation between a reference
# distribution (last N samples) and a candidate batch.  PSI > threshold raises
# a drift alarm.  Drift never blocks a prediction it fails to verify; it is an
# observable signal that a model may be operating out of distribution.
#
# Bounded: only the last `warmup` samples are retained per signal.
import math
from statistics import fmean
from typing import Any, Dict, List, Optional


class DriftDetector:
    """Bounded per-signal drift detector (PSI)."""

    def __init__(self, threshold: float = 0.30, warmup: int = 50) -> None:
        self.threshold = float(threshold)
        self.warmup = int(warmup)
        self.samples: Dict[str, List[float]] = {}
        self.last_psi: Dict[str, Optional[float]] = {}
        self.alarms: List[Dict[str, Any]] = []

    def record(self, signal: str, value: float) -> Optional[float]:
        """Ingest a value for a signal; returns PSI when a drift check armed."""
        bucket = self.samples.setdefault(signal, [])
        bucket.append(float(value))
        if len(bucket) > self.warmup * 3:
            diff = len(self.warmup * 3)
            bucket = bucket[-diff:]
            self.samples[signal] = bucket
        if len(bucket) < self.warmup:
            return None
        # keep only the warmup window for both reference & candidate
        window = bucket[-self.warmup:]
        reference = self.samples[signal][-self.warmup * 2:-self.warmup] \
            if len(bucket) >= self.warmup * 2 else None
        if not reference:
            return None
        psi = self._psi(reference, window)
        self.last_psi[signal] = psi
        if psi > self.threshold:
            self.alarms.append({"signal": signal, "psi": round(psi, 3),
                                "threshold": self.threshold})
            self.alarms = self.alarms[-20:]  # bounded alarm log
        return psi

    @staticmethod
    def _psi(reference: List[float], candidate: List[float]) -> float:
        ref = _bins(reference)
        cand = _bins(candidate)
        if ref["count"] == 0 or cand["count"] == 0:
            return 0.0
        total = 0.0
        for lo, hi in zip(ref["edges"], ref["edges"][1:]):
            r = ref["counts"].get((lo, hi), 0) / ref["count"]
            c = cand["counts"].get((lo, hi), 0) / cand["count"]
            # clamp ratio to avoid log(0) blowup
            r = max(r, 1e-4)
            c = max(c, 1e-4)
            total += (c - r) * math.log(c / r)
        return total

    def status(self) -> Dict[str, Any]:
        return {
            "warmup": self.warmup,
            "threshold": self.threshold,
            "signals": {k: (round(v, 3) if v is not None else None)
                        for k, v in self.last_psi.items()},
            "alarm_count": len(self.alarms),
            "recent_alarms": self.alarms[-5:],
        }


def _bins(values: List[float]) -> Dict[str, Any]:
    """10 uniform bins over [min, max] of values."""
    if not values:
        return {"count": 0, "edges": [], "counts": {}}
    lo, hi = min(values), max(values)
    if abs(hi - lo) < 1e-9:
        edges = [lo] * 11
    else:
        edges = [lo + (hi - lo) * k / 10.0 for k in range(11)]
    counts: Dict[tuple, int] = {}
    for v in values:
        for k in range(10):
            if edges[k] <= v <= edges[k + 1]:
                key = (edges[k], edges[k + 1])
                counts[key] = counts.get(key, 0) + 1
                break
    return {"count": len(values), "edges": edges, "counts": counts}


_drift: Optional[DriftDetector] = None


def get_drift_detector() -> DriftDetector:
    global _drift
    if _drift is None:
        from app.config import settings
        _drift = DriftDetector(threshold=settings.ml_drift_threshold,
                               warmup=settings.ml_drift_warmup_samples)
    return _drift