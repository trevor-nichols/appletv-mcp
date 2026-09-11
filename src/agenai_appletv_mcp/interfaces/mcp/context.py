"""Shared MCP tool helpers."""

from mcp.server.mcpserver import Context

from agenai_appletv_mcp.application.services.apple_tv_controller import AppleTVController
from agenai_appletv_mcp.interfaces.mcp.lifespan import AppContext


def controller(ctx: Context[AppContext]) -> AppleTVController:
    return ctx.request_context.lifespan_context.controller
