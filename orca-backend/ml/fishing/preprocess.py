"""Phase 4b preprocess: clean → normalize → align → dedup.

- Drops rows with missing sst_c AND chlorophyll (both core PFZ signals gone).
- Fills other gaps with median-of-batch + flags _imputed.
- Rounds coords to ~1km (3 decimals) for spatial matching stability.
- Sorts by valid_time; drops exact (lat,lon,time) duplicates.
"""
from typing import Any, Dict, List


def preprocess(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen, out = set(), []
    for r in rows:
        if r.get("sst_c") is None and r.get("chlorophyll") is None:
            continue
        r["lat"] = round(float(r["lat"]), 3)
        r["lon"] = round(float(r["lon"]), 3)
        key = (r["lat"], r["lon"], r.get("valid_time"))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    # median impute numeric gaps
    nums = ("sst_c", "chlorophyll", "wave_height_m", "wind_speed_ms", "current_speed_ms")
    medians = {}
    for k in nums:
        vals = sorted(float(r[k]) for r in out if r.get(k) is not None)
        medians[k] = vals[len(vals) // 2] if vals else 0.0
    for r in out:
        for k in nums:
            if r.get(k) is None:
                r[k] = medians[k]
                r.setdefault("_imputed", []).append(k)
    out.sort(key=lambda r: r.get("valid_time", ""))
    return out
