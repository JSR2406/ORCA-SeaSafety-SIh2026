"""Anomaly detection stub (Isolation Forest). Flags unusual marine states; never a verdict alone."""
from typing import List
ANOMALY_FEATURES: List[str] = ["sst_c", "chlorophyll", "wave_height_m", "wind_speed_ms", "current_speed_ms"]


def isolation_forest_note() -> str:
    return "Train sklearn.ensemble.IsolationForest on historical features; store contamination + version in metadata."
