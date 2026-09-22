# Geometry conversion helpers between GeoJSON (canonical), shapely and WKB.
#
# Canonical models carry GeoJSON dicts. The persistence layer stores PostGIS
# geometries. Unit tests that do not run PostGIS can still exercise the
# shapely<->GeoJSON round trip without a database.
from typing import Tuple
from shapely.geometry import shape, mapping
from shapely.geometry.base import BaseGeometry
from geoalchemy2 import WKBElement
from geoalchemy2.shape import from_shape


def geojson_to_shape(geojson: dict) -> BaseGeometry:
    """Convert a GeoJSON geometry dict to a shapely geometry."""
    return shape(geojson)


def shape_to_geojson(geom: BaseGeometry) -> dict:
    """Convert a shapely geometry to a GeoJSON geometry dict."""
    return mapping(geom)


def geojson_to_wkb(geojson: dict, srid: int = 4326) -> WKBElement:
    """Convert a GeoJSON geometry dict to a WKBElement suitable for inserts."""
    return from_shape(geojson_to_shape(geojson), srid=srid)


def wkb_to_geojson(wkb: WKBElement | None) -> dict | None:
    """Convert a DB WKBElement (or NULL) to a GeoJSON geometry dict."""
    if wkb is None:
        return None
    from geoalchemy2.shape import to_shape
    return mapping(to_shape(wkb))


def geojson_centroid_long_lat(geojson: dict) -> Tuple[float, float]:
    """Return (lon, lat) centroid of a GeoJSON geometry."""
    geom = geojson_to_shape(geojson)
    c = geom.centroid
    return (float(c.x), float(c.y))


def bounding_box(geojson: dict):
    """Return [minx, miny, maxx, maxy] of a GeoJSON geometry."""
    geom = geojson_to_shape(geojson)
    return list(geom.bounds)


def normalize_multipolygon(geojson: dict) -> dict:
    """Coerce Polygon -> MultiPolygon GeoJSON so DB columns accept either."""
    geom = geojson_to_shape(geojson)
    if geom.geom_type == "Polygon":
        from shapely.geometry import MultiPolygon
        geom = MultiPolygon([geom])
    return mapping(geom)