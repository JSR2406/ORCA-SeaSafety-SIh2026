# Scenario Router
# What-if scenario projection endpoints

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from datetime import datetime, timedelta

from app.config import settings
from app.schemas.scenario import (
    ScenarioType, ScenarioParameter, ScenarioRequest,
    ScenarioResult, ScenarioComparison,
    AlertSeverity, AlertStatus, AlertRule, AlertEvent,
)
from app.schemas.route import RouteAnalysisRequest, RouteAnalysisResponse, EnvironmentalConditions
from app.services.risk_engine import get_risk_engine
from app.services.scenario_agent import get_scenario_agent
from app.agents import ExecutionContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/scenarios", tags=["scenarios"])


# Request/Response models
class CreateScenarioRequest(BaseModel):
    scenario_type: str
    base_query: Dict[str, Any]
    parameters: List[Dict[str, Any]]
    name: Optional[str] = None
    description: Optional[str] = None


class ScenarioResponse(BaseModel):
    scenario_id: str
    scenario_type: str
    name: Optional[str]
    created_at: str
    projected_risk_score: float
    projected_time_hours: Optional[float]
    projected_fuel_consumption: Optional[float]
    risk_delta: float
    time_delta_hours: Optional[float]
    fuel_delta: Optional[float]
    projected_conditions: Dict[str, Any]
    confidence: float
    uncertainty_factors: List[str]
    recommendations: List[str]


class CompareScenariosRequest(BaseModel):
    base_scenario_id: str
    alternative_scenario_ids: List[str]


class CompareScenariosResponse(BaseModel):
    comparison_id: str
    base_scenario: dict
    alternative_scenarios: List[dict]
    best_scenario_id: str
    worst_scenario_id: str
    key_differences: List[str]
    tradeoffs: List[Dict[str, Any]]


