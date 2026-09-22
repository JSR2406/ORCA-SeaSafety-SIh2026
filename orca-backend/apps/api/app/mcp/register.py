# Assembly of the Phase 2 MCP capability layer from the Phase 1 services.
# A single source of truth for the tool registry used by both the HTTP
# /api/v1/mcp boundary and the native MCP SDK server.
from app.config import settings
from app.datasources.registry import build_registry, SourceRegistry
from app.db.client import get_session
from app.services.geospatial_service import GeospatialService
from app.services.marine_data_service import MarineDataService

from app.mcp import (
    tools_argo,
    tools_decision,
    tools_geospatial,
    tools_knowledge,
    tools_marine,
    tools_restriction,
    tools_safety,
    tools_weather,
)
from app.mcp.registry import ToolRegistry


def build_services() -> tuple[SourceRegistry, MarineDataService, GeospatialService]:
    sources = build_registry(settings)
    marine = MarineDataService(settings, sources, get_session)
    geo = GeospatialService(settings, marine)
    return sources, marine, geo


def build_tool_registry(
    sources: SourceRegistry,
    marine: MarineDataService,
    geo: GeospatialService,
    evidence=None,
) -> ToolRegistry:
    from app.services.analytics import AnalyticsService
    from app.services.knowledge_rag import KnowledgeRagService
    from app.services.marine_capability_client import MarineCapabilityClient

    registry = ToolRegistry(evidence=evidence)
    tools_marine.register(registry, marine)
    tools_weather.register(registry, marine)
    tools_geospatial.register(registry, geo)

    from app.services.argo_service import ArgoService
    argo = ArgoService(get_session)
    tools_argo.register(registry, argo)

    from app.services.restriction_refresh import DynamicRestrictionService
    dynamic_service = DynamicRestrictionService()

    tools_restriction.register(registry, marine, geo, dynamic=dynamic_service)
    tools_safety.register(registry, marine, geo)
    tools_knowledge.register(registry, sources, marine)
    tools_decision.register(
        registry,
        capability=MarineCapabilityClient(marine=marine, geo=geo, evidence=evidence),
        rag=KnowledgeRagService(),
        analytics=AnalyticsService(),
    )

    # Phase 12 - production ML models (feature store + model service + drift).
    from app.mcp import tools_analytics_model
    tools_analytics_model.register(registry)

    # Phase 13 - ML governance / provenance (read-only; safe for agents).
    from app.mcp import tools_ml_governance
    tools_ml_governance.register(registry)
    return registry


def build_mcp_component() -> dict:
    """Return a ready-to-use component dict for the FastAPI app."""
    from app.services.evidence_service import MarineEvidenceService

    sources, marine, geo = build_services()
    registry = build_tool_registry(sources, marine, geo, MarineEvidenceService())
    return {
        "sources": sources,
        "marine_service": marine,
        "geospatial_service": geo,
        "tool_registry": registry,
    }