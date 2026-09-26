"""Phase 3 gateway: single entry for live features.

Hierarchy: INCOIS (ocean) + IMD (warnings) primary; Open-Meteo fallback ONLY when
primary is missing AND allow_fallback=True. Every field records its source.
Never silently substitutes — caller sees exactly what fed the model.
"""
from datetime import datetime
from typing import Any, Dict, List
import time

_FEAT_CACHE: Dict[str, Any] = {}
FEAT_TTL_S = 900.0  # demo grids refresh daily; 15-min cache cuts repeat latency


def get_marine_features(lat: float, lon: float, valid_time: datetime,
                        allow_fallback: bool = True) -> Dict[str, Any]:
    from ml.data_pipeline.incois import fetch_ocean_state
    from ml.data_pipeline.imd import fetch_warnings

    key = f"{round(lat, 2)},{round(lon, 2)},{allow_fallback}"
    hit = _FEAT_CACHE.get(key)
    if hit and time.time() - hit[0] < FEAT_TTL_S:
        out = dict(hit[1])
        out["records"] = []
        return out

    records: List[Dict[str, Any]] = []
    merged: Dict[str, Any] = {"lat": lat, "lon": lon, "valid_time": valid_time.isoformat()}

    oc = fetch_ocean_state(lat, lon, valid_time)
    records.append(oc)
    for k in ("sst_c", "chlorophyll", "wave_height_m", "wave_period_s", "wind_speed_ms",
              "wind_direction_deg", "current_speed_ms", "current_direction_deg"):
        if oc.get(k) is not None:
            merged[k] = oc[k]
            merged[f"{k}__source"] = "INCOIS"

    # Tier 1b: INCOIS THREDDS forecast grids (authoritative, keyless NCSS).
    # Fills whatever the JSON API adapter missed; labeled INCOIS-THREDDS.
    missing = [k for k in ("wave_height_m", "wave_period_s", "sst_c",
                           "wind_speed_ms", "wind_direction_deg")
               if merged.get(k) is None]
    if missing:
        try:
            from ml.data_pipeline.scrapers.incois_thredds import extract_point
            th = extract_point(lat, lon, timeout_s=8.0)
            records.append({"source": "INCOIS-THREDDS", "quality": th.get("quality"),
                            "retrieval_time": th.get("retrieval_time")})
            for k in missing:
                if th.get(k) is not None:
                    merged[k] = th[k]
                    merged[f"{k}__source"] = "INCOIS-THREDDS"
        except Exception as e:
            records.append({"source": "INCOIS-THREDDS", "quality": "missing",
                            "note": str(e)[:150]})

    # Fallback fills ONLY gaps, labeled OPEN_METEO
    missing = [k for k in ("wave_height_m", "wave_period_s", "sst_c", "current_speed_ms",
                           "current_direction_deg", "wind_speed_ms", "wind_direction_deg",
                           "visibility_km", "rain_mm")
               if merged.get(k) is None]
    if missing and allow_fallback:
        from ml.data_pipeline.weather import fetch_marine_fallback
        fb = fetch_marine_fallback(lat, lon, valid_time)
        records.append(fb)
        for k in missing:
            if fb.get(k) is not None:
                merged[k] = fb[k]
                merged[f"{k}__source"] = "OPEN_METEO"
    elif missing:
        merged["_fallback_skipped"] = missing

    w = fetch_warnings(lat, lon, valid_time)
    records.append(w)
    merged["official_warning_active"] = w.get("active")
    merged["official_warning__source"] = "IMD"

    merged["records"] = records
    merged["freshness"] = "live" if any(r.get("quality") == "ok" for r in records) else "stale"
    _FEAT_CACHE[key] = (time.time(), {k: v for k, v in merged.items() if k != "records"})
    return merged
