# Tool group: knowledge - catalog and health of configured marine sources.
# These tools describe capability/config and adjudicated source freshness.
from app.mcp.registry import READ_ONLY, ToolDefinition, ToolRegistry
from app.datasources.registry import SourceRegistry
from app.services.marine_data_service import MarineDataService


def register(registry: ToolRegistry, sources: SourceRegistry, marine: MarineDataService) -> None:
    async def source_catalog(ctx=None):
        return {"sources": [info.model_dump(mode="json") for info in sources.get_info()]}

    async def source_status(ctx=None):
        statuses = await marine.sources_status()
        return {"sources": [s.model_dump(mode="json") for s in statuses]}

    registry.register(ToolDefinition(
        name="knowledge.source_catalog",
        fn=source_catalog,
        title="Marine source catalog",
        description="List configured marine data sources and their data products.",
        group="knowledge",
        safety=READ_ONLY,
        input_model=None,
    ))
    registry.register(ToolDefinition(
        name="knowledge.source_status",
        fn=source_status,
        title="Marine source status",
        description="Adjudicated freshness/availability status of each configured marine source.",
        group="knowledge",
        safety=READ_ONLY,
        input_model=None,
    ))