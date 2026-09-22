# Phase 5 - STATIC GEOFENCE catalog.
#
# Permanent, documented geophysical/administrative boundaries (EEZ, IMBL,
# Marine Protected Areas).  The canonical production store is PostGIS
# (restricted_areas with restriction_kind='permanent'); this catalog makes the
# STATIC layer queryable deterministically and offline so demos and tests run
# without a database.  Geometries are APPROXIMATE cartographic bounds for
# demonstration, never legal boundaries.
from typing import Any, Dict, List

from app.services.geospatial_service import point_in_polygon

_SEVERITY = {
    "eez": "moderate",
    "imbl": "high",
    "mpa": "moderate",
    "ecological_zone": "moderate",
    "marine_boundary": "moderate",
}

_STATIC_GEOFENCES: List[Dict[str, Any]] = [
    {
        "geofence_id": "GEOF-IN-EEZ-ARABIAN",
        "name": "Indian EEZ - Arabian Sea sector (approx.)",
        "type": "eez",
        "severity": "moderate",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [66.0, 6.0], [74.0, 6.0], [74.0, 22.0], [66.0, 22.0], [66.0, 6.0],
            ]],
        },
    },
    {
        "geofence_id": "GEOF-IN-EEZ-BAYOFBENGAL",
        "name": "Indian EEZ - Bay of Bengal sector (approx.)",
        "type": "eez",
        "severity": "moderate",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [80.0, 4.0], [94.0, 4.0], [94.0, 22.5], [80.0, 22.5], [80.0, 4.0],
            ]],
        },
    },
    {
        "geofence_id": "GEOF-IN-IMBL",
        "name": "Indo-Myanmar Baseline Boundary (approx.)",
        "type": "imbl",
        "severity": "high",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [80.0, 20.0], [94.0, 20.0], [94.0, 22.5], [80.0, 22.5], [80.0, 20.0],
            ]],
        },
    },
    {
        "geofence_id": "GEOF-IN-MPA-GULFOFMANNAR",
        "name": "Gulf of Mannar Marine National Park (approx.)",
        "type": "mpa",
        "severity": "moderate",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [78.0, 8.7], [79.4, 8.7], [79.4, 9.5], [78.0, 9.5], [78.0, 8.7],
            ]],
        },
    },
    {
        "geofence_id": "GEOF-IN-MPA-GREATNICOBAR",
        "name": "Great Nicobar Biosphere - marine sector (approx.)",
        "type": "mpa",
        "severity": "moderate",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [92.8, 6.5], [94.0, 6.5], [94.0, 7.3], [92.8, 7.3], [92.8, 6.5],
            ]],
        },
    },
    {
        "geofence_id": "GEOF-IN-BOUNDARY-LAKSHADWEEP",
        "name": "Lakshadweep water boundary (approx.)",
        "type": "marine_boundary",
        "severity": "moderate",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [71.5, 10.0], [73.6, 10.0], [73.6, 11.5], [71.5, 11.5], [71.5, 10.0],
            ]],
        },
    },
]


class GeofenceCatalog:
    """Read-only static geofence registry with deterministic containment."""

    def __init__(self, geofences: List[Dict[str, Any]] = None) -> None:
        self._geofences = geofences if geofences is not None else _STATIC_GEOFENCES

    def list_geofences(self) -> List[Dict[str, Any]]:
        return [dict(g) for g in self._geofences]

    def hits(self, lat: float, lon: float) -> List[Dict[str, Any]]:
        """Static geofences containing the point (deterministic)."""
        hits = []
        for geofence in self._geofences:
            if point_in_polygon(lat, lon, geofence.get("geometry") or {}):
                hits.append(dict(geofence))
        return hits

    def severity_for(self, geofence_type: str) -> str:
        return _SEVERITY.get(geofence_type, "moderate")


def _build_default_catalog() -> GeofenceCatalog:
    return GeofenceCatalog()


_default_catalog: Any = None


def get_geofence_catalog() -> GeofenceCatalog:
    return _build_default_catalog()