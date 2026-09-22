# Phase 12 - feature pipeline, feature store and versioning.
#
# The feature store turns raw marine observations into bounded, versioned
# feature rows consumed by the production models.  It is:
#   * versioned - every row records the feature-pipeline version that produced it;
#   * bounded - rows are retained for a configured horizon (never an unbounded cache);
#   * deterministic - the same raw inputs always produce the same features;
#   * honest - features are only produced from *present* inputs, never imputed
#     with fabricated values (a model may flag uncertainty, not invent data).
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)

FEATURES_V1 = "1.0.0"  # current feature-pipeline version


def _utcnow() -> datetime:
    return datetime.now(timezone_utc())


def timezone_utc():
    from datetime import timezone
    return timezone.utc


# Normalization bounds used so OOV/outlier inputs are still scaled consistently.
_NORM = {
    "sst_c": (-2.0, 32.0),
    "chlorophyll": (0.0, 3.0),
    "wave_height_m": (0.0, 8.0),
    "wind_speed_ms": (0.0, 30.0),
    "current_speed_ms": (0.0, 3.0),
    "visibility_m": (0.0, 20000.0),
}


def _safe_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class FeatureRow:
    """One versioned feature row produced from a fused marine state."""
    key: str                      # stable location+time identity (hash)
    version: str
    features: Dict[str, Optional[float]]
    present: List[str]            # which features were actually observed
    missing: List[str]            # which features were absent
    raw: Dict[str, Any]           # raw observed values handed through
    produced_at: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "version": self.version,
            "features": self.features,
            "present": self.present,
            "missing": self.missing,
            "raw": self.raw,
            "produced_at": self.produced_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeatureRow":
        return cls(
            key=data["key"],
            version=data.get("version", FEATURES_V1),
            features=data.get("features") or {},
            present=data.get("present") or [],
            missing=data.get("missing") or [],
            raw=data.get("raw") or {},
            produced_at=datetime.fromisoformat(data["produced_at"]),
        )


class FeatureStore:
    """Bounded, versioned feature store.  Deterministic extraction."""

    def __init__(self, version: str = FEATURES_V1,
                 retention_hours: int = 24) -> None:
        self.version = version
        self.retention = timedelta(hours=retention_hours)
        self.rows: Dict[str, FeatureRow] = {}
        self.orders: List[str] = []  # insertion order for LRU-style eviction

    # ------------------------------------------------------------- extraction
    @classmethod
    def extract(cls, state) -> dict:
        """Deterministically map a fused marine state to normalized features.

        Returns a dict of present features + missing list.  Missing inputs are
        left None - a value is NEVER invented.
        """
        raw = {}
        if hasattr(state, "variables"):
            raw = getattr(state, "variables") or {}
        normalized: Dict[str, Optional[float]] = {}
        present: List[str] = []
        missing: List[str] = []
        for var, (lo, hi) in _NORM.items():
            value = _safe_float(raw.get(var)) if isinstance(raw, dict) else None
            if value is None:
                missing.append(var)
                normalized[var] = None
                continue
            # min-max scale to 0..1 (clamped).  Deterministic per version.
            scale = (value - lo) / (hi - lo) if hi > lo else 0.0
            normalized[var] = round(max(0.0, min(1.0, scale)), 6)
            present.append(var)
        return {"normalized": normalized, "present": present, "missing": missing,
                "raw": {k: raw.get(k) for k in raw if isinstance(raw, dict)}}

    def put(self, key: str, state) -> Optional[FeatureRow]:
        """Store a versioned feature row for a fused state (bounded horizon)."""
        extraction = self.extract(state)
        row = FeatureRow(
            key=key,
            version=self.version,
            features=extraction["normalized"],
            present=extraction["present"],
            missing=extraction["missing"],
            raw=extraction["raw"],
        )
        if key in self.rows:
            self.orders.remove(key)
        self.rows[key] = row
        self.orders.append(key)
        self._evict_expired()
        self._evict_oldest()  # hard bound against unbounded growth
        return row

    def get(self, key: str) -> Optional[FeatureRow]:
        row = self.rows.get(key)
        if row is not None and _utcnow() - row.produced_at > self.retention:
            self.delete(key)
            return None
        return row

    def delete(self, key: str) -> None:
        self.rows.pop(key, None)
        if key in self.orders:
            self.orders.remove(key)

    def _evict_expired(self) -> None:
        cutoff = _utcnow() - self.retention
        for key in list(self.rows.keys()):
            if self.rows[key].produced_at < cutoff:
                self.delete(key)

    def _evict_oldest(self) -> None:
        # hard bound: never exceed 10x the expected retention window of items
        cap = int(self.retention.total_seconds()) + 1
        while len(self.rows) > cap and self.orders:
            self.delete(self.orders[0])

    def recent(self, limit: int = 100) -> List[FeatureRow]:
        rows = list(self.rows.values())
        rows.sort(key=lambda r: r.produced_at, reverse=True)
        return rows[:limit]

    def stats(self) -> Dict[str, Any]:
        present = 0
        for row in self.rows.values():
            present += len(row.present)
        return {
            "version": self.version,
            "rows": len(self.rows),
            "total_present_features": present,
            "retention_hours": round(self.retention.total_seconds() / 3600, 3),
        }

    # ------------------------------------------------------- state persistence
    def to_snapshot(self) -> Dict[str, Any]:
        """JSON-serializable feature-store state (insertion-ordered rows)."""
        return {
            "version": self.version,
            "rows": [self.rows[k].to_dict() for k in self.orders if k in self.rows],
        }

    @classmethod
    def from_snapshot(cls, snapshot: Dict[str, Any],
                      retention_hours: int = 24) -> "FeatureStore":
        """Reconstruct a feature store from a persisted snapshot."""
        store = cls(version=snapshot.get("version", FEATURES_V1),
                    retention_hours=retention_hours)
        for data in snapshot.get("rows") or []:
            try:
                row = FeatureRow.from_dict(data)
            except Exception:  # noqa: BLE001 - skip corrupt rows
                continue
            store.rows[row.key] = row
            store.orders.append(row.key)
        store._evict_expired()
        store._evict_oldest()
        return store

    def persist(self, path: Optional[str] = None) -> Optional[str]:
        """Write the feature-store snapshot to disk (best-effort)."""
        import json
        import os
        if path is None:
            from app.config import settings
            path = getattr(settings, "ml_feature_store_path", None)
        if not path:
            return None
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(self.to_snapshot(), fh, indent=2, default=str)
            return path
        except Exception:  # noqa: BLE001 - observability never fails the loop
            logger.warning("feature_store persist failed: %s", path)
            return None


_feature_store: Optional[FeatureStore] = None


def load_feature_store_state(path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Read a persisted feature-store snapshot (None if missing/corrupt)."""
    import json
    import os
    if path is None:
        from app.config import settings
        path = getattr(settings, "ml_feature_store_path", None)
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
            return None
        return data
    except Exception:  # noqa: BLE001 - corrupt state is ignored, never fatal
        logger.warning("feature_store load failed: %s", path)
        return None


def get_feature_store() -> FeatureStore:
    global _feature_store
    if _feature_store is None:
        from app.config import settings
        state = load_feature_store_state(settings.ml_feature_store_path)
        if state:
            _feature_store = FeatureStore.from_snapshot(
                state, retention_hours=settings.features_cache_hours)
        else:
            _feature_store = FeatureStore(
                version=FEATURES_V1,
                retention_hours=settings.features_cache_hours)
    return _feature_store