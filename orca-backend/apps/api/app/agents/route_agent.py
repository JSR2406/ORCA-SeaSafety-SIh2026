# Route Agent
# Generates and analyzes vessel routes with hazard and geofence checking

import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.agents import BaseAgent, ExecutionContext
from app.schemas.provenance import SourceType
from app.schemas.hazard import HazardType
from app.schemas.route import (
    RouteAnalysisRequest, RouteAnalysisResponse, RouteMode, VesselType,
    EnvironmentalConditions, HazardIntersection, GeofenceIntersection,
    RouteSegment, RiskAssessment
)
from app.services.provenance import get_provenance_service
from app.services.data_fusion import get_fusion_engine
from app.services.marine_capability_client import (
    MarineCapabilityClient, get_marine_capability_client,
)


class RouteAgent(BaseAgent):
    """
    Generates vessel routes and performs safety analysis including:
    - Route generation (great circle or waypoint-based)
    - Hazard intersection detection (live marine warnings)
    - Geofence compliance checking (live restricted areas)
    - Environmental condition assessment (live ocean/weather observations)
    - Risk scoring (hard constraints can never be overridden)
    """
    
    def __init__(self, capability: Optional[MarineCapabilityClient] = None):
        super().__init__("route_agent")
        self.provenance = get_provenance_service()
        self.fusion = get_fusion_engine()
        self._capability = capability or get_marine_capability_client()
        self._live_marine = False
        self._evidence_sources: List[str] = []
    
    def get_required_inputs(self) -> List[str]:
        return []
    
    def get_output_types(self) -> List[SourceType]:
        return []
    
    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "generates_routes": True,
            "hazard_detection": True,
            "geofence_checking": True,
            "risk_scoring": True,
        }
    
    async def execute(self, context: ExecutionContext) -> List[Any]:
        """
        Execute route analysis based on structured query.
        Returns list containing RouteAnalysisResponse.
        """
        sq = context.structured_query or {}
        request_dict = sq.get("route_request")
        
        if not request_dict:
            return [self._create_error_response("No route request found in structured query")]
        
        try:
            request = RouteAnalysisRequest(**request_dict)
        except Exception as e:
            return [self._create_error_response(f"Invalid route request: {str(e)}")]
        
        result = await self._analyze_route(request, context)
        return [result]
    
    def _create_error_response(self, error_msg: str) -> Dict[str, Any]:
        """Create an error response."""
        return {
            "route_geometry": [],
            "route_distance_km": 0.0,
            "total_estimated_time_hours": 0.0,
            "segments": [],
            "hazard_intersections": [],
            "geofence_intersections": [],
            "environmental_conditions": EnvironmentalConditions(
                max_wave_height=0, avg_wave_height=0, max_wave_period=0,
                avg_wave_period=0, max_wind_speed=0, avg_wind_speed=0,
                current_speed=0, visibility=0, precipitation=0
            ),
            "risk_assessment": RiskAssessment(
                overall_score=0.0, risk_level="unavailable",
                component_scores={}, reasoning=error_msg, confidence=0.0,
                missing_data=["route_parameters"]
            ),
            "evidence": [],
            "recommendations": [f"Error: {error_msg}"],
            "limitations": ["Could not parse route request"]
        }
    
    async def _analyze_route(self, request: RouteAnalysisRequest, 
                            context: ExecutionContext) -> RouteAnalysisResponse:
        """Perform complete route analysis."""
        start_time = datetime.utcnow()
        
        # 1. Generate route geometry
        route_geometry = await self._generate_route_geometry(request)
        
        # 2. Calculate route distance
        route_distance_km = await self._calculate_route_distance(route_geometry)
        
        # 3. Generate segments
        segments = await self._generate_segments(route_geometry, request)
        
        # 4. Detect hazards along route
        hazard_intersections = await self._detect_hazards(route_geometry, request)
        
        # 5. Check geofence compliance
        geofence_intersections = await self._check_geofences(route_geometry, request)
        
        # 6. Assess environmental conditions
        env_conditions = await self._assess_environmental_conditions(route_geometry, request)
        
        # 7. Calculate risk assessment
        risk_assessment = await self._calculate_risk(
            env_conditions, hazard_intersections, geofence_intersections, request
        )
        
        # 8. Generate evidence and recommendations
        evidence = await self._gather_evidence(route_geometry, request)
        recommendations = self._generate_recommendations(
            risk_assessment, hazard_intersections, geofence_intersections, env_conditions
        )
        limitations = self._get_limitations(request)
        
        total_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Record provenance
        self.provenance.record_execution(
            query_run_id=context.query_run_id,
            agent_name=self.name,
            tool_name="route_analysis",
            input_bundles=[],
            output_bundles=[],  # No evidence bundles
            execution_time_ms=int(total_time),
            status="success",
        )
        
        return RouteAnalysisResponse(
            route_geometry=[{"lat": p[1], "lon": p[0]} for p in route_geometry.coords],
            route_distance_km=round(route_distance_km, 2),
            total_estimated_time_hours=round(route_distance_km / 15.0, 1) if route_distance_km > 0 else 0,
            segments=segments,
            hazard_intersections=hazard_intersections,
            geofence_intersections=geofence_intersections,
            environmental_conditions=env_conditions,
            risk_assessment=risk_assessment,
            evidence=evidence,
            recommendations=recommendations,
            limitations=limitations,
        )
    
    async def _generate_route_geometry(self, request: RouteAnalysisRequest):
        """Generate route geometry using great circle or waypoints."""
        # Simple great circle path between origin and destination
        lons = [request.origin_lon, request.destination_lon]
        lats = [request.origin_lat, request.destination_lat]
        
        # Create a simple line between origin and destination
        line = __import__('shapely.geometry', fromlist=['LineString']).LineString([(request.origin_lon, request.origin_lat), 
                                                        (request.destination_lon, request.destination_lat)])
        
        # Add waypoints if provided
        if request.waypoints:
            wp_coords = []
            wp_coords.append((request.origin_lat, request.origin_lon))
            for wp in request.waypoints:
                wp_coords.append((wp['lat'], wp['lon']))
            wp_coords.append((request.destination_lat, request.destination_lon))
            line = __import__('shapely.geometry', fromlist=['LineString']).LineString([(lon, lat) for lat, lon in wp_coords])
        
        return line
    
    async def _calculate_route_distance(self, route) -> float:
        """Calculate route distance in km."""
        return route.length * 111.0  # Approximate: 1 degree ≈ 111 km at equator
    
    async def _generate_segments(self, route, request: RouteAnalysisRequest) -> List:
        """Generate route segments with environmental data."""
        # Divide route into segments (default: 5 segments)
        num_segments = 5
        
        segments = []
        total_length = route.length
        
        if total_length == 0:
            return segments
        
        segment_length = total_length / num_segments
        
        for i in range(num_segments):
            start_frac = i / num_segments
            end_frac = (i + 1) / num_segments
            
            start_point = route.interpolate(start_frac, normalized=True)
            end_point = route.interpolate(end_frac, normalized=True)
            
            seg_distance = segment_length * 111.0  # km
            
            # Get environmental conditions for segment center
            center_frac = (start_frac + end_frac) / 2
            center_point = route.interpolate(center_frac, normalized=True)
            
            from app.schemas.route import RouteSegment, EnvironmentalConditions
            segments.append(RouteSegment(
                segment_id=f"seg_{i+1}",
                start_lat=start_point.y,
                start_lon=start_point.x,
                end_lat=end_point.y,
                end_lon=end_point.x,
                distance_km=round(seg_distance, 2),
                estimated_time_hours=round(seg_distance / 15.0, 1),  # 15 knots assumed
                conditions=EnvironmentalConditions(
                    max_wave_height=2.0, avg_wave_height=1.0,
                    max_wave_period=8.0, avg_wave_period=5.0,
                    max_wind_speed=10.0, avg_wind_speed=5.0,
                    current_speed=0.5, visibility=10.0, precipitation=0.0
                ),
            ))
        
        return segments
    
    async def _detect_hazards(self, route, request: RouteAnalysisRequest) -> List:
        """Detect live marine-warning hazards intersecting the route."""
        route_latlon = [(lat, lon) for lon, lat in route.coords]
        mid = route.interpolate(0.5, normalized=True)
        warnings_env = await self._capability.warnings_near_route(route_latlon)
        hazards: List[HazardIntersection] = []

        intersections = (warnings_env.get("data") or {}).get("warning_intersections") or []
        self._evidence_sources.extend(warnings_env.get("sources") or [])
        for warning in intersections:
            if warning.get("status") != "active":
                continue
            warning_type = (warning.get("warning_type") or "").lower()
            hazard_type = warning_type if warning_type in {
                t.value for t in HazardType} else HazardType.WARNING.value
            hazards.append(HazardIntersection(
                hazard_type=hazard_type,
                location={"lat": round(mid.y, 4), "lon": round(mid.x, 4)},
                severity=self._severity_to_hazard(warning.get("severity")),
                distance_from_route_km=0.0,
                description=warning.get("description")
                or f"{warning.get('warning_type', 'marine')} warning along route",
            ))
        return hazards

    async def _check_geofences(self, route, request: RouteAnalysisRequest) -> List:
        """Check live restricted-area compliance along the route."""
        route_latlon = [(lat, lon) for lon, lat in route.coords]
        mid = route.interpolate(0.5, normalized=True)
        restrictions_env = await self._capability.restrictions_near_route(route_latlon)

        intersections: List[GeofenceIntersection] = []
        if not restrictions_env.get("available"):
            self._evidence_sources.extend(restrictions_env.get("sources") or [])
            return intersections

        self._evidence_sources.extend(restrictions_env.get("sources") or [])
        for area in (restrictions_env.get("data") or {}).get("intersections") or []:
            if area.get("status") != "active":
                continue
            intersections.append(GeofenceIntersection(
                geofence_id=area.get("area_id"),
                geofence_name=area.get("area_name"),
                violation_type="pass",
                location={"lat": round(mid.y, 4), "lon": round(mid.x, 4)},
                severity=self._severity_to_hazard(area.get("severity")),
                description=f"Restricted area: {area.get('restriction_type') or area.get('restriction_kind') or 'restricted'}",
            ))
        return intersections

    @staticmethod
    def _severity_to_hazard(severity: Optional[str]) -> str:
        """Map marine severity (low/moderate/high/critical/unknown) to hazard level."""
        if severity is None:
            return "low"
        severity = str(severity).lower()
        if severity in ("high", "critical"):
            return "high"
        if severity == "moderate":
            return "moderate"
        return "low"

    async def _assess_environmental_conditions(self, route, request: RouteAnalysisRequest):
        """Assess environmental conditions using live ocean/weather observations."""
        from app.schemas.route import EnvironmentalConditions
        self._live_marine = False
        self._evidence_sources = []

        sample_points = [0.0, 0.5, 1.0]
        rows = []
        for frac in sample_points:
            pt = route.interpolate(frac, normalized=True)
            env = await self._capability.ocean_conditions(pt.y, pt.x)
            if env.get("available"):
                rows.append((env["data"] or {}).get("row") or {})
                self._evidence_sources.extend(env.get("sources") or [])
        weather_rows = []
        for frac in sample_points:
            pt = route.interpolate(frac, normalized=True)
            env = await self._capability.weather_at(pt.y, pt.x)
            if env.get("available"):
                weather_rows.append((env["data"] or {}).get("row") or {})
                self._evidence_sources.extend(env.get("sources") or [])

        if rows:
            self._live_marine = True
            return EnvironmentalConditions(
                max_wave_height=round(max(r.get("wave_height_m") or 0 for r in rows), 1),
                avg_wave_height=round(sum(r.get("wave_height_m") or 0 for r in rows) / len(rows), 1),
                max_wave_period=round(max(r.get("wave_period_s") or 0 for r in rows), 1),
                avg_wave_period=round(sum(r.get("wave_period_s") or 0 for r in rows) / len(rows), 1),
                max_wind_speed=round(max(
                    (r.get("wind_speed_ms") or 0) for r in rows +
                    weather_rows), 1),
                avg_wind_speed=round(sum(
                    (r.get("wind_speed_ms") or 0) for r in rows + weather_rows
                ) / max(len(rows) + len(weather_rows), 1), 1),
                current_speed=round(max(r.get("current_speed_ms") or 0 for r in rows), 1),
                visibility=round(max(
                    (w.get("visibility_m") or 0) for w in weather_rows
                ) / 1000.0, 1) if weather_rows else 10.0,
                precipitation=round(max(
                    (w.get("precipitation_mm") or 0) for w in weather_rows), 1)
                if weather_rows else 0.0,
            )

        # Fallback: deterministic baseline when no live source is configured.
        from app.services.temporal_reasoner import get_temporal_reasoner
        temporal = get_temporal_reasoner()
        season = temporal.determine_season(datetime.utcnow().month)
        base = EnvironmentalConditions(
            max_wave_height=2.0, avg_wave_height=1.0,
            max_wave_period=8.0, avg_wave_period=5.0,
            max_wind_speed=10.0, avg_wind_speed=5.0,
            current_speed=0.5, visibility=10.0, precipitation=0.0,
        )
        if season == "monsoon":
            base.max_wave_height = 3.0
            base.max_wind_speed = 25.0
            base.current_speed = 0.8
        return base
    
    async def _calculate_risk(
        self,
        env_conditions,
        hazard_intersections: List,
        geofence_intersections: List,
        request: RouteAnalysisRequest,
    ):
        """Calculate overall risk score for the route.

        Hard constraints (active restricted areas, active high/critical
        warnings) are passed to the risk engine and can never be overridden by
        the environmental score.
        """
        from app.services.risk_engine import get_risk_engine

        env = EnvironmentalConditions(
            max_wave_height=env_conditions.max_wave_height,
            avg_wave_height=env_conditions.avg_wave_height,
            max_wave_period=env_conditions.max_wave_period,
            avg_wave_period=env_conditions.avg_wave_period,
            max_wind_speed=env_conditions.max_wind_speed,
            avg_wind_speed=env_conditions.avg_wind_speed,
            current_speed=env_conditions.current_speed,
            visibility=env_conditions.visibility,
            precipitation=env_conditions.precipitation,
        )

        active_restrictions = [g for g in geofence_intersections
                               if getattr(g, "severity", None) in ("high", "moderate")]
        high_warnings = [h for h in hazard_intersections
                         if getattr(h, "severity", None) in ("high", "moderate")]
        hard_constraints = {
            "active_restrictions": len(active_restrictions),
            "high_severity_warnings": len(high_warnings),
            "restrictions": [
                {"area_name": getattr(g, "geofence_name", "restricted area")}
                for g in active_restrictions
            ],
            "warnings": [
                {"warning_id": getattr(h, "hazard_type", "marine"), "severity": "high"}
                for h in high_warnings
            ],
        }

        return get_risk_engine().assess_risk(
            environmental_conditions=env,
            hard_constraints=hard_constraints,
        )
    
    async def _gather_evidence(self, route, request: RouteAnalysisRequest) -> List[Dict[str, Any]]:
        """Gather evidence for the route analysis (real data when available)."""
        evidence = []
        evidence.append({
            "source": "route_parameters",
            "type": "route_parameters",
            "description": f"Route from ({request.origin_lat}, {request.origin_lon}) to "
                          f"({request.destination_lat}, {request.destination_lon})",
        })
        if self._live_marine:
            sources = ", ".join(sorted(set(self._evidence_sources))) or "live_marine"
            evidence.append({
                "source": sources,
                "type": "live_marine_observations",
                "description": "Environmental conditions and restriction checks "
                               "derived from live marine observations.",
            })
        else:
            evidence.append({
                "source": "baseline_estimates",
                "type": "marine_data_status",
                "description": "No live marine data source configured; conditions "
                               "are deterministic baseline estimates.",
            })
        return evidence

    def _get_limitations(self, request: RouteAnalysisRequest) -> List[str]:
        """Get list of limitations for the route analysis."""
        limitations = [
            "Speed assumption: 15 knots assumed for time estimates",
            "Simplified route: great circle between waypoints",
        ]
        if not self._live_marine:
            limitations.append("Live marine data: not configured; environmental "
                               "conditions are baseline estimates only")
        
        if not request.waypoints:
            limitations.append("No custom waypoints specified")
        
        if self._live_marine and any(
            s in ("incois", "imd", "mosdac") for s in self._evidence_sources
        ):
            limitations.append("Live marine sources may have partial coverage")

        return limitations
    
    @staticmethod
    def _generate_recommendations(
        risk_assessment,
        hazard_intersections: List,
        geofence_intersections: List,
        env_conditions,
    ) -> List[str]:
        """Generate safety recommendations based on analysis."""
        recommendations = []
        
        if risk_assessment.risk_level == "elevated":
            recommendations.append("Consider postponing voyage until conditions improve")
        
        if risk_assessment.risk_level == "moderate":
            recommendations.append("Monitor conditions continuously during voyage")
        
        if hazard_intersections:
            recommendations.append("Review hazard advisories and adjust route if needed")
        
        if geofence_intersections:
            recommendations.append("Verify geofence compliance and obtain necessary permissions")
        
        # Default recommendation if low risk
        if not recommendations:
            recommendations.append("Conditions appear suitable for planned voyage")
        
        return recommendations


# Global route agent instance
_route_agent: Optional[RouteAgent] = None


def get_route_agent() -> RouteAgent:
    global _route_agent
    if _route_agent is None:
        _route_agent = RouteAgent()
    return _route_agent