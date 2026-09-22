# Geofence Agent
# Checks vessel compliance with geofenced areas (EEZ, MPAs, restricted zones)

import asyncio
from typing import Any, Dict, List, Optional
from shapely.geometry import Point, shape, Polygon, LineString
from datetime import datetime

from app.services.spatial_reasoner import get_spatial_reasoner, SpatialReasoner
from app.agents import BaseAgent, ExecutionContext
from app.schemas.route import GeofenceIntersection
from app.services.provenance import get_provenance_service


class GeofenceAgent(BaseAgent):
    """
    Checks vessel compliance with geofenced areas including:
    - Exclusive Economic Zones (EEZ)
    - Marine Protected Areas (MPAs)
    - Restricted military zones
    - Traffic separation schemes
    - Environmental protection areas
    """
    
    def __init__(self, capability=None):
        super().__init__("geofence_agent")
        self.spatial = get_spatial_reasoner()
        self.provenance = get_provenance_service()
        if capability is None:
            from app.services.marine_capability_client import get_marine_capability_client
            capability = get_marine_capability_client()
        self._capability = capability
        self._live_source = False
    
    def get_required_inputs(self) -> List[str]:
        return []
    
    def get_output_types(self) -> List[str]:
        return []
    
    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "geofence_checking": True,
            "eez_compliance": True,
            "mpa_detection": True,
            "restricted_zone_detection": True,
        }
    
    async def execute(self, context: ExecutionContext) -> List[Any]:
        """
        Execute geofence compliance check based on structured query.
        Returns list containing compliance assessment.
        """
        sq = context.structured_query or {}
        request_dict = sq.get("geofence_request")
        
        if not request_dict:
            return [self._create_error_response("No geofence request found")]
        
        try:
            return [await self._check_geofence_compliance(context)]
        except Exception as e:
            return [self._create_error_response(str(e))]
    
    def _create_error_response(self, error_msg: str) -> Dict[str, Any]:
        return {
            "geofence_violations": [],
            "compliance_status": "unknown",
            "restricted_zone_intersections": [],
            "eez_violations": [],
            "mpa_violations": [],
            "reasoning": f"Error: {error_msg}",
            "confidence": 0.0,
        }
    
    async def _check_geofence_compliance(self, context: ExecutionContext) -> Dict[str, Any]:
        """Check geofence compliance for a vessel route."""
        # Get route information from context
        sq = context.structured_query or {}
        route_geometry = sq.get("route_geometry", [])
        
        if not route_geometry:
            return self._create_error_response("No route geometry provided")
        
        # Convert route geometry to shapely LineString
        try:
            coords = [(pt['lat'], pt['lon']) for pt in route_geometry]
            line = LineString(coords)
        except Exception:
            return self._create_error_response("Invalid route geometry format")
        
        violations = []
        compliance_status = "compliant"
        confidence = 1.0
        reasoning_note = ""

        # Live restricted areas first (never fabricated: source must be configured).
        route_latlon = [[pt['lat'], pt['lon']] for pt in route_geometry]
        restrictions_env = await self._capability.restrictions_near_route(route_latlon)
        active_areas = []
        if restrictions_env.get("available"):
            live_intersections = (restrictions_env.get("data") or {}).get("intersections") or []
            active_areas = [
                {
                    "id": area.get("area_id"),
                    "name": area.get("area_name"),
                    "type": "restricted",
                    "description": f"Restricted area ({area.get('restriction_type')})",
                    "severity": self._severity_from_area_type(
                        area.get("restriction_kind") or "restricted"),
                }
                for area in live_intersections
                if area.get("status") == "active"
            ]
            if active_areas:
                self._live_source = True
                compliance_status = "violation"
                confidence = 0.9
                reasoning_note = f"Live marine data (sources: {', '.join(restrictions_env.get('sources') or [])})"
        else:
            reasoning_note = "No live marine data configured; demo geofences only"

        # Fallback: demo areas when the marine source is not configured.
        if not active_areas:
            demo_areas = self._get_demo_geofences()
            for area in demo_areas:
                area_geom = shape(area['geometry']) if isinstance(area['geometry'], str) else Polygon(area['geometry'])
                if line.intersects(area_geom) or line.within(area_geom):
                    active_areas.append(area)

        for area in active_areas:
            if isinstance(area.get('geometry'), str) or (isinstance(area.get('geometry'), list)):
                area_geom = shape(area['geometry']) if isinstance(area['geometry'], str) else Polygon(area['geometry'])
                centroid = area_geom.centroid
            else:
                centroid = line.centroid
            nearest_point = line.interpolate(line.project(centroid), normalized=True)

            violation_type = area.get('violation_type', 'enter')
            if violation_type not in ("enter", "exit", "pass"):
                violation_type = "enter"
            violations.append(GeofenceIntersection(
                geofence_id=area['id'],
                geofence_name=area['name'],
                violation_type=violation_type,
                location={"lat": nearest_point.y, "lon": nearest_point.x},
                severity=area.get("severity") or self._severity_from_area_type(area.get('type', 'restricted')),
                description=area.get('description', f"Passing through {area['name']}"),
            ))
            compliance_status = "violation"
            confidence = 0.9
        
        # Record provenance
        self.provenance.record_execution(
            query_run_id=context.query_run_id,
            agent_name=self.name,
            tool_name="geofence_check",
            input_bundles=[],
            output_bundles=[],  # No evidence bundles
            execution_time_ms=0,
            status="success" if compliance_status != "violation" else "violation_detected",
        )
        
        return {
            "geofence_violations": violations,
            "compliance_status": compliance_status,
            "restricted_zone_intersections": [v for v in violations if v.severity in ["high", "moderate"]],
            "eez_violations": [v for v in violations if "eez" in v.geofence_name.lower()],
            "mpa_violations": [v for v in violations if "mpa" in v.geofence_name.lower() or "protected" in v.geofence_name.lower()],
            "source": "live_marine" if self._live_source else "demo_geofences",
            "reasoning": (
                reasoning_note if reasoning_note else
                f"Checked {len(route_geometry)} route points against {len(active_areas)} geofence areas"
            ),
            "confidence": confidence,
        }
    
    @staticmethod
    def _severity_from_area_type(area_type: str) -> str:
        """Convert area type to severity level."""
        type_map = {
            "eez": "moderate",
            "mpa": "moderate",
            "restricted": "high",
            "military": "high",
            "environmental": "moderate",
            "ts": "low",  # Traffic separation - generally low risk
        }
        return type_map.get(area_type.lower(), "moderate")
    
    @staticmethod
    def _get_demo_geofences() -> List[Dict[str, Any]]:
        """Get demo geofence areas for Indian Ocean region."""
        return [
            {
                "id": "geofence_1",
                "name": "Arabian Sea MPA",
                "type": "mpa",
                "geometry": "POLYGON((61.0 18.0, 65.0 18.0, 65.0 22.0, 61.0 22.0, 61.0 18.0))",
                "violation_type": "entry",
                "description": "Marine Protected Area in Arabian Sea",
            },
            {
                "id": "geofence_2",
                "name": "Suez Canal Zone",
                "type": "restricted",
                "geometry": "POLYGON((32.5 29.8, 32.8 29.8, 32.8 30.2, 32.5 30.2, 32.5 29.8))",
                "violation_type": "entry",
                "description": "Suez Canal restricted zone",
            },
            {
                "id": "geofence_3",
                "name": "Strait of Hormuz",
                "type": "eez",
                "geometry": "POLYGON((56.0 25.0, 57.0 25.0, 57.0 26.0, 56.0 26.0, 56.0 25.0))",
                "violation_type": "pass",
                "description": "Strait of Hormuz EEZ area",
            },
        ]


# Global geofence agent instance
_geofence_agent: Optional[GeofenceAgent] = None


def get_geofence_agent() -> GeofenceAgent:
    global _geofence_agent
    if _geofence_agent is None:
        _geofence_agent = GeofenceAgent()
    return _geofence_agent

    