"""Remote navigation without feedback. Prefer semantic tools when they are available."""

from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations
from pydantic import Field

from appletv_mcp.domain.enums import PressAction, RemoteButton
from appletv_mcp.domain.models.results import PressResult
from appletv_mcp.interfaces.mcp.context import controller
from appletv_mcp.interfaces.mcp.errors import run_tool
from appletv_mcp.interfaces.mcp.lifespan import AppContext


def register(mcp: MCPServer[AppContext]) -> None:
    @mcp.tool(
        name="apple_tv_press",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=False,
        ),
    )
    async def apple_tv_press(
        button: Annotated[RemoteButton, Field(description="Remote button to press.")],
        ctx: Context[AppContext],
        action: Annotated[
            PressAction,
            Field(description="Tap, double-tap, or hold."),
        ] = PressAction.TAP,
        count: Annotated[
            int,
            Field(ge=1, le=10, description="Number of sequential presses."),
        ] = 1,
    ) -> PressResult:
        """Press a remote button. Navigation is non-idempotent.

        The press itself has no visual feedback and does not report which UI element
        has focus. Use apple_tv_screenshot separately when visible UI state needs to be
        inspected or verified. Uncertain transport failures are not retried automatically.
        """

        return await run_tool(lambda: controller(ctx).press(button, action, count))
