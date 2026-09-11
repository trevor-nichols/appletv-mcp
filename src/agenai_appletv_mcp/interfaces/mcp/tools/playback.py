"""Playback, seek, and skip tools."""

from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations
from pydantic import Field

from agenai_appletv_mcp.domain.enums import PlaybackAction, SkipDirection
from agenai_appletv_mcp.domain.models.results import PlaybackResult, SeekResult, SkipResult
from agenai_appletv_mcp.interfaces.mcp.context import controller
from agenai_appletv_mcp.interfaces.mcp.errors import run_tool
from agenai_appletv_mcp.interfaces.mcp.lifespan import AppContext


def register(mcp: MCPServer[AppContext]) -> None:
    @mcp.tool(
        name="apple_tv_playback",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=False,
        ),
    )
    async def apple_tv_playback(
        action: Annotated[
            PlaybackAction,
            Field(description="Semantic playback action. toggle/next/previous are not retried."),
        ],
        ctx: Context[AppContext],
    ) -> PlaybackResult:
        """Control playback with play, pause, toggle, stop, next, or previous."""

        return await run_tool(lambda: controller(ctx).playback(action))

    @mcp.tool(
        name="apple_tv_seek",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
    )
    async def apple_tv_seek(
        position_seconds: Annotated[
            int,
            Field(ge=0, description="Absolute playback position in seconds."),
        ],
        ctx: Context[AppContext],
    ) -> SeekResult:
        """Seek to an absolute playback position in seconds."""

        return await run_tool(lambda: controller(ctx).seek(position_seconds))

    @mcp.tool(
        name="apple_tv_skip",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=False,
        ),
    )
    async def apple_tv_skip(
        direction: Annotated[SkipDirection, Field(description="Skip direction.")],
        ctx: Context[AppContext],
        seconds: Annotated[
            float,
            Field(
                ge=0,
                description="Skip interval in seconds. Zero lets the device choose its default.",
            ),
        ] = 0,
    ) -> SkipResult:
        """Skip forward or backward. Relative skips are not retried after uncertain failure."""

        return await run_tool(lambda: controller(ctx).skip(direction, seconds))
