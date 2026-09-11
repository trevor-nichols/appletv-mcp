"""Virtual keyboard text entry. Submitted text is never logged."""

from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations
from pydantic import Field

from appletv_mcp.domain.models.results import TextResult
from appletv_mcp.interfaces.mcp.context import controller
from appletv_mcp.interfaces.mcp.errors import run_tool
from appletv_mcp.interfaces.mcp.lifespan import AppContext


def register(mcp: MCPServer[AppContext]) -> None:
    @mcp.tool(
        name="apple_tv_set_text",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
    )
    async def apple_tv_set_text(
        text: Annotated[
            str,
            Field(description="Replacement text for the focused field. Empty string clears it."),
        ],
        ctx: Context[AppContext],
    ) -> TextResult:
        """Replace text in a focused Apple TV text field.

        Requires an active virtual keyboard. An empty string clears the field.
        """

        return await run_tool(lambda: controller(ctx).set_text(text))
