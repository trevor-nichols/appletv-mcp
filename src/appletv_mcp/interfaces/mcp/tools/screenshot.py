"""Point-in-time screen observation returned as native MCP image content."""

from mcp.server import MCPServer
from mcp.server.mcpserver import Context, Image
from mcp.types import ToolAnnotations

from appletv_mcp.interfaces.mcp.context import screen_capture
from appletv_mcp.interfaces.mcp.errors import run_tool
from appletv_mcp.interfaces.mcp.lifespan import AppContext


def register(mcp: MCPServer[AppContext]) -> None:
    @mcp.tool(
        name="apple_tv_screenshot",
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
        structured_output=False,
    )
    async def apple_tv_screenshot(ctx: Context[AppContext]) -> Image:
        """Capture the Apple TV screen as one PNG image.

        The image is point-in-time evidence of what the Apple TV rendered when the
        capture ran. It may be stale after any later action; capture again to verify.
        Protected DRM video can appear black while surrounding UI stays visible; a black
        region alone does not mean the TV is off or playback failed. Requires the optional
        screen-capture helper; without it the tool reports that screen capture is
        unavailable.
        """

        screen = await run_tool(screen_capture(ctx).capture)
        return Image(data=screen.data, format="png")
