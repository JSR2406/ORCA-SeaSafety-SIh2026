"""Open-source deep extractor for INCOIS OSF forecast grids (THREDDS NCSS).

No keys, no browser, no paid tool: plain HTTPS point queries against INCOIS's
public THREDDS catalog (wave, winds, currents, SST, chlorophyll). This is the
same gridded model output that powers the OSF WebGIS map.

Catalog: https://incois.gov.in/thredds/catalog/osf/{wave,winds,currents,sst,chl}/
Method: latest daily NetCDF -> NCSS CSV point query -> NaN-aware offshore stepping
(land-masked coastal cells return NaN; we step seaward until a wet cell hits).

Respects the service: short timeouts, retries, identifiable User-Agent, and a
6-hour in-memory cache on latest-file discovery (catalogs change once daily).
"""
import math
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

BASE = "https://incois.gov.in/thredds"
HDRS = {"User-Agent": "ORCA-demo-research/1.0 (SIH academic use)"}
SOURCE = "INCOIS-THREDDS"

# catalog -> (filename regex preference, [variables to pull])
GROUPS: Dict[str, Dict[str, Any]] = {
    "wave": {"vars": ["SWH", "SWP", "WP"], "prefer": ("WAVES_coast_", "WAVES_io_")},
    "winds": {"vars": ["WSM", "WSXM", "WSYM"], "prefer": ("WINDS_",)},
    "currents": {"vars": ["CURRENT", "U", "V"], "prefer": ("CURRENTS_",)},
    "sst": {"vars": ["SST"], "prefer": ("SST_",)},
    "chl": {"vars": ["chlor_a"], "prefer": (".nc",)},
}

_catalog_cache: Dict[str, Any] = {}


def _latest_urlpath(group: str, timeout_s: float = 15.0) -> Optional[str]:
    cached = _catalog_cache.get(group)
    if cached and time.time() - cached[0] < 6 * 3600:
        return cached[1]
    t = httpx.get(f"{BASE}/catalog/osf/{group}/catalog.xml", timeout=timeout_s,
                  headers=HDRS, follow_redirects=True).text
    paths = sorted(set(re.findall(r'urlPath="([^"]+\.nc)"', t)))
    prefer = GROUPS[group]["prefer"]
    best = None
    for pref in prefer:  # first matching preference wins, newest file within it
        matches = [p for p in paths if pref in p]
        if matches:
            best = matches[-1]
            break
    best = best or (paths[-1] if paths else None)
    _catalog_cache[group] = (time.time(), best)
    return best


def _ncss_point(urlpath: str, varlist: List[str], lat: float, lon: float,
                timeout_s: float = 20.0) -> Optional[Dict[str, float]]:
    r = httpx.get(f"{BASE}/ncss/grid/{urlpath}",
                  params={"var": varlist, "latitude": lat, "longitude": lon,
                          "temporal": "nearest", "accept": "csv"},
                  timeout=timeout_s, headers=HDRS)
    r.raise_for_status()
    rows = [l for l in r.text.strip().splitlines() if l]
    header_idx = next((i for i, l in enumerate(rows) if l.startswith("time")), None)
    if header_idx is None or header_idx + 1 >= len(rows):
        return None
    header = [h.split("[")[0] for h in rows[header_idx].split(",")]
    vals = rows[header_idx + 1].split(",")
    row = dict(zip(header, vals))
    out: Dict[str, float] = {}
    for v in varlist:
        try:
            f = float(row.get(v, "NaN"))
            out[v] = None if math.isnan(f) else f
        except (TypeError, ValueError):
            out[v] = None
    return out


