"""Run the local stdio MCP server. Do not write application text to stdout."""

from appletv_mcp.infrastructure.observability.logging import configure_logging
from appletv_mcp.interfaces.mcp.server import run_stdio


def run_serve(*, debug: bool = False) -> int:
    configure_logging(debug=debug)
    run_stdio()
    return 0
