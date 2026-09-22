# Chat Router
# Main chat endpoint integrating planner, executor, verifier, confidence

import logging
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.db.client import get_db_session
from app.db.models import QueryRun, EvidenceRecord
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.query import StructuredQuery, Intent
from app.schemas.evidence import EvidenceRecord as EvidenceSchema, ConfidenceScore, ConfidenceComponents
from app.services.query_planner import get_query_planner
from app.services.query_executor import QueryExecutor
from app.services.verifier import Verifier, create_claims_from_result
from app.services.confidence import ConfidenceCalculator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
):
    """Main chat endpoint: NL question → structured query → execution → verified response."""
    query_run_id = str(uuid.uuid4())
    session_id = request.session_id or str(uuid.uuid4())

    logger.info(f"Chat request: {request.message[:100]}... (session: {session_id})")

    # 1. Plan structured query
    try:
        planner = get_query_planner()
    except ValueError as e:
        # LLM not configured - honest degradation
        return ChatResponse(
            query_run_id=query_run_id,
            answer="",
            language=request.language or "en",
            structured_query=None,
            status="unavailable",
            clarification_question=None,
            partial_query=None,
            visualizations=None,
            evidence=None,
            audio_url=None,
        )

    plan_result = await planner.plan_query(request.message, request.language)

    if plan_result.status == "needs_clarification":
        # Save query run with clarification status
        query_run = QueryRun(
            session_id=session_id,
            user_input=request.message,
            detected_language=plan_result.language.value,
            normalized_intent=plan_result.intent.value,
            structured_query=plan_result.query.model_dump(),
            execution_status="needs_clarification",
        )
        session.add(query_run)
        await session.commit()

        return ChatResponse(
            query_run_id=query_run_id,
            answer="",
            language=plan_result.language.value,
            structured_query=plan_result.query,
            status="needs_clarification",
            clarification_question=plan_result.clarification_question,
            partial_query=plan_result.query,
        )

    if plan_result.status == "unsupported":
        raise HTTPException(status_code=400, detail="Query type not supported")

    structured_query = plan_result.query

    # 2. Execute query
    executor = QueryExecutor(session)
    try:
        query_result = await executor.execute(structured_query)
    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Query execution failed: {str(e)}")

    # 3. Build evidence record
    evidence = build_evidence_record(structured_query, query_result)

    # 4. Verify numeric claims
    claims = create_claims_from_result(query_result, evidence)
    verifier = Verifier(evidence, query_result)
    verification_result = verifier.verify_all(claims)

    # Update evidence with verification status
    evidence.verified = verification_result.all_verified
    evidence.verification_errors = [f"{c.claim}: {c.value}" for c in verification_result.failed_claims]

    # 5. Calculate confidence
    confidence_calc = ConfidenceCalculator(evidence.model_dump(), query_result)
    confidence = confidence_calc.calculate()
    evidence.confidence = confidence

    # 6. Generate answer text
    answer = generate_answer(structured_query, query_result, evidence, verification_result)

    # 7. Create visualizations
    visualizations = create_visualizations(structured_query, query_result, evidence)

    # 8. Save query run and evidence
    query_run = QueryRun(
        session_id=session_id,
        user_input=request.message,
        detected_language=plan_result.language.value,
        normalized_intent=plan_result.intent.value,
        structured_query=structured_query.model_dump(),
        tool_calls=[{"tool": "executor", "params": structured_query.model_dump()}],
        execution_status="success",
    )
    session.add(query_run)
    await session.flush()

    evidence_record = EvidenceRecord(
        query_run_id=query_run.id,
        float_ids=evidence.float_ids,
        profile_count=evidence.profile_count,
        observation_count=evidence.observation_count,
        region=evidence.region.model_dump(),
        depth_range=evidence.depth_range_m.model_dump() if evidence.depth_range_m else None,
        time_range=evidence.time_range.model_dump(),
        filters=evidence.quality_filters.model_dump(),
        data_freshness=evidence.data_freshness.model_dump(),
        confidence_label=evidence.confidence.label.value,
        confidence_components=evidence.confidence.components.model_dump(),
        limitations=evidence.limitations,
        source_identifiers=evidence.source_identifiers.model_dump(),
        verified=evidence.verified,
        verification_errors=evidence.verification_errors,
    )
    session.add(evidence_record)
    await session.commit()

    query_run_id = str(query_run.id)
    logger.info(f"Chat completed: {query_run_id}, verified={evidence.verified}, confidence={confidence.label}")

    return ChatResponse(
        query_run_id=query_run_id,
        answer=answer,
        language=plan_result.language.value,
        structured_query=structured_query,
        visualizations=visualizations,
        evidence=evidence,
        status="success",
    )


