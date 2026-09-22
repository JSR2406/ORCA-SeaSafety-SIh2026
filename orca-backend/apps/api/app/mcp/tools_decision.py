# Phase 3 tool group - decision support on top of the fused state, analytics
# and the hybrid RAG knowledge base.
#
# Honest-by-construction: fused state and analytics never fabricate values; the
# knowledge search reports its retrieval mode (hybrid vs fts_only) so callers
# know exactly which pipeline produced the chunks.
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.mcp.registry import DECISION_SUPPORT, READ_ONLY, ToolDefinition, ToolRegistry
from app.services.analytics import AnalyticsService
from app.services.knowledge_rag import KnowledgeRagService
from app.services.marine_capability_client import MarineCapabilityClient
from app.services.marine_fusion import FusedMarineState


class FusedStateInput(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0, description="Latitude of the point of interest")
    lon: float = Field(ge=-180.0, le=180.0, description="Longitude of the point of interest")
    query_run_id: Optional[str] = Field(None, description="Observability run id for evidence")


class KnowledgeSearchInput(BaseModel):
    query: str = Field(min_length=1, max_length=500, description="Free-text knowledge query")
    limit: int = Field(5, ge=1, le=20, description="Max chunks to return")
    ingestion_status: Optional[str] = Field(
        None, description="Restrict to documents with this ingestion status "
                          "e.g. 'pending' or 'completed' (None = all)")


class KnowledgeQueryInput(BaseModel):
    query: str = Field(min_length=1, max_length=500,
                       description="Free-text knowledge question")
    top_k: int = Field(5, ge=1, le=10,
                       description="Max context chunks to retrieve")
    generate: Optional[bool] = Field(
        None, description="Default auto: use the LLM when configured. "
                          "False forces extractive mode.")
    ingestion_status: Optional[str] = Field(
        None, description="Restrict to documents with this ingestion status")


class KnowledgeOverviewInput(BaseModel):
    include_vector_layer: bool = Field(
        True, description="Also verify the pgvector layer (extension, index)")


class DescriptiveStatsInput(BaseModel):
    rows: List[Dict[str, Any]] = Field(description="Observation rows (dicts with numeric fields)")
    fields: List[str] = Field(min_length=1, description="Numeric field names to summarize")


