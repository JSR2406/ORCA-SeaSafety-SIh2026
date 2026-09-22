# Phase 12 tool group - production ML models exposed through the MCP boundary.
#
# These wrap the ModelService (feature store -> model -> uncertainty ->
# provenance -> drift).  Every response carries an explicit status:
#   OK | MODEL_UNAVAILABLE | INPUT_DATA_UNAVAILABLE | PREDICTION_UNCERTAIN
# so callers can never mistake an unavailable/uncertain result for a confident
# one.  Responses are advisory only and never override the Risk Engine.
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.mcp.registry import DECISION_SUPPORT, READ_ONLY, ToolDefinition, ToolRegistry
from app.ml.service import get_model_service


class ModelVarsInput(BaseModel):
    lat: Optional[float] = Field(None, ge=-90.0, le=90.0)
    lon: Optional[float] = Field(None, ge=-180.0, le=180.0)
    variables: Dict[str, Any] = Field(
        description="Observed variables: sst_c, chlorophyll, wave_height_m, "
                    "wind_speed_ms, current_speed_ms, visibility_m")
    force_refresh: bool = Field(False, description="Bypass the bounded cache")


class RegistryStatusInput(BaseModel):
    pass


def register(registry: ToolRegistry, model_service=None) -> None:
    """Register the Phase 12 `analytics.*` model tools."""
    service = model_service or get_model_service()

    async def predict_pfz(lat: Optional[float] = None, lon: Optional[float] = None,
                          variables: Optional[Dict[str, Any]] = None,
                          force_refresh: bool = False,
                          ctx=None) -> Dict[str, Any]:
        return service.predict("pfz", variables or {},
                               force=force_refresh).to_dict()

    async def predict_risk(lat: Optional[float] = None, lon: Optional[float] = None,
                           variables: Optional[Dict[str, Any]] = None,
                           force_refresh: bool = False,
                           ctx=None) -> Dict[str, Any]:
        return service.predict("risk", variables or {},
                               force=force_refresh).to_dict()

    async def predict_productivity(lat: Optional[float] = None,
                                   lon: Optional[float] = None,
                                   variables: Optional[Dict[str, Any]] = None,
                                   force_refresh: bool = False,
                                   ctx=None) -> Dict[str, Any]:
        return service.predict("productivity", variables or {},
                               force=force_refresh).to_dict()

    async def predict_forecast(lat: Optional[float] = None,
                               lon: Optional[float] = None,
                               variables: Optional[Dict[str, Any]] = None,
                               force_refresh: bool = False,
                               ctx=None) -> Dict[str, Any]:
        return service.predict("forecast", variables or {},
                               force=force_refresh).to_dict()

    async def registry_status(ctx=None) -> Dict[str, Any]:
        return service.status()

    tools = [
        ("analytics.pfz_predict", "Potential Fishing Zone (ML)", predict_pfz,
         "Rule-based PFZ favorability 0..1 from SST + chlorophyll with uncertainty, "
         "provenance, missing inputs. Status OK | models, never a catch forecast."),
        ("analytics.risk_predict", "Environmental risk proxy (ML)", predict_risk,
         "Advisory risk 0..1 from wave/wind/current with uncertainty. The RiskEngine "
         "remains authoritative for safety; this is decision-support only."),
        ("analytics.productivity_predict", "SRP productivity (ML)", predict_productivity,
         "Productivity proxy 0..1 from chlorophyll + SST with uncertainty and missing "
         "input reporting. Satellite-inferred, not a catch forecast."),
        ("analytics.forecast_predict", "Scenario forecast (ML)", predict_forecast,
         "Bounded deterministic forecast series over the configured horizon with "
         "per-step uncertainty that honestly widens with the horizon."),
        ("analytics.model_registry", "Model registry status", registry_status,
         "Current production model versions, feature-store and drift state."),
    ]
    for name, title, fn, description in tools:
        registry.register(ToolDefinition(
            name=name,
            fn=fn,
            title=title,
            description=description,
            group="analytics_model",
            safety=READ_ONLY,
            input_model=ModelVarsInput if name != "analytics.model_registry"
            else RegistryStatusInput,
        ))