"""Blind remote navigation. Prefer semantic tools when they are available."""

from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations
from pydantic import Field

from agenai_appletv_mcp.domain.enums import PressAction, RemoteButton
from agenai_appletv_mcp.domain.models.results import PressResult
from agenai_appletv_mcp.interfaces.mcp.context import controller
from agenai_appletv_mcp.interfaces.mcp.errors import run_tool
from agenai_appletv_mcp.interfaces.mcp.lifespan import AppContext


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
        """Press a remote button. Navigation is blind and non-idempotent.

        The server cannot see the Apple TV screen or which UI element has focus.
        Uncertain transport failures are not retried automatically.
        """

        return await run_tool(lambda: controller(ctx).press(button, action, count))
