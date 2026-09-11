"""Capability inspection."""

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from appletv_mcp.domain.models.capabilities import AppleTVCapabilities
from appletv_mcp.interfaces.mcp.context import controller
from appletv_mcp.interfaces.mcp.errors import run_tool
from appletv_mcp.interfaces.mcp.lifespan import AppContext


def register(mcp: MCPServer[AppContext]) -> None:
    @mcp.tool(
        name="apple_tv_capabilities",
        annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
    )
    async def apple_tv_capabilities(ctx: Context[AppContext]) -> AppleTVCapabilities:
        """Return current availability of semantic Apple TV operations.

        Values are available, unknown, unavailable, or unsupported. This is not a
        screenshot or UI-hierarchy dump.
        """

        return await run_tool(controller(ctx).capabilities)
