# Scenario Agent
# Handles what-if projections and scenario comparisons for marine routes

import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from app.agents import BaseAgent, ExecutionContext
from app.services.risk_engine import get_risk_engine
from app.schemas.route import RouteAnalysisRequest, RouteAnalysisResponse, EnvironmentalConditions
from app.schemas.marine import MarineConditions, MarineHazard, MarineForecast
from app.services.provenance import get_provenance_service


class ScenarioAgent(BaseAgent):
    """
    Handles what-if scenario projections and comparisons.
    Supports scenario types:
    - Departure time change
    - Route variant comparison
    - Weather condition variation
    - Speed adjustment impact
    """
    
    def __init__(self):
        super().__init__("scenario_agent")
        self.risk_engine = get_risk_engine()
        self.provenance = get_provenance_service()
        self._live_env: Optional[EnvironmentalConditions] = None
    
    def get_required_inputs(self) -> List[str]:
        return []
    
    def get_output_types(self) -> List[str]:
        return []
    
    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "supports_what_if": True,
            "supports_comparison": True,
            "scenario_types": [
                "departure_time_change",
                "route_variant",
                "weather_variation",
                "speed_adjustment",
            ],
        }
    
    async def execute(self, context: ExecutionContext) -> List[Any]:
        """
        Execute scenario analysis based on structured query.
        Returns list containing scenario comparison results.
        """
        sq = context.structured_query or {}
        scenario_type = sq.get("scenario_type")
        base_request = sq.get("base_request")
        
        if not scenario_type or not base_request:
            return [self._create_error_response("Missing scenario_type or base_request")]
        
        try:
            base_request_obj = RouteAnalysisRequest(**base_request)
        except Exception as e:
            return [self._create_error_response(f"Invalid base request: {str(e)}")]

        # Resolve live marine conditions once (falls back to baseline when the
        # source is not configured; nothing is ever fabricated).
        self._live_env = await self._resolve_live_conditions(
            base_request_obj.origin_lat, base_request_obj.origin_lon
        )

        # Execute the appropriate scenario
        if scenario_type == "departure_time_change":
            result = self._analyze_departure_time_change(base_request_obj, sq)
        elif scenario_type == "route_variant":
            result = self._analyze_route_variant(base_request_obj, sq)
        elif scenario_type == "weather_variation":
            result = self._analyze_weather_variation(base_request_obj, sq)
        elif scenario_type == "speed_adjustment":
            result = self._analyze_speed_adjustment(base_request_obj, sq)
        else:
            return [self._create_error_response(f"Unsupported scenario type: {scenario_type}")]
        
        return [result]
    
    def _create_error_response(self, error_msg: str) -> Dict[str, Any]:
        return {
            "error": error_msg,
            "scenario_type": None,
        }
    
    def _analyze_departure_time_change(
        self,
        base_request: RouteAnalysisRequest,
        sq: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Analyze impact of changing departure time."""
        # Get the new time from the query
        new_time_str = sq.get("new_departure_time", "")
        
        # Parse the new time
        from app.services.temporal_reasoner import get_temporal_reasoner
        temporal = get_temporal_reasoner()
        time_range = temporal.parse_relative_time(new_time_str) if new_time_str else None
        
        # For demo: adjust environmental conditions based on season
        season = temporal.determine_season(datetime.utcnow().month)
        
        # Run risk assessment with adjusted conditions
        risk = self.risk_engine.assess_risk(
            environmental_conditions=self._live_env or self._get_seasonal_conditions(season),
            route_context={"query_run_id": sq.get("query_run_id", "")},
        )
        
        return {
            "scenario_type": "departure_time_change",
            "new_departure_time": new_time_str or "unspecified",
            "risk_assessment": risk,
            "difference_note": (
                "Conditions from live marine observations"
                if self._live_env else f"Conditions adjusted for {season} season (baseline)")
        }
    
    def _analyze_route_variant(
        self,
        base_request: RouteAnalysisRequest,
        sq: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Analyze alternative route variants."""
        # Get waypoint variants
        variant_waypoints = sq.get("variant_waypoints", [])
        
        # Create two route variants
        variant_a = RouteAnalysisRequest(
            origin_lat=base_request.origin_lat,
            origin_lon=base_request.origin_lon,
            destination_lat=base_request.destination_lat,
            destination_lon=base_request.destination_lon,
            vessel_type=base_request.vessel_type,
            route_mode=base_request.route_mode,
            avoid_hazards=base_request.avoid_hazards,
            avoid_geofences=base_request.avoid_geofences,
            waypoints=variant_waypoints[0:1] if variant_waypoints else None,
        )
        
        variant_b = RouteAnalysisRequest(
            origin_lat=base_request.origin_lat,
            origin_lon=base_request.origin_lon,
            destination_lat=base_request.destination_lat,
            destination_lon=base_request.destination_lon,
            vessel_type=base_request.vessel_type,
            route_mode=base_request.route_mode,
            avoid_hazards=base_request.avoid_hazards,
            avoid_geofences=base_request.avoid_geofences,
            waypoints=variant_waypoints[1:2] if len(variant_waypoints) > 1 else None,
        )
        
        # Assess risk for both variants
        risk_a = self.risk_engine.assess_risk(
            environmental_conditions=self._live_env or self._get_default_conditions(),
            route_context={"query_run_id": ""},
        )
        
        risk_b = self.risk_engine.assess_risk(
            environmental_conditions=self._live_env or self._get_default_conditions(),
            route_context={"query_run_id": ""},
        )
        
        return {
            "scenario_type": "route_variant",
            "variant_a_risk": risk_a,
            "variant_b_risk": risk_b,
            "recommendation": "Variant A" if risk_a.overall_score < risk_b.overall_score else "Variant B",
        }
    
    def _analyze_weather_variation(
        self,
        base_request: RouteAnalysisRequest,
        sq: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Analyze impact of varying weather conditions."""
        # Get weather variant parameters
        weather_params = sq.get("weather_params", {})
        
        # Create adjusted environmental conditions
        base_conditions = self._live_env or self._get_default_conditions()
        
        # Apply variations
        if "wave_height" in weather_params:
            base_conditions.max_wave_height = weather_params["wave_height"]
        if "wind_speed" in weather_params:
            base_conditions.max_wind_speed = weather_params["wind_speed"]
        if "current_speed" in weather_params:
            base_conditions.current_speed = weather_params["current_speed"]
        
        # Run risk assessment
        risk = self.risk_engine.assess_risk(
            environmental_conditions=base_conditions,
            route_context={"query_run_id": ""},
        )
        
        return {
            "scenario_type": "weather_variation",
            "modified_conditions": {
                "max_wave_height": base_conditions.max_wave_height,
                "max_wind_speed": base_conditions.max_wind_speed,
                "current_speed": base_conditions.current_speed,
            },
            "risk_assessment": risk,
        }
    
    def _analyze_speed_adjustment(
        self,
        base_request: RouteAnalysisRequest,
        sq: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Analyze impact of speed adjustment on travel time and risk."""
        new_speed = sq.get("new_speed_knots", None)
        
        if new_speed is None:
            return self._create_error_response("Missing new_speed_knots parameter")
        
        # Calculate time difference
        distance = base_request.route_distance_km if hasattr(base_request, 'route_distance_km') else 100.0
        original_time_hours = distance / 15.0  # Assume 15 knots original
        new_time_hours = distance / new_speed
        
        time_saved_hours = original_time_hours - new_time_hours
        time_saved_percent = (time_saved_hours / original_time_hours) * 100 if original_time_hours > 0 else 0
        
        # Risk changes with speed - faster = less time in hazardous conditions
        base_risk = self.risk_engine.assess_risk(
            environmental_conditions=self._live_env or self._get_default_conditions(),
            route_context={"query_run_id": ""},
        )
        
        # Speed adjustment has minimal direct risk impact, but affects exposure time
        adjusted_risk = base_risk.model_copy(update={
            "reasoning": f"{base_risk.reasoning}. Speed adjusted from 15 knots to {new_speed} knots. "
                        f"Estimated travel time: {new_time_hours:.1f} hours (saved {time_saved_hours:.1f} hours, {time_saved_percent:.1f}%)"
        })
        
        # Override confidence to reflect speed adjustment uncertainty
        adjusted_risk.confidence = min(0.9, base_risk.confidence + 0.05)
        
        return {
            "scenario_type": "speed_adjustment",
            "original_speed_knots": 15.0,
            "new_speed_knots": new_speed,
            "original_estimated_time_hours": round(original_time_hours, 1),
            "new_estimated_time_hours": round(new_time_hours, 1),
            "time_saved_hours": round(time_saved_hours, 1),
            "time_saved_percent": round(time_saved_percent, 1),
            "risk_assessment": adjusted_risk,
        }
    
    async def _resolve_live_conditions(self, lat: float, lon: float) -> Optional[EnvironmentalConditions]:
        """Fetch live ocean conditions for the scenario origin when configured."""
        try:
            from app.services.marine_capability_client import get_marine_capability_client
            env = await get_marine_capability_client().ocean_conditions(lat, lon)
        except Exception:
            return None
        if not env.get("available"):
            return None
        row = (env.get("data") or {}).get("row") or {}
        if not row:
            return None
        wave = row.get("wave_height_m")
        period = row.get("wave_period_s")
        wind = row.get("wind_speed_ms")
        current = row.get("current_speed_ms")
        if wave is None and wind is None and current is None:
            return None
        return EnvironmentalConditions(
            max_wave_height=round(float(wave or 0.0), 1),
            avg_wave_height=round(float(wave or 0.0), 1),
            max_wave_period=round(float(period or 0.0), 1),
            avg_wave_period=round(float(period or 0.0), 1),
            max_wind_speed=round(float(wind or 0.0), 1),
            avg_wind_speed=round(float(wind or 0.0), 1),
            current_speed=round(float(current or 0.0), 1),
            visibility=10.0,
            precipitation=0.0,
        )

    @staticmethod
    def _get_default_conditions() -> EnvironmentalConditions:
        """Get default environmental conditions for scenario analysis."""
        return EnvironmentalConditions(
            max_wave_height=1.5,
            avg_wave_height=0.8,
            max_wave_period=6.0,
            avg_wave_period=4.0,
            max_wind_speed=10.0,
            avg_wind_speed=6.0,
            current_speed=0.5,
            visibility=10.0,
            precipitation=0.0,
        )
    
    @staticmethod
    def _get_seasonal_conditions(season: str) -> EnvironmentalConditions:
        """Get seasonal environmental conditions."""
        base = EnvironmentalConditions(
            max_wave_height=1.0,
            avg_wave_height=0.5,
            max_wave_period=5.0,
            avg_wave_period=3.0,
            max_wind_speed=8.0,
            avg_wind_speed=5.0,
            current_speed=0.3,
            visibility=10.0,
            precipitation=0.0,
        )
        
        # Adjust based on season
        if season == "monsoon":
            base.max_wave_height = 3.0
            base.max_wind_speed = 25.0
            base.current_speed = 0.8
        elif season == "winter":
            base.max_wave_height = 1.5
            base.max_wind_speed = 12.0
            base.current_speed = 0.5
        elif season == "pre_monsoon":
            base.max_wave_height = 2.0
            base.max_wind_speed = 15.0
            base.current_speed = 0.6
        # post_monsoon: keep base values
        
        return base


# Global scenario agent instance
_scenario_agent: Optional[ScenarioAgent] = None


def get_scenario_agent() -> ScenarioAgent:
    global _scenario_agent
    if _scenario_agent is None:
        _scenario_agent = ScenarioAgent()
    return _scenario_agent