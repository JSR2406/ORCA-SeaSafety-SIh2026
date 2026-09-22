# Phase 13 - ML governance & provenance API.
#
#   GET /api/v1/ml/models/{model_id}               - model + versions + lineage
#   GET /api/v1/ml/models/{model_id}/versions      - all versions (governed)
#   GET /api/v1/ml/models/{model_id}/metrics       - rolling metrics
#   GET /api/v1/ml/models/{model_id}/health        - model health probe
#   GET /api/v1/ml/predictions/{prediction_id}     - a prediction record
#   GET /api/v1/ml/predictions/{prediction_id}/provenance - full lineage
#   GET /api/v1/ml/dashboard                        - ML-ops dashboard contract
#
# This router NEVER exposes chain-of-thought, internal prompts, DB queries,
# credentials, or raw internal tool arguments.  It never exposes promote /
# train / deploy to callers: those remain controlled backend operations.
from typing import Any, Dict, Optional

import structlog
from fastapi import APIRouter, HTTPException, Query

from app.ml.governance import get_governance_engine

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/ml", tags=["ml-governance"])


def _engine():
    return get_governance_engine()


@router.get("/models/{model_id}")
async def get_model(model_id: str) -> Dict[str, Any]:
    try:
        mg = _engine()
        versions = [v.to_dict() for v in mg.registry.list(model_id)]
    except Exception:  # noqa: BLE001 - never leak internals
        logger.exception("ml_model_error")
        raise HTTPException(status_code=500, detail="Failed to read model")
    if not versions:
        raise HTTPException(status_code=404, detail="Model not found")
    return {
        "model_id": model_id,
        "production_version": mg.registry.production.get(model_id),
        "versions": versions,
        "lineage": {
            "data": "prediction ledger + ground truth + historical features",
            "feature_version": mg.feature_version,
            "model": model_id,
            "prediction": "ledger",
            "decision": "agent / risk engine (ML advisory only)",
            "observed_outcome": "ground truth store",
        },
    }


@router.get("/models/{model_id}/versions")
async def model_versions(model_id: str) -> Dict[str, Any]:
    try:
        mg = _engine()
        versions = [v.to_dict() for v in mg.registry.list(model_id)]
    except Exception:  # noqa: BLE001
        logger.exception("ml_model_versions_error")
        raise HTTPException(status_code=500, detail="Failed to read versions")
    if not versions:
        raise HTTPException(status_code=404,
                            detail="Model has no registered versions")
    return {"model_id": model_id, "versions": versions}


@router.get("/models/{model_id}/metrics")
async def model_metrics(model_id: str) -> Dict[str, Any]:
    try:
        mg = _engine()
        metrics = mg.metrics(model_id)
    except Exception:  # noqa: BLE001
        logger.exception("ml_model_metrics_error")
        raise HTTPException(status_code=500, detail="Failed to read metrics")
    return {"model_id": model_id, "metrics": metrics}


@router.get("/models/{model_id}/health")
async def model_health(model_id: str) -> Dict[str, Any]:
    try:
        mg = _engine()
        health = mg.model_health(model_id)
    except Exception:  # noqa: BLE001
        logger.exception("ml_model_health_error")
        raise HTTPException(status_code=500, detail="Failed to read health")
    return {"health": health}


@router.get("/predictions/{prediction_id}")
async def get_prediction(prediction_id: str) -> Dict[str, Any]:
    try:
        rec = _engine().ledger.get_prediction(prediction_id)
    except Exception:  # noqa: BLE001
        logger.exception("ml_prediction_error")
        raise HTTPException(status_code=500, detail="Failed to read prediction")
    if rec is None:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return {"prediction": rec.to_dict()}


@router.get("/predictions/{prediction_id}/provenance")
async def prediction_provenance(prediction_id: str) -> Dict[str, Any]:
    try:
        result = _engine().prediction_provenance(prediction_id)
    except Exception:  # noqa: BLE001
        logger.exception("ml_provenance_error")
        raise HTTPException(status_code=500, detail="Failed to read provenance")
    if not result.get("found"):
        raise HTTPException(status_code=404, detail="Prediction not found")
    return result


@router.get("/dashboard")
async def dashboard() -> Dict[str, Any]:
    """Operational dashboard contract for a future ML-ops UI (Phase 13 item 28).

    Returns: models, versions, health, metrics, drift, training jobs, candidate
    models, promotion history, rollback history — enough for the frontend team
    to build the dashboard independently.
    """
    try:
        mg = _engine()
        models = {}
        healths = {}
        from app.ml.models import known_models
        for name in known_models():
            models[name] = [v.to_dict() for v in mg.registry.list(name)]
            healths[name] = mg.model_health(name)
        from datetime import datetime, timezone
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "models": models,
            "health": healths,
            "metrics": mg.metrics(),
            "drift": mg.drift.status(),
            "training_jobs": [c for c in mg.candidates.values()
                              if c.get("status") in ("TRAINING", "VALIDATED")],
            "candidate_models": [c for c in mg.candidates.values()
                                 if c.get("status") == "VALIDATED"],
            "promotion_history": mg.promotion_history,
            "rollback_history": mg.rollback_history,
        }
    except Exception:  # noqa: BLE001
        logger.exception("ml_dashboard_error")
        raise HTTPException(status_code=500, detail="Failed to build dashboard")