# Tool group: weather - forecast and observation products from the IMD adapter.
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.mcp.registry import READ_ONLY, ToolDefinition, ToolRegistry
from app.services.marine_data_service import MarineDataService


class WeatherForecastInput(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    valid_time: Optional[datetime] = Field(None, description="The time the forecast must cover (ISO-8601)")
    radius_km: float = Field(50.0, gt=0.0, le=500.0)
    limit: int = Field(5, ge=1, le=50)


class WeatherObservationInput(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    time: Optional[datetime] = Field(None, description="Observation time (ISO-8601; omit for latest)")
    radius_km: float = Field(50.0, gt=0.0, le=500.0)
    limit: int = Field(5, ge=1, le=50)


def register(registry: ToolRegistry, marine: MarineDataService) -> None:
    async def forecast(
        lat: float, lon: float, valid_time: Optional[datetime] = None,
        radius_km: float = 50.0, limit: int = 5,
        ctx=None,
    ):
        return await marine.get_weather_forecast(
            lat, lon, valid_time=valid_time, radius_km=radius_km, limit=limit)

    async def observation(
        lat: float, lon: float, time: Optional[datetime] = None,
        radius_km: float = 50.0, limit: int = 5,
        ctx=None,
    ):
        return await marine.get_weather_observation(
            lat, lon, time=time, radius_km=radius_km, limit=limit)

    registry.register(ToolDefinition(
        name="weather.forecast",
        fn=forecast,
        title="Weather forecast",
        description="Weather forecast nearest a point valid at an optional time.",
        group="weather",
        safety=READ_ONLY,
        input_model=WeatherForecastInput,
    ))
    registry.register(ToolDefinition(
        name="weather.observation",
        fn=observation,
        title="Weather observation",
        description="Latest weather observation nearest a point.",
        group="weather",
        safety=READ_ONLY,
        input_model=WeatherObservationInput,
    ))