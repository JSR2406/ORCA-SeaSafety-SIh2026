"""Geofence wrapper around PostGIS. No ML here — pure spatial rules."""
from typing import Optional


def check_geofence(lat: float, lon: float) -> Optional[str]:
    """Returns restriction id if inside a restricted polygon, else None.

    Returns None when PostGIS is unconfigured/unreachable — caller must
    treat geofence as unknown via freshness, never as a restriction.
    """
    from database.postgis import check_spatial_risk
    try:
        score = check_spatial_risk(lat, lon)
    except Exception:
        return None
    return "RESTRICTED_SECTOR" if score >= 0.7 else None
