"""Absolute and relative volume tools."""

from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations
from pydantic import Field

from appletv_mcp.domain.enums import VolumeDirection
from appletv_mcp.domain.models.results import VolumeAdjustResult, VolumeResult
from appletv_mcp.interfaces.mcp.context import controller
from appletv_mcp.interfaces.mcp.errors import run_tool
from appletv_mcp.interfaces.mcp.lifespan import AppContext


def register(mcp: MCPServer[AppContext]) -> None:
    @mcp.tool(
        name="apple_tv_set_volume",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
    )
    async def apple_tv_set_volume(
        percent: Annotated[
            float,
            Field(ge=0, le=100, description="Absolute volume percent from 0 to 100."),
        ],
        ctx: Context[AppContext],
    ) -> VolumeResult:
        """Set absolute volume percent when the device supports volume control."""

        return await run_tool(lambda: controller(ctx).set_volume(percent))

    @mcp.tool(
        name="apple_tv_adjust_volume",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=False,
        ),
    )
    async def apple_tv_adjust_volume(
        direction: Annotated[VolumeDirection, Field(description="Relative volume direction.")],
        ctx: Context[AppContext],
        steps: Annotated[
            int,
            Field(ge=1, le=10, description="Number of relative volume steps."),
        ] = 1,
    ) -> VolumeAdjustResult:
        """Nudge volume up or down. Relative steps are not retried after uncertain failure."""

        return await run_tool(lambda: controller(ctx).adjust_volume(direction, steps))
