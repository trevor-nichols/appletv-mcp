"""Read-only device and playback status."""

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from appletv_mcp.domain.models.status import AppleTVStatus
from appletv_mcp.interfaces.mcp.context import controller
from appletv_mcp.interfaces.mcp.errors import run_tool
from appletv_mcp.interfaces.mcp.lifespan import AppContext


def register(mcp: MCPServer[AppContext]) -> None:
    @mcp.tool(
        name="apple_tv_status",
        annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
    )
    async def apple_tv_status(ctx: Context[AppContext]) -> AppleTVStatus:
        """Read current device, power, playback, volume, and keyboard state.

        media_app is the application associated with currently playing media, not a
        guaranteed foreground or visible application. The server cannot see the screen.
        """

        return await run_tool(controller(ctx).status)
