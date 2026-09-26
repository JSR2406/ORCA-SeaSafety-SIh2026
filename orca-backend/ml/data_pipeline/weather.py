"""Open-Meteo Marine + Forecast API — DEVELOPMENT/FALLBACK ONLY, always labeled OPEN_METEO.

Coastal accuracy limited; never present as authoritative safety source.
Docs: https://open-meteo.com/en/docs/marine-weather-api
Note: timezone must be 'Asia/Kolkata' (slash); 'Asia_Kolkata' is rejected (HTTP 400).
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from ml.data_pipeline.base import AdapterError, fetch_json, normalized_record, validate_latlon

MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TZ = "Asia/Kolkata"
MS_PER_KMH = 1.0 / 3.6


def _nearest(times: List[str], target: datetime) -> int:
    best, best_dt = 0, None
    for i, t in enumerate(times):
        try:
            dt = datetime.fromisoformat(t)
        except ValueError:
            continue
        if best_dt is None or abs((dt - target).total_seconds()) < abs((best_dt - target).total_seconds()):
            best, best_dt = i, dt
    return best


def _at(hourly: Dict[str, List], key: str, i: int) -> Optional[float]:
    vals = hourly.get(key) or []
    if i < len(vals):
        try:
            return float(vals[i]) if vals[i] is not None else None
        except (TypeError, ValueError):
            return None
    return None


def fetch_marine_fallback(lat: float, lon: float, valid_time: datetime,
                          timeout_s: float = 8.0) -> Dict[str, Any]:
    """Marine swell/SST/currents + forecast-API wind/rain/visibility, merged + labeled."""
    validate_latlon(lat, lon)
    try:
        m = fetch_json(MARINE_URL, {"latitude": lat, "longitude": lon,
                                    "hourly": "wave_height,wave_direction,wave_period,"
                                              "ocean_current_velocity,ocean_current_direction,"
                                              "sea_surface_temperature",
                                    "timezone": TZ}, timeout_s=timeout_s)
        w = fetch_json(FORECAST_URL, {"latitude": lat, "longitude": lon,
                                      "hourly": "wind_speed_10m,wind_direction_10m,"
                                                "precipitation,visibility",
                                      "current": "wind_speed_10m,wind_direction_10m",
                                      "timezone": TZ, "wind_speed_unit": "ms"},
                       timeout_s=timeout_s)
        mh, wh = m["data"].get("hourly", {}), w["data"].get("hourly", {})
        if not mh.get("time"):
            raise AdapterError("marine API returned no hourly rows")
        i = _nearest(mh["time"], valid_time)
        j = _nearest(wh["time"], valid_time) if wh.get("time") else 0
        cur = w["data"].get("current", {})
        payload = {
            "matched_time": mh["time"][i],
            "wave_height_m": _at(mh, "wave_height", i),
            "wave_period_s": _at(mh, "wave_period", i),
            "wave_direction_deg": _at(mh, "wave_direction", i),
            "sst_c": _at(mh, "sea_surface_temperature", i),
            "current_speed_ms": _at(mh, "ocean_current_velocity", i),
            "current_direction_deg": _at(mh, "ocean_current_direction", i),
            "wind_speed_ms": _at(wh, "wind_speed_10m", j),
            "wind_direction_deg": _at(wh, "wind_direction_10m", j),
            "rain_mm": _at(wh, "precipitation", j),
            "visibility_km": (lambda v: v / 1000.0 if v is not None else None)(
                _at(wh, "visibility", j)),
            "wind_now_ms": (lambda v: float(v) if v is not None else None)(
                cur.get("wind_speed_10m")),
        }
        return normalized_record(lat, lon, valid_time, "OPEN_METEO", payload)
    except AdapterError as e:
        return normalized_record(lat, lon, valid_time, "OPEN_METEO",
                                 {"status": "error", "note": str(e)}, quality="missing")