@router.post("/create", response_model=ScenarioResponse)
async def create_scenario(
    request: CreateScenarioRequest,
    background_tasks: BackgroundTasks,
):
    """Create a what-if scenario projection."""
    try:
        # Validate scenario type
        try:
            scenario_type = ScenarioType(request.scenario_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid scenario type: {request.scenario_type}")
        
        # Create scenario request
        scenario_req = ScenarioRequest(
            scenario_type=scenario_type,
            base_query=request.base_query,
            parameters=[ScenarioParameter(**p) for p in request.parameters],
            name=request.name,
            description=request.description,
        )
        
        # Get scenario agent and execute
        scenario_agent = get_scenario_agent()
        
        # Build execution context
        context = ExecutionContext(
            query_run_id=f"scenario_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            user_query=request.name or f"Scenario: {request.scenario_type}",
            structured_query={
                "scenario_type": request.scenario_type,
                "base_request": request.base_query,
            } | {p["name"]: p["value"] for p in request.parameters},
            detected_language="en-IN",
            session_id="scenario_session",
        )
        
        # Execute scenario
        results = await scenario_agent.execute(context)
        
        # Get risk assessment from results
        risk_result = results[0] if results else {}
        risk_assessment = risk_result.get("risk_assessment", {})
        
        # Build response
        scenario_id = f"scn_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{hash(str(request.base_query)) % 10000:04d}"
        
        response = ScenarioResponse(
            scenario_id=scenario_id,
            scenario_type=request.scenario_type,
            name=request.name,
            created_at=datetime.utcnow().isoformat(),
            projected_risk_score=risk_assessment.get("overall_score", 0.3),
            projected_time_hours=risk_result.get("total_estimated_time_hours"),
            projected_fuel_consumption=None,
            risk_delta=risk_assessment.get("overall_score", 0.3) - 0.2,  # Simplified delta
            time_delta_hours=None,
            fuel_delta=None,
            projected_conditions=risk_result.get("environmental_conditions", {}),
            confidence=risk_assessment.get("confidence", 0.8),
            uncertainty_factors=risk_assessment.get("missing_data", []),
            recommendations=risk_assessment.get("recommendations", []),
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Scenario creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Scenario creation failed: {str(e)}")


@router.post("/project", response_model=ScenarioResponse)
async def project_scenario(
    request: CreateScenarioRequest,
    background_tasks: BackgroundTasks,
):
    """Legacy alias for POST /api/v1/scenarios/create (frontend compatibility)."""
    return await create_scenario(request, background_tasks)


@router.post("/compare", response_model=CompareScenariosResponse)
async def compare_scenarios(request: CompareScenariosRequest):
    """Compare multiple scenarios."""
    try:
        base = get_scenario_result(request.base_scenario_id)
        if not base:
            raise HTTPException(status_code=404, detail=f"Base scenario not found: {request.base_scenario_id}")
        
        alternatives = []
        for alt_id in request.alternative_scenario_ids:
            alt = get_scenario_result(alt_id)
            if not alt:
                raise HTTPException(status_code=404, detail=f"Alternative scenario not found: {alt_id}")
            alternatives.append(alt)
        
        # Build comparison
        comparison_id = f"cmp_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        # Find best/worst by risk score
        all_scenarios = [base] + alternatives
        best = min(all_scenarios, key=lambda s: s.overall_score if hasattr(s, 'overall_score') else s.projected_risk_score)
        worst = max(all_scenarios, key=lambda s: s.overall_score if hasattr(s, 'overall_score') else s.projected_risk_score)
        
        key_differences = [
            f"Risk range: {best.projected_risk_score:.2f} - {worst.projected_risk_score:.2f}",
            f"Time range: {min(s.projected_time_hours for s in all_scenarios if s.projected_time_hours):.1f}h - {max(s.projected_time_hours for s in all_scenarios if s.projected_time_hours):.1f}h",
        ]
        
        tradeoffs = [
            {"factor": "Risk", "best": best.scenario_id, "worst": worst.scenario_id},
            {"factor": "Time", "best": min(all_scenarios, key=lambda s: s.projected_time_hours or 999).scenario_id if any(s.projected_time_hours for s in all_scenarios) else "N/A", "worst": max(all_scenarios, key=lambda s: s.projected_time_hours or 0).scenario_id if any(s.projected_time_hours for s in all_scenarios) else "N/A"},
        ]
        
        return CompareScenariosResponse(
            comparison_id=f"cmp_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            base_scenario=base.model_dump(),
            alternative_scenarios=[a.model_dump() for a in alternatives],
            best_scenario_id=best.scenario_id,
            worst_scenario_id=worst.scenario_id,
            key_differences=key_differences,
            tradeoffs=tradeoffs,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Scenario comparison failed: {e}")
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")


@router.get("/{scenario_id}")
async def get_scenario(scenario_id: str):
    """Get a scenario by ID."""
    scenario = get_scenario_result(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario not found: {scenario_id}")
    return scenario


@router.get("/")
async def list_scenarios(limit: int = 50):
    """List recent scenarios."""
    # Would query database in production
    return {"scenarios": [], "total": 0}


# --- Alert Endpoints ---

class CreateAlertRuleRequest(BaseModel):
    name: str
    description: str
    hazard_types: Optional[List[str]] = None
    severity_threshold: Optional[str] = None
    region: Optional[Dict[str, float]] = None
    route_id: Optional[str] = None
    active_from: Optional[str] = None
    active_to: Optional[str] = None
    check_interval_minutes: int = 60
    notify_channels: List[str] = []
    auto_resolve: bool = True


@router.post("/alerts/rules", response_model=AlertRule)
async def create_alert_rule_endpoint(request: CreateAlertRuleRequest):
    """Create an alert rule."""
    rule = AlertRule(
        rule_id=f"rule_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        name=request.name,
        description=request.description,
        hazard_types=request.hazard_types,
        severity_threshold=request.severity_threshold,
        region=request.region,
        route_id=request.route_id,
        active_from=datetime.fromisoformat(request.active_from) if request.active_from else None,
        active_to=datetime.fromisoformat(request.active_to) if request.active_to else None,
        check_interval_minutes=request.check_interval_minutes,
        notify_channels=request.notify_channels,
        auto_resolve=request.auto_resolve,
        created_by="api_user",
    )
    create_alert_rule(rule)
    return rule


@router.get("/alerts/rules")
async def list_alert_rules_endpoint(enabled_only: bool = True):
    rules = list_alert_rules(enabled_only)
    return {"rules": [r.model_dump() for r in rules]}


@router.get("/alerts/rules/{rule_id}")
async def get_alert_rule_endpoint(rule_id: str):
    rule = get_alert_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Alert rule not found: {rule_id}")
    return rule


@router.delete("/alerts/rules/{rule_id}")
async def delete_alert_rule_endpoint(rule_id: str):
    rule = get_alert_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Alert rule not found: {rule_id}")
    _alert_rules.pop(rule_id, None)
    return {"status": "deleted", "rule_id": rule_id}


@router.get("/alerts/events")
async def list_alert_events_endpoint(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100,
):
    events = list_alert_events(
        status=AlertStatus(status) if status else None,
        severity=severity,
        limit=limit,
    )
    return {"events": [e.model_dump() for e in events]}


@router.get("/alerts/events/{event_id}")
async def get_alert_event_endpoint(event_id: str):
    event = get_alert_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Alert event not found: {event_id}")
    return event


@router.post("/alerts/events/{event_id}/acknowledge")
async def acknowledge_alert_endpoint(event_id: str, user: str):
    event = acknowledge_alert(event_id, user)
    if not event:
        raise HTTPException(status_code=404, detail=f"Alert event not found: {event_id}")
    return event


@router.post("/alerts/events/{event_id}/resolve")
async def resolve_alert_endpoint(event_id: str, user: str, notes: Optional[str] = None):
    event = resolve_alert(event_id, user, notes)
    if not event:
        raise HTTPException(status_code=404, detail=f"Alert event not found: {event_id}")
    return event


@router.post("/alerts/check")
async def check_alerts(background_tasks: BackgroundTasks):
    """Manually trigger alert checking."""
    # In production, this would be a scheduled task
    background_tasks.add_task(_check_all_alert_rules)
    return {"status": "check_triggered", "timestamp": datetime.utcnow().isoformat()}


async def _check_all_alert_rules():
    """Background task to check all alert rules."""
    rules = list_alert_rules(enabled_only=True)
    for rule in rules:
        try:
            await _evaluate_alert_rule(rule)
        except Exception as e:
            logger.error(f"Failed to evaluate rule {rule.rule_id}: {e}")


async def _evaluate_alert_rule(rule: AlertRule):
    """Evaluate a single alert rule."""
    # This would integrate with hazard detection, route monitoring, etc.
    # For now, just log the evaluation
    logger.info(f"Evaluating alert rule: {rule.rule_id} - {rule.name}")
    # Implementation would:
    # 1. Query hazard data for the rule's region/route
    # 2. Check if conditions exceed thresholds
    # 3. Create alert events if triggered
    pass