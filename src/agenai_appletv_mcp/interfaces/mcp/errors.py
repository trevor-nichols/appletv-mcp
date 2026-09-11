"""Convert domain errors into model-visible MCP tool errors."""

from collections.abc import Awaitable, Callable

from mcp.server.mcpserver.exceptions import ToolError

from agenai_appletv_mcp.domain.errors import AppleTVError


async def run_tool[T](operation: Callable[[], Awaitable[T]]) -> T:
    try:
        return await operation()
    except AppleTVError as exc:
        raise ToolError(exc.message) from exc
