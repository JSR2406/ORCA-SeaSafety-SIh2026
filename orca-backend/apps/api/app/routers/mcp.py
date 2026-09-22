# Re-export the MCP capability-layer HTTP router under app.routers so main.py
# can include it uniformly with the other router modules.
from app.mcp.router import router

__all__ = ["router"]