"""Phase 4a collect: PFZ labels + gateway features → raw rows.

FEATURE TIME <= LABEL TIME always (no future leakage).
"""
from datetime import datetime
from typing import Any, Dict, List


def collect_row(lat: float, lon: float, valid_time: datetime, suitable: int,
                allow_fallback: bool = True) -> Dict[str, Any]:
    from ml.data_pipeline.gateway import get_marine_features
    feats = get_marine_features(lat, lon, valid_time, allow_fallback=allow_fallback)
    records = feats.pop("records")
    row = {**feats, "target": suitable, "label__source": "INCOIS-PFZ",
           "feature_time": valid_time.isoformat()}
    row["_provenance"] = [(r.get("source"), r.get("quality")) for r in records]
    return row


def collect_batch(items: List[Dict[str, Any]], allow_fallback: bool = True) -> List[Dict[str, Any]]:
    return [collect_row(i["lat"], i["lon"], i["valid_time"], i["suitable"], allow_fallback)
            for i in items]
