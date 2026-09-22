# Phase 2 - MCP (Model Context Protocol) capability layer.
#
# A thin boundary over the Phase 1 marine data services.  Tools never call
# external APIs directly; they call MarineDataService / GeospatialService /
# SourceRegistry, and every invocation returns the uniform structured envelope
# with status/sources/timestamps/freshness/provenance and a stable error code.
#
# Consumers:
#   - HTTP boundary:  app.mcp.router (/api/v1/mcp)
#   - Native MCP SDK: app.mcp.server.build_mcp_server(registry)
#   - Assembly:       app.mcp.register.build_mcp_component()