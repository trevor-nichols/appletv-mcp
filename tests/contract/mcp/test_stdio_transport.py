"""Real stdio transport checks. No Apple TV required."""

import os
import sys
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from tests.contract.mcp.test_tool_contract import EXPECTED_TOOLS


async def test_stdio_tools_list_and_clean_shutdown() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "agenai_appletv_mcp", "serve"],
        cwd=str(Path.cwd()),
        env={
            **os.environ,
            "AGENAI_APPLETV_CONFIG_DIR": "/tmp/agenai-appletv-mcp-stdio-test",
        },
    )
    async with Client(params) as client:
        listed = await client.list_tools()
        names = [tool.name for tool in listed.tools]
        assert names == EXPECTED_TOOLS
        result = await client.call_tool("apple_tv_status", {})
        assert result.is_error is True
