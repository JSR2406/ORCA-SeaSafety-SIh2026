"""Adapter contract: timeout + retry + validate + normalize + source/freshness labels.

Hierarchy: INCOIS/IMD (primary, authoritative) > Open-Meteo (dev fallback, always labeled).
Never silently substitute fallback data — every record states its source.
"""
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
import httpx


class AdapterError(RuntimeError):
    pass


class AdapterConfig:
    def __init__(self, timeout_s: float = 8.0, retries: int = 2):
        self.timeout_s = timeout_s
        self.retries = retries


def validate_latlon(lat: float, lon: float) -> None:
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise AdapterError(f"invalid lat/lon: {lat},{lon}")


RANGES: Dict[str, tuple] = {
    "sst_c": (-2.0, 38.0), "chlorophyll": (0.0, 30.0),
    "wave_height_m": (0.0, 20.0), "wave_period_s": (0.0, 30.0),
    "wind_speed_ms": (0.0, 80.0), "current_speed_ms": (0.0, 5.0),
    "visibility_km": (0.0, 50.0), "rain_mm": (0.0, 500.0),
}


def validate_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Clamp out-of-range values to None + mark suspect; never invent data."""
    issues: List[str] = []
    for k, (lo, hi) in RANGES.items():
        v = payload.get(k)
        if v is None:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            payload[k] = None
            issues.append(f"{k}:non-numeric")
            continue
        if not (lo <= f <= hi):
            payload[k] = None
            issues.append(f"{k}:out-of-range({f})")
    payload["_validation_issues"] = issues
    return payload


def fetch_json(url: str, params: Optional[Dict[str, Any]] = None,
               timeout_s: float = 8.0, retries: int = 2,
               headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    last: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            r = httpx.get(url, params=params, timeout=timeout_s, headers=headers)
            r.raise_for_status()
            return {"data": r.json(), "retrieval_time": datetime.utcnow().isoformat(),
                    "attempt": attempt + 1}
        except Exception as e:
            last = e
            time.sleep(0.5 * (attempt + 1))
    raise AdapterError(f"fetch failed after {retries + 1} attempts: {url}: {last}")


def normalized_record(lat: float, lon: float, valid_time: datetime, source: str,
                      payload: Dict[str, Any], quality: str = "ok") -> Dict[str, Any]:
    validate_latlon(lat, lon)
    payload = validate_response(dict(payload))
    if payload.pop("_validation_issues", []):
        quality = "suspect" if quality == "ok" else quality
    return {"lat": lat, "lon": lon, "valid_time": valid_time.isoformat(),
            "retrieval_time": datetime.utcnow().isoformat(), "source": source,
            "quality": quality, **payload}
