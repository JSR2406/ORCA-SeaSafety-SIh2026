# Spatial Reasoner
# PostGIS spatial operations for route analysis and geospatial reasoning

import logging
from typing import Any, Dict, List, Optional, Tuple
from shapely.geometry import Point, LineString, Polygon, shape
import numpy as np

logger = logging.getLogger(__name__)


class SpatialReasoner:
    """
    Provides deterministic spatial operations using PostGIS/SHAPE.
    All operations are pure functions with no side effects.
    """
    
    @staticmethod
    def point_in_bbox(lat: float, lon: float, 
                      min_lat: float, max_lat: float,
                      min_lon: float, max_lon: float) -> bool:
        """Check if a point is within a bounding box."""
        return (min_lat <= lat <= max_lat) and (min_lon <= lon <= max_lon)
    
    @staticmethod
    def point_in_polygon(lat: float, lon: float, 
                         polygon_wkt: str) -> bool:
        """Check if a point is inside a polygon."""
        try:
            point = Point(lon, lat)
            polygon = shape(polygon_wkt) if isinstance(polygon_wkt, str) else Polygon(polygon_wkt)
            return point.within(polygon)
        except Exception as e:
            logger.warning(f"Point-in-polygon failed: {e}")
            return False
    
    @staticmethod
    def distance_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate great-circle distance between two points in km."""
        from math import radians, cos, sin, asin, sqrt
        
        lat1_r, lon1_r = radians(lat1), radians(lon1)
        lat2_r, lon2_r = radians(lat2), radians(lon2)
        
        dlat = lat2_r - lat1_r
        dlon = lon2_r - lon1_r
        
        a = sin(dlat/2)**2 + cos(lat1_r) * cos(lat2_r) * sin(dlon/2)**2
        c = 2 * asin(min(1, sqrt(a)))
        
        # Earth radius in km
        r = 6371
        return c * r
    
    @staticmethod
    def bearing_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate initial bearing from point 1 to point 2 in degrees (0-360)."""
        from math import radians, sin, cos, atan2, degrees
        
        lat1_r, lon1_r = radians(lat1), radians(lon1)
        lat2_r, lon2_r = radians(lat2), radians(lon2)
        
        dlon = lon2_r - lon1_r
        
        y = sin(dlon) * cos(lat2_r)
        x = cos(lat1_r) * sin(lat2_r) - sin(lat1_r) * cos(lat2_r) * cos(dlon)
        
        initial_bearing = degrees(atan2(y, x))
        return (initial_bearing + 360) % 360
    
    @staticmethod
    def is_along_route(lat: float, lon: float, 
                       route_line: LineString,
                       tolerance_km: float = 5.0) -> bool:
        """
        Check if a point is within tolerance of a route line.
        Uses perpendicular distance from point to line.
        """
        try:
            point = Point(lon, lat)
            # Project point onto line
            proj = route_line.interpolate(route_line.project(point), normalized=True)
            distance = point.distance(proj)
            return distance <= (tolerance_km / 111.0)  # Approximate km to degrees
        except Exception:
            return False
    
    @staticmethod
    def bbox_intersection(bbox1: Dict[str, float], 
                          bbox2: Dict[str, float]) -> bool:
        """Check if two bounding boxes intersect."""
        return (bbox1['min_lat'] <= bbox2['max_lat'] and 
                bbox1['max_lat'] >= bbox2['min_lat'] and
                bbox1['min_lon'] <= bbox2['max_lon'] and 
                bbox1['max_lon'] >= bbox2['min_lon'])
    
    @staticmethod
    def buffer_point(lat: float, lon: float, radius_km: float) -> Dict[str, Any]:
        """Create a buffered point geometry (as GeoJSON)."""
        from shapely.geometry import mapping
        point = Point(lon, lat)
        buffered = point.buffer(radius_km * 1000)  # Convert km to meters
        return mapping(buffered)
    
    @staticmethod
    def line_string_from_coords(coords: List[Dict[str, float]]) -> LineString:
        """Create a LineString from list of {lat, lon} dicts."""
        points = [(c['lat'], c['lon']) for c in coords]
        return LineString(points)
    
    @staticmethod
    def line_distance_km(line: LineString) -> float:
        """Calculate total length of a LineString in km."""
        return line.length * 111.0  # Approximate: 1 degree ≈ 111 km at equator
    
    @staticmethod
    def point_along_line(lat: float, lon: float, 
                         line: LineString,
                         fraction: float = 0.5) -> Dict[str, Any]:
        """
        Find the closest point on a line and return coordinates + distance.
        fraction: 0=start, 1=end, 0.5=midpoint
        """
        try:
            point = Point(lon, lat)
            proj = line.interpolate(fraction, normalized=False)
            distance = point.distance(proj)
            return {
                "closest_lat": proj.y,
                "closest_lon": proj.x,
                "distance_km": distance * 111.0,  # Approximate
                "fraction": fraction
            }
        except Exception:
            return {
                "closest_lat": lat,
                "closest_lon": lon,
                "distance_km": 9999.0,
                "fraction": fraction
            }


# Global spatial reasoner instance
_spatial_reasoner: Optional[SpatialReasoner] = None


def get_spatial_reasoner() -> SpatialReasoner:
    global _spatial_reasoner
    if _spatial_reasoner is None:
        _spatial_reasoner = SpatialReasoner()
    return _spatial_reasoner