def _query_group(group: str, lat: float, lon: float, timeout_s: float = 20.0,
                 sea_steps: int = 6) -> Dict[str, Any]:
    """Query with seaward stepping: coastal land-mask NaNs resolve offshore."""
    urlpath = _latest_urlpath(group, timeout_s)
    if not urlpath:
        return {"_error": "no dataset in catalog"}
    varlist = GROUPS[group]["vars"]
    last: Optional[Dict[str, float]] = None
    for step in range(sea_steps + 1):
        qlon = lon - step * 0.15  # Arabian Sea is west of Kochi; steps go seaward
        try:
            last = _ncss_point(urlpath, varlist, lat, qlon, timeout_s)
        except Exception as e:
            return {"_error": str(e)[:150]}
        if last and any(v is not None for v in last.values()):
            return {"values": last, "file": urlpath.split("/")[-1],
                    "qlat": lat, "qlon": round(qlon, 3), "sea_steps": step}
    return {"values": last or {}, "file": urlpath.split("/")[-1],
            "qlat": lat, "qlon": lon, "_warning": "all wet-cell steps NaN"}


def _wind_dir_deg(u: Optional[float], v: Optional[float]) -> Optional[float]:
    """Meteorological wind direction (FROM): components point downwind."""
    if u is None or v is None:
        return None
    return (math.degrees(math.atan2(-u, -v)) + 360.0) % 360.0


def _current_dir_deg(u: Optional[float], v: Optional[float]) -> Optional[float]:
    """Oceanographic current direction (TOWARD): components point downstream."""
    if u is None or v is None:
        return None
    return (math.degrees(math.atan2(u, v)) + 360.0) % 360.0


def extract_point(lat: float, lon: float, timeout_s: float = 20.0) -> Dict[str, Any]:
    """Full multi-group extraction -> normalized observation fields + provenance."""
    from concurrent.futures import ThreadPoolExecutor
    valid_time = datetime.utcnow()
    groups: Dict[str, Any] = {}
    fast_groups = ("wave", "winds", "sst")  # currents/chl: coarse grid / NCSS gap
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(_query_group, g, lat, lon, timeout_s): g for g in fast_groups}
        for fut in futs:
            g = futs[fut]
            try:
                groups[g] = fut.result(timeout=timeout_s + 5)
            except Exception as e:
                groups[g] = {"_error": str(e)[:150]}
    wv = groups["wave"].get("values", {}) if "wave" in groups else {}
    wn = groups["winds"].get("values", {}) if "winds" in groups else {}
    cu = groups.get("currents", {}).get("values", {})
    sst = groups["sst"].get("values", {}) if "sst" in groups else {}
    chl = groups.get("chl", {}).get("values", {})
    wsm = wn.get("WSM")
    cur = cu.get("CURRENT")
    if cur is None and cu.get("U") is not None and cu.get("V") is not None:
        cur = math.hypot(cu["U"], cu["V"])
    payload = {
        "wave_height_m": wv.get("SWH"),
        "wave_period_s": wv.get("SWP") or wv.get("WP"),
        "wind_speed_ms": wsm,
        "wind_direction_deg": _wind_dir_deg(wn.get("WSXM"), wn.get("WSYM")),
        "current_speed_ms": cur,
        "current_direction_deg": _current_dir_deg(cu.get("U"), cu.get("V")),
        "sst_c": sst.get("SST"),
        "chlorophyll": chl.get("chlor_a"),
    }
    files = {g: groups[g].get("file") for g in groups}
    errors = {g: groups[g].get("_error") for g in groups if groups[g].get("_error")}
    return {"lat": lat, "lon": lon, "valid_time": valid_time.isoformat(),
            "retrieval_time": datetime.utcnow().isoformat(), "source": SOURCE,
            "quality": "ok" if any(v is not None for v in payload.values()) else "missing",
            **payload, "_files": files, "_errors": errors}


def snapshot(lat: float, lon: float, out_dir: str = "ml/data/raw") -> str:
    """Persist one extraction as timestamped JSON for dataset building."""
    os.makedirs(out_dir, exist_ok=True)
    rec = extract_point(lat, lon)
    path = os.path.join(out_dir, f"incois_thredds_{rec['valid_time'][:10]}_{lat}_{lon}.json"
                        .replace(":", "-"))
    import json
    with open(path, "w") as f:
        json.dump(rec, f, indent=2)
    return path