def build_evidence_record(query: StructuredQuery, result: dict) -> EvidenceSchema:
    """Build evidence record from query and results."""
    metadata = result.get("metadata", {})
    profiles = result.get("profiles", [])

    # Float IDs
    float_ids = metadata.get("float_ids", [])

    # Region info
    region_info = {"type": "unknown"}
    if query.region:
        region_info = query.region.model_dump()

    # Time range
    time_range = {"start": "", "end": ""}
    if metadata.get("time_range"):
        time_range = metadata["time_range"]
    elif query.time_range:
        time_range = query.time_range.model_dump()

    # Depth range
    depth_range = None
    if metadata.get("depth_range_m"):
        depth_range = metadata["depth_range_m"]
    elif query.depth_range_m:
        depth_range = query.depth_range_m.model_dump()

    # Data freshness
    data_freshness = {
        "latest_profile": time_range.get("end", datetime.utcnow().isoformat()),
        "days_old": 0,
        "source": "argo_realtime",
    }

    # Quality filters
    quality_filters = {
        "filters": [query.quality_filter.value],
        "description": f"QC filter: {query.quality_filter.value} (flags 1=good, 2=probably good)",
    }

    # Source identifiers
    source_identifiers = {
        "dataset": "argo_gdac",
        "snapshot": datetime.utcnow().strftime("%Y-%m-%d"),
        "doi": "10.17882/42182",
        "source_urls": ["https://data-argo.ifremer.fr/argo"],
    }

    # Query steps
    query_steps = [
        {"step": 1, "tool": "search_profiles", "params": query.model_dump(), "result_count": metadata.get("profile_count", 0)},
    ]

    return EvidenceSchema(
        float_ids=float_ids,
        profile_count=metadata.get("profile_count", 0),
        observation_count=metadata.get("observation_count", 0),
        region=region_info,
        depth_range_m=depth_range,
        time_range=time_range,
        quality_filters=quality_filters,
        data_freshness=data_freshness,
        confidence=ConfidenceScore(
            label="medium",
            score=0.5,
            components=ConfidenceComponents(
                spatial_coverage=0.5,
                temporal_freshness=0.5,
                sample_density=0.5,
                measurement_quality=0.5,
                method_stability=0.5,
            ),
            explanation="Initial confidence - will be calculated",
            limitations=[],
        ),
        query_steps=query_steps,
        limitations=[],
        source_identifiers=source_identifiers,
    )


def generate_answer(
    query: StructuredQuery,
    result: dict,
    evidence: EvidenceSchema,
    verification_result
) -> str:
    """Generate human-readable answer from query results."""
    metadata = result.get("metadata", {})
    profiles = result.get("profiles", [])

    float_count = metadata.get("float_count", 0)
    profile_count = metadata.get("profile_count", 0)
    obs_count = metadata.get("observation_count", 0)

    if query.intent == Intent.PROFILE_SEARCH:
        var_names = ", ".join([v.value for v in (query.variables or ["temperature"])])
        region_name = "the requested region"
        if query.region and hasattr(query.region, 'name'):
            region_name = query.region.name.replace("_", " ").title()

        time_str = ""
        if query.time_range:
            time_str = f" during {query.time_range.start[:7]}"

        answer = (
            f"Found **{profile_count} profiles** from **{float_count} floats** "
            f"in {region_name}{time_str}. "
            f"Variables: {var_names}. "
            f"Total observations: {obs_count:,}."
        )

        # Add temperature summary if available
        if profiles:
            temps = []
            for p in profiles:
                for obs in p.get("observations", []):
                    if obs.get("temperature_c") is not None:
                        temps.append(obs["temperature_c"])
            if temps:
                answer += f" Temperature range: **{min(temps):.1f}–{max(temps):.1f}°C** (mean: {sum(temps)/len(temps):.1f}°C)."

        if not verification_result.all_verified:
            answer += " ⚠️ *Some numeric claims could not be fully verified.*"

        return answer

    elif query.intent == Intent.TIMESERIES_SUMMARY:
        return f"Time series analysis for {query.variables[0].value if query.variables else 'variable'} completed with {profile_count} profiles."

    elif query.intent == Intent.DEPTH_PROFILE_SUMMARY:
        return f"Depth profile summary generated for {profile_count} profiles across {float_count} floats."

    else:
        return f"Query executed successfully. Found {profile_count} profiles from {float_count} floats."


