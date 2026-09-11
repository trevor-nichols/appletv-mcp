"""MCP server composition. Tools live in dedicated modules."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from mcp.server import MCPServer

from agenai_appletv_mcp._version import __version__
from agenai_appletv_mcp.interfaces.mcp.instructions import SERVER_INSTRUCTIONS
from agenai_appletv_mcp.interfaces.mcp.lifespan import AppContext, app_lifespan
from agenai_appletv_mcp.interfaces.mcp.tools import register_all

Lifespan = Callable[[MCPServer[AppContext]], AbstractAsyncContextManager[AppContext]]


def create_mcp_server(*, lifespan: Lifespan = app_lifespan) -> MCPServer[AppContext]:
    mcp = MCPServer[AppContext](
        "agenai-appletv",
        version=__version__,
        instructions=SERVER_INSTRUCTIONS,
        lifespan=lifespan,
    )
    register_all(mcp)
    return mcp


mcp = create_mcp_server()


def run_stdio() -> None:
    mcp.run()