class FavorabilityInput(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    target: str = Field("fishing", pattern="^(fishing|transit)$",
                        description="fishing or transit favorability")
    query_run_id: Optional[str] = Field(None, description="Observability run id for evidence")


class RiskProfileInput(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    active_warnings: Optional[List[Dict[str, Any]]] = Field(
        None, description="Active warnings already fetched by the caller "
                          "(reused; otherwise fetched here)")
    active_restrictions: Optional[List[Dict[str, Any]]] = Field(
        None, description="Active restricted areas already fetched by the "
                          "caller (reused; otherwise fetched here)")
    query_run_id: Optional[str] = Field(None, description="Observability run id for evidence")


class FishingPotentialInput(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    query_run_id: Optional[str] = Field(None, description="Observability run id for evidence")


class ProductivityInput(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    query_run_id: Optional[str] = Field(None, description="Observability run id for evidence")


def _state_from_payload(lat: float, lon: float, payload: Dict[str, Any]) -> FusedMarineState:
    return FusedMarineState(
        lat=lat,
        lon=lon,
        status=payload.get("status") or "unavailable",
        sources=payload.get("sources") or [],
        variables=payload.get("variables") or {},
        providers=payload.get("providers") or {},
        missing=payload.get("missing") or [],
        limitations=payload.get("limitations") or [],
        freshness=payload.get("freshness") or {},
    )


def register(
    registry: ToolRegistry,
    capability: MarineCapabilityClient,
    rag: KnowledgeRagService,
    analytics: AnalyticsService,
) -> None:
    async def get_fused_state(lat: float, lon: float, query_run_id: Optional[str] = None,
                              ctx=None) -> Dict[str, Any]:
        return await capability.fused_state(lat, lon, query_run_id=query_run_id)

    async def knowledge_search(query: str, limit: int = 5,
                               ingestion_status: Optional[str] = None,
                               ctx=None) -> Dict[str, Any]:
        kwargs = {"query": query, "limit": limit}
        if ingestion_status is not None:
            kwargs["ingestion_status"] = ingestion_status
        result = await rag.retrieve(**kwargs)
        return result.to_dict()

    async def knowledge_query(query: str, top_k: int = 5,
                              generate: Optional[bool] = None,
                              ingestion_status: Optional[str] = None,
                              ctx=None) -> Dict[str, Any]:
        from app.services.knowledge_generation import (
            get_knowledge_generation_service,
        )

        service = get_knowledge_generation_service()
        answer = await service.answer(
            query, top_k=top_k, generate=generate,
            ingestion_status=ingestion_status)
        return answer.to_dict()

    async def knowledge_overview(include_vector_layer: bool = True,
                                 ctx=None) -> Dict[str, Any]:
        from app.ingestion.knowledge_ingestion import (
            get_knowledge_ingestion_service,
        )

        overview = await rag.kb_overview()
        overview["pending_documents"] = [
            {"id": d.get("id"), "title": d.get("title"),
             "source_url": d.get("source_url")}
            for d in await get_knowledge_ingestion_service().store.list_documents(
                status="pending", limit=50)
        ]
        if include_vector_layer:
            overview["vector_layer"] = overview.get("vector_layer") or {
                "checked": False, "verified": False}
        return overview

    async def descriptive_stats(rows: List[Dict[str, Any]], fields: List[str],
                                ctx=None) -> Dict[str, Any]:
        return analytics.descriptive_stats(rows, fields)

    async def favorability(lat: float, lon: float, target: str = "fishing",
                           query_run_id: Optional[str] = None,
                           ctx=None) -> Dict[str, Any]:
        payload = await capability.fused_state(lat, lon, query_run_id=query_run_id)
        state = _state_from_payload(lat, lon, payload)
        return analytics.favorability_index(state, target)

    async def risk_profile(
        lat: float, lon: float,
        active_warnings: Optional[List[Dict[str, Any]]] = None,
        active_restrictions: Optional[List[Dict[str, Any]]] = None,
        query_run_id: Optional[str] = None,
        ctx=None,
    ) -> Dict[str, Any]:
        payload = await capability.fused_state(lat, lon, query_run_id=query_run_id)
        state = _state_from_payload(lat, lon, payload)
        if active_warnings is None:
            warnings_env = await capability.active_warnings_at(
                lat, lon, query_run_id=query_run_id)
            active_warnings = list(warnings_env.get("data") or [])
        if active_restrictions is None:
            restrictions_env = await capability.active_restrictions_at(
                lat, lon, query_run_id=query_run_id)
            active_restrictions = list(
                (restrictions_env.get("data") or {}).get("active_restrictions")
                or [])
        profile = analytics.risk_profile(
            state, active_warnings, active_restrictions)
        profile["point"] = {"lat": lat, "lon": lon}
        return profile

    async def fishing_potential(lat: float, lon: float,
                                query_run_id: Optional[str] = None,
                                ctx=None) -> Dict[str, Any]:
        payload = await capability.fused_state(lat, lon, query_run_id=query_run_id)
        state = _state_from_payload(lat, lon, payload)
        result = analytics.fishing_potential(state)
        result["pigment"] = state.variables.get("chlorophyll")
        result["surface_temperature_c"] = state.variables.get("sst_c")
        result["fused_status"] = state.status
        result["freshness"] = state.freshness
        return result

    async def productivity(lat: float, lon: float,
                           query_run_id: Optional[str] = None,
                           ctx=None) -> Dict[str, Any]:
        payload = await capability.fused_state(lat, lon, query_run_id=query_run_id)
        state = _state_from_payload(lat, lon, payload)
        result = analytics.productivity(state)
        result["fused_status"] = state.status
        result["freshness"] = state.freshness
        return result

    registry.register(ToolDefinition(
        name="marine.get_fused_state",
        fn=get_fused_state,
        title="Fused marine state",
        description=("Canonical fused marine state at a point: real ocean + weather "
                     "observations with per-variable provider provenance, confidence, "
                     "missing variables and limitations.  Never fabricates values."),
        group="marine",
        safety=READ_ONLY,
        input_model=FusedStateInput,
    ))
    registry.register(ToolDefinition(
        name="knowledge.search",
        fn=knowledge_search,
        title="Knowledge base search",
        description=("Hybrid retrieval over the curated knowledge base (PostgreSQL FTS "
                     "and, only when an embeddings provider is configured, pgvector). "
                     "Response reports its retrieval mode and verbatim citation excerpts. "
                     "May be restricted to a single ingestion status (e.g. 'pending')."),
        group="knowledge",
        safety=READ_ONLY,
        input_model=KnowledgeSearchInput,
    ))
    registry.register(ToolDefinition(
        name="knowledge.query",
        fn=knowledge_query,
        title="Knowledge base question answering",
        description=("End-to-end RAG: retrieves context chunks and produces a grounded "
                     "answer with [n] citations.  Uses the LLM when configured; otherwise "
                     "returns a verbatim, labelled excerpt (never fabricated prose).  "
                     "Reports its mode and grounding check."),
        group="knowledge",
        safety=READ_ONLY,
        input_model=KnowledgeQueryInput,
    ))
    registry.register(ToolDefinition(
        name="knowledge.overview",
        fn=knowledge_overview,
        title="Knowledge base pipeline overview",
        description=("Pipeline health: documents by ingestion status (including "
                     "pending), chunk/embedding counts and pgvector layer "
                     "verification."),
        group="knowledge",
        safety=READ_ONLY,
        input_model=KnowledgeOverviewInput,
    ))
    registry.register(ToolDefinition(
        name="analytics.descriptive_stats",
        fn=descriptive_stats,
        title="Descriptive marine statistics",
        description=("Descriptive statistics (count/mean/std/min/max) computed from the "
                     "supplied observation rows.  Statistical description only - no "
                     "forecasts or predictions."),
        group="analytics",
        safety=READ_ONLY,
        input_model=DescriptiveStatsInput,
    ))
    registry.register(ToolDefinition(
        name="analytics.favorability",
        fn=favorability,
        title="Fishing / transit favorability",
        description=("Transparent favorability index over real fused-state variables with "
                     "per-variable weights and rationale.  Requires half or more of the "
                     "target's inputs; otherwise reports missing inputs instead of a score."),
        group="analytics",
        safety=DECISION_SUPPORT,
        input_model=FavorabilityInput,
    ))
    registry.register(ToolDefinition(
        name="analytics.risk_profile",
        fn=risk_profile,
        title="Marine risk profile",
        description=("Transparent per-variable risk profile (Risk Engine over real "
                     "fused-state values) combined with active warnings and restricted "
                     "areas.  Hard constraints always override environmental scores; "
                     "the profile never fabricates values and is advisory only."),
        group="analytics",
        safety=DECISION_SUPPORT,
        input_model=RiskProfileInput,
    ))
    registry.register(ToolDefinition(
        name="analytics.fishing_potential",
        fn=fishing_potential,
        title="Fishing potential at a point",
        description=("Transparent satellite-inferred fishing potential at a point from "
                     "the documented favorability bands (more == beneficial SST and "
                     "chlorophyll), with per-variable contributions and data caveats.  "
                     "Descriptive only - never a catch forecast."),
        group="analytics",
        safety=DECISION_SUPPORT,
        input_model=FishingPotentialInput,
    ))
    registry.register(ToolDefinition(
        name="analytics.productivity",
        fn=productivity,
        title="Primary productivity index",
        description=("SRP-style productivity index from chlorophyll + SST (+ upwelling "
                     "proxy) over real fused-state data, mapped to oligotrophic / moderate "
                     " / productive / highly_productive.  Satellite-inferred, not a "
                     "measurement."),
        group="analytics",
        safety=DECISION_SUPPORT,
        input_model=ProductivityInput,
    ))