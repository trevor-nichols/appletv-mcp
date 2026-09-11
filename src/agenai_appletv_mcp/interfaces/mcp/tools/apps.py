"""Application listing and launch tools."""

from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations
from pydantic import Field

from agenai_appletv_mcp.domain.models.device import AppInfo
from agenai_appletv_mcp.domain.models.results import OpenAppResult, OpenUrlResult
from agenai_appletv_mcp.interfaces.mcp.context import controller
from agenai_appletv_mcp.interfaces.mcp.errors import run_tool
from agenai_appletv_mcp.interfaces.mcp.lifespan import AppContext


def register_list(mcp: MCPServer[AppContext]) -> None:
    @mcp.tool(
        name="apple_tv_list_apps",
        annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
    )
    async def apple_tv_list_apps(
        ctx: Context[AppContext],
        query: Annotated[
            str | None,
            Field(
                default=None,
                description="Optional case-insensitive substring filter for name or bundle ID.",
            ),
        ] = None,
    ) -> list[AppInfo]:
        """List launchable applications installed on the Apple TV."""

        return await run_tool(lambda: controller(ctx).list_apps(query))


def register_launch(mcp: MCPServer[AppContext]) -> None:
    @mcp.tool(
        name="apple_tv_open_app",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
    )
    async def apple_tv_open_app(
        app: Annotated[
            str,
            Field(
                min_length=1,
                description="Exact bundle identifier, or exact application display name.",
            ),
        ],
        ctx: Context[AppContext],
    ) -> OpenAppResult:
        """Launch an installed application by exact bundle ID or exact display name.

        Matching is deterministic. Typos do not auto-launch a similar application.
        """

        return await run_tool(lambda: controller(ctx).open_app(app))

    @mcp.tool(
        name="apple_tv_open_url",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=False,
        ),
    )
    async def apple_tv_open_url(
        url: Annotated[
            str,
            Field(
                min_length=1,
                description="Application URL or deep link, including custom schemes.",
            ),
        ],
        ctx: Context[AppContext],
    ) -> OpenUrlResult:
        """Ask the Apple TV to open a URL or application deep link.

        A successful result means the launch request was accepted. It does not prove
        that a specific screen or item is visible. Deep links are not retried after
        uncertain delivery because they may start playback or other side effects.
        """

        return await run_tool(lambda: controller(ctx).open_url(url))
