"""IMD official warnings adapter (PRIMARY for cyclone/weather alerts — never ML-predicted).

Env: IMD_API_BASE, IMD_API_KEY (optional; unset → quality=missing record, never fake SAFE).
"""
import os
from datetime import datetime
from typing import Any, Dict
from ml.data_pipeline.base import AdapterError, fetch_json, normalized_record, validate_latlon


def _parse_warnings(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        warnings = raw.get("warnings", raw.get("alerts", []))
        return {"warning_count": len(warnings) if isinstance(warnings, list) else 0,
                "active": bool(warnings), "raw": raw}
    return {"warning_count": 0, "active": False, "raw": raw}


def fetch_warnings(lat: float, lon: float, valid_time: datetime,
                   timeout_s: float = 8.0) -> Dict[str, Any]:
    validate_latlon(lat, lon)
    base = os.getenv("IMD_API_BASE", "").rstrip("/")
    if not base:
        return normalized_record(lat, lon, valid_time, "IMD",
                                 {"status": "unconfigured", "note": "set IMD_API_BASE",
                                  "active": None},
                                 quality="missing")
    headers = {}
    if os.getenv("IMD_API_KEY"):
        headers["Authorization"] = f"Bearer {os.environ['IMD_API_KEY']}"
    try:
        out = fetch_json(f"{base}/warnings", {"lat": lat, "lon": lon},
                         timeout_s=timeout_s, headers=headers or None)
        return normalized_record(lat, lon, valid_time, "IMD", _parse_warnings(out["data"]))
    except AdapterError as e:
        return normalized_record(lat, lon, valid_time, "IMD",
                                 {"status": "error", "note": str(e), "active": None},
                                 quality="missing")
