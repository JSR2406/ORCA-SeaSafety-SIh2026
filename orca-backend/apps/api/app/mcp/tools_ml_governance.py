# Phase 13 - MCP governance / provenance tools.
#
# Exposes ONLY safe ML-governance capabilities to the conversational agent:
#   analytics.model_status
#   analytics.prediction_provenance
#   analytics.model_metrics
#   analytics.model_health
#
# DELIBERATELY does NOT expose train_and_deploy / promote to the agent: training
# and promotion remain controlled backend operations (safe, approval-gated).
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from app.mcp.registry import READ_ONLY, ToolDefinition, ToolRegistry
from app.ml.governance import get_governance_engine


class ModelStatusInput(BaseModel):
    model: str = Field("all", description="model name (pfz|risk|productivity|forecast) or 'all'")


class ModelHealthInput(BaseModel):
    model: str = Field(..., description="model name to check")


class ProvenanceInput(BaseModel):
    prediction_id: str = Field(..., description="prediction ledger id")


class ModelMetricsInput(BaseModel):
    model: str = Field(..., description="model name")


def register(registry: ToolRegistry, governance=None) -> None:
    service = governance or get_governance_engine()

    async def model_status(model: str = "all", ctx=None) -> Dict[str, Any]:
        if model == "all":
            return {"status": "live", "models": service.full_status()}
        return {"status": "live", **service.model_health(model)}

    async def model_health(model: str, ctx=None) -> Dict[str, Any]:
        return {"status": "live", **service.model_health(model)}

    async def prediction_provenance(prediction_id: str, ctx=None) -> Dict[str, Any]:
        return {"status": "live", **service.prediction_provenance(prediction_id)}

    async def model_metrics(model: str, ctx=None) -> Dict[str, Any]:
        return {"status": "live", "model": model,
                "metrics": service.metrics(model)}

    tools = [
        ("analytics.model_status", "Model registry & learning status", model_status,
         "Current production model versions, ledger, drift, candidates, "
         "promotion/rollback history and datasets. Read-only; safe for agents."),
        ("analytics.model_health", "Model health probe", model_health,
         "Health of a model: status, version, drift state, performance, data "
         "freshness. Health only; never promotes or mutates."),
        ("analytics.prediction_provenance", "Prediction provenance", prediction_provenance,
         "Full lineage for a prediction ledger id: model, version, features, "
         "matched outcomes. Lets an agent explain WHY rather than invent."),
        ("analytics.model_metrics", "Rolling model metrics", model_metrics,
         "Daily/weekly/monthly MAE / RMSE / precision / recall / F1 / "
         "calibration / bias / coverage for a model."),
    ]
    for name, title, fn, desc in tools:
        registry.register(ToolDefinition(
            name=name, fn=fn, title=title, description=desc,
            group="analytics_governance", safety=READ_ONLY,
            input_model={
                "analytics.model_status": ModelStatusInput,
                "analytics.model_health": ModelHealthInput,
                "analytics.prediction_provenance": ProvenanceInput,
                "analytics.model_metrics": ModelMetricsInput,
            }[name],
        ))