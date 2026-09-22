# Convert an argopy xarray Dataset into ArgoRepository-friendly rows.
#
# argopy's .to_xarray() layout varies slightly by access mode, so this uses the
# canonical ARGO variable names (JULD, LATITUDE, LONGITUDE, PRES, TEMP, PSAL,
# DOXY, CHLA) and tolerates either a "PROFILE" dim or a (N_PROF, N_LEVELS) 2-D
# layout.  It never invokes network I/O - it only shapes already-fetched data.
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _as_number(value) -> Optional[float]:
    try:
        if value is None:
            return None
        f = float(value)
        if f != f:  # NaN
            return None
        return f
    except (TypeError, ValueError):
        return None


def _as_datetime(value) -> Optional[datetime]:
    try:
        from pandas import to_datetime
        ts = to_datetime(value)
        if ts is None:
            return None
        if hasattr(ts, "to_pydatetime"):
            ts = ts.to_pydatetime()
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)
    except Exception:
        return None


def _field(ds: Any, *names: str) -> Optional[Any]:
    """Pull the first present variable matching any of the names."""
    for n in names:
        if n in ds:
            try:
                return ds[n].values
            except Exception:
                return None
    return None


def dataset_to_profiles(
    ds: Any,
    *,
    source: str = "argo",
    source_url: Optional[str] = None,
    qc_status: str = "recommended",
    max_profiles: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Convert an argopy Dataset into profile+observation payload dicts.

    Returns a list of profile dicts::

        {
            "platform_number": int,
            "cycle_number": int,
            "profile_time": datetime,
            "latitude": float,
            "longitude": float,
            "source": str,
            "source_url": str|None,
            "qc_status": str,
            "observations": [{"depth_m":.., "pressure_dbar":.., "temperature_c":..,
                              "salinity_psu":.., "oxygen_umol_kg":.., "chlorophyll":..,
                              "temperature_qc":.., "salinity_qc":.., "oxygen_qc":..}, ...],
        }
    """
    # Named latitude/longitude/time arrays (single- or multi-valued).
    lats = _field(ds, "LATITUDE", "latitude")
    lons = _field(ds, "LONGITUDE", "longitude")
    times = _field(ds, "JULD", "TIME", "profile_time")

    def _scalar(vals, idx: int):
        if vals is None:
            return None
        try:
            return _as_number(vals[idx])
        except Exception:
            return None

    # Determine profile count.
    n_prof = 0
    if lats is not None:
        try:
            n_prof = len(lats)
        except Exception:
            n_prof = 0

    profiles: List[Dict[str, Any]] = []
    for pi in range(n_prof):
        if max_profiles is not None and pi >= max_profiles:
            break
        lat = _scalar(lats, pi) if lats is not None else None
        lon = _scalar(lons, pi) if lons is not None else None
        if lat is None or lon is None:
            continue

        platform = _field(ds, "PLATFORM_NUMBER", "platform_number")
        cycle = _field(ds, "CYCLE_NUMBER", "cycle_number")
        plat = _scalar(platform, pi) if platform is not None else None
        cyc = _scalar(cycle, pi) if cycle is not None else None
        if plat is None or cyc is None:
            continue

        ptime = None
        if times is not None:
            try:
                ptime = _as_datetime(times[pi] if len(times) > 1 else times)
            except Exception:
                ptime = None

        observations: List[Dict[str, Any]] = []
        pres = _field(ds, "PRES", "pressure")
        temp = _field(ds, "TEMP", "temperature")
        psal = _field(ds, "PSAL", "salinity")
        doxy = _field(ds, "DOXY", "oxygen")
        chla = _field(ds, "CHLA", "chlorophyll")
        tqc = _field(ds, "TEMP_QC", "temperature_qc")
        sqc = _field(ds, "PSAL_QC", "salinity_qc")
        oqc = _field(ds, "DOXY_QC", "oxygen_qc")

        n_levels = 0
        if temp is not None:
            try:
                n_levels = len(temp[pi]) if len(temp) > 1 else len(temp)
            except Exception:
                n_levels = 0

        for li in range(n_levels):
            def _level(vals, idx=li, prof=pi):
                if vals is None:
                    return None
                try:
                    if len(vals) > 1:
                        return _as_number(vals[prof][idx])
                    return _as_number(vals[idx])
                except Exception:
                    return None

            depth = _level(pres)
            observations.append({
                "pressure_dbar": depth,
                "depth_m": depth,
                "temperature_c": _level(temp),
                "salinity_psu": _level(psal),
                "oxygen_umol_kg": _level(doxy),
                "chlorophyll": _level(chla),
                "temperature_qc": int(_level(tqc)) if _level(tqc) is not None else None,
                "salinity_qc": int(_level(sqc)) if _level(sqc) is not None else None,
                "oxygen_qc": int(_level(oqc)) if _level(oqc) is not None else None,
            })

        profiles.append({
            "platform_number": int(plat),
            "cycle_number": int(cyc),
            "profile_time": ptime,
            "latitude": lat,
            "longitude": lon,
            "source": source,
            "source_url": source_url,
            "qc_status": qc_status,
            "observations": observations,
        })
    return profiles