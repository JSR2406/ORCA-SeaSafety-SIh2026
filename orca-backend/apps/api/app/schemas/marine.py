# Marine Conditions Schema
# Schema for marine condition data and briefings

from enum import Enum
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime


class MarineConditionType(str, Enum):
    """Types of marine conditions."""
    ROUTE_BRIEFING = "route_briefing"
    AREA_CONDITIONS = "area_conditions"
    HAZARD_SUMMARY = "hazard_summary"
    WEATHER_FORECAST = "weather_forecast"


class MarineConditionRequest(BaseModel):
    """Request schema for marine conditions."""
    
    location_lat: float = Field(ge=-90, le=90, description="Latitude")
    location_lon: float = Field(ge=-180, le=180, description="Longitude")
    
    radius_km: float = Field(
        default=50.0, ge=0, le=500,
        description="Search radius in kilometers"
    )
    
    variables: List[str] = Field(
        default=["wind_speed", "wave_height", "current_speed"],
        description="Variables to retrieve"
    )
    
    time_range: Optional[Dict[str, str]] = Field(
        default=None,
        description="Time range {start, end} in ISO format"
    )
    
    detail_level: Literal["summary", "detailed"] = Field(
        default="summary",
        description="Level of detail"
    )


class MarineConditionResponse(BaseModel):
    """Response schema for marine conditions."""
    
    location: Dict[str, float]
    condition_type: MarineConditionType
    
    # Core measurements
    wave_height: Optional[float] = Field(default=None, ge=0, le=10)
    wave_period: Optional[float] = Field(default=None, ge=0, le=30)
    wind_speed: Optional[float] = Field(default=None, ge=0, le=50)
    wind_direction: Optional[float] = Field(default=None, ge=0, le=360)
    current_speed: Optional[float] = Field(default=None, ge=0, le=3)
    current_direction: Optional[float] = Field(default=None, ge=0, le=360)
    sea_surface_temp: Optional[float] = Field(
        default=None, ge=-2, le=40
    )
    
    # Derived
    visibility: Optional[float] = Field(default=None, ge=0, le=50)
    precipitation: float = Field(default=0.0, ge=0, le=100)
    
    # Assessment
    risk_level: Literal["low", "moderate", "elevated", "unavailable"] = Field(
        default="low"
    )
    confidence: float = Field(ge=0, le=1)
    
    # Evidence
    evidence_ids: List[str] = Field(default_factory=list)
    data_source: str = Field(description="Primary data source")
    
    # Temporal
    valid_from: Optional[datetime] = Field(default=None)
    valid_to: Optional[datetime] = Field(default=None)


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


class MarineHazard(BaseModel):
    """Individual marine hazard."""
    hazard_id: str
    hazard_type: str  # "cyclone", "storm", "geofence", "shallow_water"
    severity: Literal["low", "moderate", "high"]
    location: Dict[str, float]  # lat, lon
    radius_km: Optional[float] = Field(default=None, ge=0)
    description: str
    valid_from: Optional[datetime] = Field(default=None)
    valid_to: Optional[datetime] = Field(default=None)


class MarineForecast(BaseModel):
    """Marine forecast for a period."""
    forecast_id: str
    location: Dict[str, float]
    forecast_period: str  # e.g., "2024-01-15_2024-01-22"
    
    # Forecasted conditions
    wave_height_mean: float = Field(ge=0, le=10)
    wave_height_max: float = Field(ge=0, le=10)
    wave_period_mean: float = Field(ge=0, le=30)
    wind_speed_mean: float = Field(ge=0, le=50)
    wind_speed_max: float = Field(ge=0, le=50)
    current_speed_mean: float = Field(ge=0, le=3)
    
    # Confidence
    confidence: float = Field(ge=0, le=1)
    
    # Evidence
    evidence_ids: List[str] = Field(default_factory=list)