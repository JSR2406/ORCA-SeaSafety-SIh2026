# Query Runs Router
# Query run details endpoint

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.client import get_db_session
from app.db.models import QueryRun, EvidenceRecord, Narrative, ScenarioRun
from app.services.evidence_service import get_marine_evidence_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/query-runs", tags=["query-runs"])


@router.get("/{query_run_id}/provenance")
async def get_query_run_provenance(query_run_id: str):
    """Replayable evidence/provenance trail for an orchestrated run.

    Rows are written best-effort by the orchestrator after every run, so a
    response can be re-validated offline without re-running the agents.
    """
    rows = await get_marine_evidence_service().list_for_run(query_run_id)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No evidence rows recorded for this query run")
    return {
        "query_run_id": query_run_id,
        "count": len(rows),
        "evidence_rows": rows,
    }


@router.get("/{query_run_id}")
async def get_query_run(
    query_run_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Get detailed query run information."""
    stmt = select(QueryRun).where(QueryRun.id == query_run_id)
    result = await session.execute(stmt)
    query_run = result.scalar_one_or_none()
    
    if not query_run:
        raise HTTPException(status_code=404, detail="Query run not found")
    
    # Get evidence
    ev_stmt = select(EvidenceRecord).where(EvidenceRecord.query_run_id == query_run_id)
    ev_result = await session.execute(ev_stmt)
    evidence = ev_result.scalar_one_or_none()
    
    # Get narratives
    nar_stmt = select(Narrative).where(Narrative.query_run_id == query_run_id)
    nar_result = await session.execute(nar_stmt)
    narratives = nar_result.scalars().all()
    
    # Get scenarios
    scn_stmt = select(ScenarioRun).where(ScenarioRun.query_run_id == query_run_id)
    scn_result = await session.execute(scn_stmt)
    scenarios = scn_result.scalars().all()
    
    return {
        "id": query_run.id,
        "session_id": query_run.session_id,
        "user_input": query_run.user_input,
        "detected_language": query_run.detected_language,
        "normalized_intent": query_run.normalized_intent,
        "structured_query": query_run.structured_query,
        "tool_calls": query_run.tool_calls,
        "execution_status": query_run.execution_status,
        "created_at": query_run.created_at.isoformat() if query_run.created_at else None,
        "evidence": {
            "float_ids": evidence.float_ids,
            "profile_count": evidence.profile_count,
            "observation_count": evidence.observation_count,
            "region": evidence.region,
            "depth_range": evidence.depth_range,
            "time_range": evidence.time_range,
            "filters": evidence.filters,
            "data_freshness": evidence.data_freshness,
            "confidence_label": evidence.confidence_label,
            "confidence_components": evidence.confidence_components,
            "limitations": evidence.limitations,
            "source_identifiers": evidence.source_identifiers,
            "verified": evidence.verified,
            "verification_errors": evidence.verification_errors,
        } if evidence else None,
        "narratives": [
            {
                "id": n.id,
                "title": n.title,
                "narrative_text": n.narrative_text,
                "numeric_claims": n.numeric_claims,
                "verified": n.verified,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in narratives
        ],
        "scenarios": [
            {
                "id": s.id,
                "variable": s.variable,
                "region": s.region,
                "baseline": s.baseline,
                "trend_window": s.trend_window,
                "projection_horizon": s.projection_horizon,
                "model_name": s.model_name,
                "assumptions": s.assumptions,
                "uncertainty_method": s.uncertainty_method,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in scenarios
        ],
    }