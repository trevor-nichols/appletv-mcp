"""Power control."""

from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations
from pydantic import Field

from agenai_appletv_mcp.domain.enums import PowerTarget
from agenai_appletv_mcp.domain.models.results import PowerResult
from agenai_appletv_mcp.interfaces.mcp.context import controller
from agenai_appletv_mcp.interfaces.mcp.errors import run_tool
from agenai_appletv_mcp.interfaces.mcp.lifespan import AppContext


def register(mcp: MCPServer[AppContext]) -> None:
    @mcp.tool(
        name="apple_tv_power",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
    )
    async def apple_tv_power(
        state: Annotated[PowerTarget, Field(description="Requested power state.")],
        ctx: Context[AppContext],
    ) -> PowerResult:
        """Turn the Apple TV on or off and report the observed power state."""

        return await run_tool(lambda: controller(ctx).power(state))
