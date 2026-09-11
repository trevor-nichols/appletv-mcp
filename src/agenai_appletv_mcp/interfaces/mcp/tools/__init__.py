"""Register v0.1 MCP tools on a server instance."""

from mcp.server import MCPServer

from agenai_appletv_mcp.interfaces.mcp.lifespan import AppContext

from . import capabilities, playback, power, remote, status, text, volume
from .apps import register_launch, register_list


def register_all(mcp: MCPServer[AppContext]) -> None:
    status.register(mcp)
    capabilities.register(mcp)
    register_list(mcp)
    power.register(mcp)
    register_launch(mcp)
    remote.register(mcp)
    playback.register(mcp)
    text.register(mcp)
    volume.register(mcp)