def create_visualizations(query: StructuredQuery, result: dict, evidence: EvidenceSchema):
    """Create visualization data for frontend."""
    profiles = result.get("profiles", [])
    metadata = result.get("metadata", {})

    charts = []
    map_data = None

    # Map data - float locations
    if profiles:
        features = []
        for p in profiles:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [p["longitude"], p["latitude"]]
                },
                "properties": {
                    "float_id": p["profile_id"],
                    "platform_number": p["platform_number"],
                    "cycle_number": p["cycle_number"],
                    "profile_time": p["profile_time"],
                    "latitude": p["latitude"],
                    "longitude": p["longitude"],
                    "temperature_c": p["observations"][0].get("temperature_c") if p.get("observations") else None,
                    "salinity_psu": p["observations"][0].get("salinity_psu") if p.get("observations") else None,
                    "depth_m": max([o.get("depth_m", 0) for o in p.get("observations", [])], default=0),
                }
            })

        # Compute center
        lats = [f["geometry"]["coordinates"][1] for f in features]
        lons = [f["geometry"]["coordinates"][0] for f in features]
        center = [sum(lons)/len(lons), sum(lats)/len(lats)]

        map_data = {
            "type": "geojson",
            "features": features,
            "center": center,
            "zoom": 4,
        }

    # Depth profile chart
    if query.intent in [Intent.PROFILE_SEARCH, Intent.DEPTH_PROFILE_SUMMARY]:
        # Aggregate by depth bins
        depth_bins = {}
        for p in profiles:
            for obs in p.get("observations", []):
                depth = obs.get("depth_m")
                temp = obs.get("temperature_c")
                if depth is not None and temp is not None:
                    bin_key = int(depth / 10) * 10
                    if bin_key not in depth_bins:
                        depth_bins[bin_key] = []
                    depth_bins[bin_key].append(temp)

        chart_data = []
        for depth in sorted(depth_bins.keys()):
            temps = depth_bins[depth]
            chart_data.append({
                "x": sum(temps) / len(temps),
                "y": depth + 5,  # bin center
                "sample_count": len(temps),
            })

        if chart_data:
            charts.append({
                "type": "depth_profile",
                "title": f"Temperature vs Depth ({metadata.get('float_count', 0)} floats)",
                "data": chart_data,
                "config": {
                    "xAxis": {"label": "Temperature (°C)", "unit": "°C"},
                    "yAxis": {"label": "Depth (m)", "unit": "m"},
                },
                "metadata": {
                    "variable": "temperature",
                    "region": str(query.region),
                    "time_range": f"{metadata.get('time_range', {}).get('start', '')} to {metadata.get('time_range', {}).get('end', '')}",
                    "sample_count": sum(d["sample_count"] for d in chart_data),
                    "float_count": metadata.get("float_count", 0),
                    "data_source": "ARGO",
                }
            })

    # Time series chart
    if query.intent == Intent.TIMESERIES_SUMMARY and "data" in result:
        ts_data = result["data"]
        chart_data = [
            {
                "x": d["date"],
                "y": d["mean"],
                "sample_count": d["count"],
            }
            for d in ts_data if d.get("mean") is not None
        ]
        if chart_data:
            charts.append({
                "type": "time_series",
                "title": f"{query.variables[0].value if query.variables else 'Variable'} Time Series",
                "data": chart_data,
                "config": {
                    "xAxis": {"label": "Date", "type": "time"},
                    "yAxis": {"label": query.variables[0].value if query.variables else "Value"},
                },
                "metadata": {
                    "variable": query.variables[0].value if query.variables else "unknown",
                    "region": str(query.region),
                    "sample_count": len(chart_data),
                    "float_count": metadata.get("float_count", 0),
                    "data_source": "ARGO",
                }
            })

    visualizations = {"charts": charts}
    if map_data:
        visualizations["map"] = map_data

    return visualizations