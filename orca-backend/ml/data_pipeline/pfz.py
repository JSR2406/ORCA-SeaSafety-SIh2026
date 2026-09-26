"""INCOIS PFZ adapter — advisory-derived LABELS for the fishing dataset.

PFZ advisory gives lat/lon/depth/distance/sector. Labels:
  1 = inside/near advised PFZ polygon (potentially suitable)
  0 = background sample (see dataset.py for careful negative sampling)
Secondary context: Global Fishing Watch activity (optional, never ground truth).
"""
from datetime import datetime
from typing import Any, Dict, List
from ml.data_pipeline.base import normalized_record, validate_latlon


def pfz_record(lat: float, lon: float, valid_time: datetime, suitable: int,
               source: str = "INCOIS", extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    assert suitable in (0, 1), "binary first: 0=unsuitable, 1=potentially suitable"
    validate_latlon(lat, lon)
    payload: Dict[str, Any] = {"pfz_label": suitable}
    if extra:
        payload.update(extra)
    return normalized_record(lat, lon, valid_time, source, payload)


def batch_pfz(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate a batch of pre-fetched advisory rows (dicts with lat/lon/valid_time/suitable)."""
    out = []
    for r in records:
        out.append(pfz_record(r["lat"], r["lon"], r["valid_time"], r["suitable"],
                              r.get("source", "INCOIS"), r.get("extra")))
    return out
