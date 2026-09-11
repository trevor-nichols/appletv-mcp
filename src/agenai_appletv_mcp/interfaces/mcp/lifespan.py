"""Typed MCP process lifespan. Connection to the Apple TV is lazy."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server import MCPServer

from agenai_appletv_mcp.application.services.apple_tv_controller import AppleTVController
from agenai_appletv_mcp.composition import Runtime, create_runtime


@dataclass
class AppContext:
    controller: AppleTVController
    runtime: Runtime | None = None


@asynccontextmanager
async def app_lifespan(_server: MCPServer[AppContext]) -> AsyncIterator[AppContext]:
    runtime = await create_runtime()
    try:
        yield AppContext(controller=runtime.controller, runtime=runtime)
    finally:
        await runtime.aclose()
