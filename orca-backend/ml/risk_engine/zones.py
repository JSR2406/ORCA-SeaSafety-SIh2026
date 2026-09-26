"""Demo geofence zones: Sector Bravo box, Kochi MPA circle, EEZ limit.

Pure-python point-in-polygon + haversine (no shapely/PostGIS needed for demo).
Production: load these same zones into PostGIS and query ST_Contains/ST_DWithin.
Coordinates are illustrative demo values around Kochi — replace with licensed
Marine Regions / Protected Planet geometries before operational use.
"""
import math

ZONES = [
    {"id": "SECTOR_BRAVO", "kind": "restricted", "source": "NAVAREA VIII #0482",
     "shape": "polygon",
     "points": [(9.95, 76.05), (10.05, 76.05), (10.05, 76.20), (9.95, 76.20)]},
    {"id": "KOCHI_MPA", "kind": "mpa", "source": "Wildlife Protection Act demo",
     "shape": "circle", "center": (9.80, 76.10), "radius_km": 5.0},
    {"id": "EEZ_LIMIT", "kind": "eez", "source": "Marine Regions demo",
     "shape": "offshore_limit", "max_offshore_km": 370.4,
     "ref": (9.97, 76.24)},
]

EARTH_KM = 6371.0


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_KM * math.asin(math.sqrt(a))


def _in_polygon(lat, lon, points):
    inside = False
    n = len(points)
    for i in range(n):
        lat1, lon1 = points[i]
        lat2, lon2 = points[(i + 1) % n]
        if ((lon1 > lon) != (lon2 > lon)) and (
                lat < (lat2 - lat1) * (lon - lon1) / (lon2 - lon1) + lat1):
            inside = not inside
    return inside


def _dist_to_polygon_km(lat, lon, points):
    return min(haversine_km(lat, lon, plat, plon) for plat, plon in points)


def check_point(lat: float, lon: float) -> dict:
    """Evaluate one position. Returns hits[] with distance-to-boundary km."""
    hits = []
    for z in ZONES:
        if z["shape"] == "polygon":
            inside = _in_polygon(lat, lon, z["points"])
            dist = 0.0 if inside else _dist_to_polygon_km(lat, lon, z["points"])
            if inside or dist <= 4.2:  # 4.2 km standoff buffer
                hits.append({"zone": z["id"], "kind": z["kind"], "source": z["source"],
                             "inside": inside, "distance_km": round(dist, 2)})
        elif z["shape"] == "circle":
            d = haversine_km(lat, lon, *z["center"])
            if d <= z["radius_km"] + 4.6:  # 2.5 NM buffer ≈ 4.6 km
                hits.append({"zone": z["id"], "kind": z["kind"], "source": z["source"],
                             "inside": d <= z["radius_km"], "distance_km": round(max(0.0, d - z["radius_km"]), 2)})
        elif z["shape"] == "offshore_limit":
            d = haversine_km(lat, lon, *z["ref"])
            if d > z["max_offshore_km"]:
                hits.append({"zone": z["id"], "kind": z["kind"], "source": z["source"],
                             "inside": True, "distance_km": round(d - z["max_offshore_km"], 2)})
    status = "VIOLATION" if any(h["inside"] for h in hits) else (
        "CAUTION" if hits else "CLEAR")
    return {"status": status, "hits": hits}


def check_route(origin: tuple, dest: tuple, samples: int = 11) -> list:
    """Sample the great-circle-ish leg; return violations with segment index."""
    violations = []
    for i in range(samples):
        f = i / (samples - 1)
        lat = origin[0] + (dest[0] - origin[0]) * f
        lon = origin[1] + (dest[1] - origin[1]) * f
        res = check_point(lat, lon)
        for h in res["hits"]:
            violations.append({"segment": i, "lat": round(lat, 4), "lon": round(lon, 4), **h})
    return violations
