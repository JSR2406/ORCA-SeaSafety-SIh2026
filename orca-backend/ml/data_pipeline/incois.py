"""INCOIS Ocean State Forecast adapter (PRIMARY, authoritative for Indian waters).

Env: INCOIS_BASE_URL (optional; when unset returns quality=missing, never fake data).
Parses wind/currents/waves/SST into normalized ocean variables.
"""
import os
from datetime import datetime
from typing import Any, Dict
from ml.data_pipeline.base import AdapterError, fetch_json, normalized_record, validate_latlon


def _parse_osf(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Map provider fields → normalized vars. Unknown shapes pass through as raw."""
    out: Dict[str, Any] = {}
    mapping = {"sst": "sst_c", "SST": "sst_c", "wave_height": "wave_height_m",
               "waveHeight": "wave_height_m", "wave_period": "wave_period_s",
               "wind_speed": "wind_speed_ms", "windSpeed": "wind_speed_ms",
               "wind_dir": "wind_direction_deg", "current_speed": "current_speed_ms",
               "current_dir": "current_direction_deg", "chlorophyll": "chlorophyll"}
    if isinstance(raw, dict):
        for k, v in raw.items():
            if k in mapping:
                out[mapping[k]] = v
    out["_raw_keys"] = sorted(raw.keys()) if isinstance(raw, dict) else []
    return out


def fetch_ocean_state(lat: float, lon: float, valid_time: datetime,
                      timeout_s: float = 8.0) -> Dict[str, Any]:
    validate_latlon(lat, lon)
    base = os.getenv("INCOIS_BASE_URL", "").rstrip("/")
    if not base:
        return normalized_record(lat, lon, valid_time, "INCOIS",
                                 {"status": "unconfigured", "note": "set INCOIS_BASE_URL"},
                                 quality="missing")
    try:
        out = fetch_json(f"{base}/forecast", {"lat": lat, "lon": lon}, timeout_s=timeout_s)
        parsed = _parse_osf(out["data"] if isinstance(out["data"], dict) else {})
        parsed["raw"] = out["data"]
        return normalized_record(lat, lon, valid_time, "INCOIS", parsed)
    except AdapterError as e:
        return normalized_record(lat, lon, valid_time, "INCOIS",
                                 {"status": "error", "note": str(e)}, quality="missing")
