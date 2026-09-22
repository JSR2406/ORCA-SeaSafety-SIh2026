# Route Analysis Schema
# Schema for vessel route analysis requests and responses

from enum import Enum
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime


class RouteMode(str, Enum):
    """Travel modes for route analysis."""
    SAIL = "sail"
    POWER = "power"
    MANUAL = "manual"


class VesselType(str, Enum):
    """Types of vessels for route planning."""
    SAILBOAT = "sailboat"
    POWER_BOAT = "power_boat"
    COMMERCIAL = "commercial"
    RESEARCH = "research"
    FISHING = "fishing"


class EnvironmentalConditions(BaseModel):
    """Environmental conditions along a route."""
    max_wave_height: float = Field(ge=0, le=10, description="Maximum wave height in meters")
    avg_wave_height: float = Field(ge=0, le=10, description="Average wave height in meters")
    max_wave_period: float = Field(ge=0, le=30, description="Maximum wave period in seconds")
    avg_wave_period: float = Field(ge=0, le=30, description="Average wave period in seconds")
    max_wind_speed: float = Field(ge=0, le=50, description="Maximum wind speed in m/s")
    avg_wind_speed: float = Field(ge=0, le=50, description="Average wind speed in m/s")
    current_speed: float = Field(ge=0, le=3, description="Current speed in m/s")
    visibility: Optional[float] = Field(ge=0, le=50, description="Visibility in km")
    precipitation: float = Field(ge=0, le=10, description="Precipitation probability %")


class HazardIntersection(BaseModel):
    """Hazard intersection along a route."""
    hazard_type: str
    location: Dict[str, float]  # lat, lon
    severity: Literal["low", "moderate", "high"]
    distance_from_route_km: float
    description: str


class GeofenceIntersection(BaseModel):
    """Geofence intersection along a route."""
    geofence_id: str
    geofence_name: str
    violation_type: Literal["enter", "exit", "pass"]
    location: Dict[str, float]  # lat, lon
    severity: Literal["low", "moderate", "high"]


class RouteSegment(BaseModel):
    """A segment of a vessel route."""
    segment_id: str
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    distance_km: float
    estimated_time_hours: float
    conditions: EnvironmentalConditions
    hazards: List[HazardIntersection] = Field(default_factory=list)
    geofences: List[GeofenceIntersection] = Field(default_factory=list)


class RiskAssessment(BaseModel):
    """Risk assessment for a route."""
    overall_score: float = Field(ge=0, le=1, description="Overall risk score 0-1")
    risk_level: Literal["low", "moderate", "elevated", "unavailable"]
    component_scores: Dict[str, float]
    reasoning: str
    confidence: float
    missing_data: List[str]


class RouteAnalysisRequest(BaseModel):
    """Request schema for route analysis."""
    
    origin_lat: float = Field(ge=-90, le=90, description="Origin latitude")
    origin_lon: float = Field(ge=-180, le=180, description="Origin longitude")
    destination_lat: float = Field(ge=-90, le=90, description="Destination latitude")
    destination_lon: float = Field(ge=-180, le=180, description="Destination longitude")
    
    vessel_type: VesselType = Field(default=VesselType.POWER_BOAT, description="Type of vessel")
    route_mode: RouteMode = Field(default=RouteMode.POWER, description="Travel mode")
    
    avoid_hazards: bool = Field(default=True, description="Avoid hazards if possible")
    avoid_geofences: bool = Field(default=True, description="Avoid geofenced areas")
    
    # Optional: specify a custom route path
    waypoints: Optional[List[Dict[str, float]]] = Field(
        default=None, 
        description="List of [lat, lon] waypoints to waypoint via"
    )
    
    # Optional: avoid specific areas
    avoid_bbox: Optional[Dict[str, float]] = Field(
        default=None,
        description="Avoid bounding box {min_lat, max_lat, min_lon, max_lon}"
    )
    
    # Quality and safety thresholds
    max_risk_score: float = Field(default=0.7, ge=0, le=1, description="Maximum acceptable risk score")
    preferred_speed: Optional[float] = Field(
        default=None, ge=0, description="Preferred speed in knots"
    )
    
    @validator("origin_lat", "destination_lat")
    def valid_latitude(cls, v):
        if v < -90 or v > 90:
            raise ValueError("Latitude must be between -90 and 90")
        return v
    
    @validator("origin_lon", "destination_lon")
    def valid_longitude(cls, v):
        if v < -180 or v > 180:
            raise ValueError("Longitude must be between -180 and 180")
        return v


class RouteAnalysisResponse(BaseModel):
    """Response schema for route analysis."""
    
    route_geometry: List[Dict[str, float]]  # List of [lon, lat] points
    route_distance_km: float
    total_estimated_time_hours: float
    segments: List[RouteSegment]
    hazard_intersections: List[HazardIntersection]
    geofence_intersections: List[GeofenceIntersection]
    environmental_conditions: EnvironmentalConditions
    risk_assessment: RiskAssessment
    evidence: List[Dict[str, Any]]
    recommendations: List[str]
    limitations: List[str]


class MarineConditions(BaseModel):
    """Marine conditions at a location."""
    location: Dict[str, float]  # lat, lon
    wave_height: float = Field(ge=0, le=10, description="Wave height in meters")
    wave_period: float = Field(ge=0, le=30, description="Wave period in seconds")
    wave_direction: float = Field(ge=0, le=360, description="Wave direction in degrees")
    wind_speed: float = Field(ge=0, le=50, description="Wind speed in m/s")
    wind_direction: float = Field(ge=0, le=360, description="Wind direction in degrees")
    current_speed: float = Field(ge=0, le=3, description="Current speed in m/s")
    current_direction: float = Field(ge=0, le=360, description="Current direction in degrees")
    sea_surface_temp: float = Field(ge=-2, le=40, description="Sea surface temperature in °C")
    visibility: Optional[float] = Field(default=None, ge=0, le=50, description="Visibility in km")
    precipitation: float = Field(ge=0, le=100, description="Precipitation probability %")
    
    @validator("wave_height", "wind_speed", "current_speed", "sea_surface_temp", "visibility")
    def non_negative(cls, v, values=None):
        if v is not None and v < 0:
            raise ValueError("Value must be non-negative")
        return v