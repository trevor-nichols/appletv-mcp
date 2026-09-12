"""Shared MCP tool helpers."""

from mcp.server.mcpserver import Context

from appletv_mcp.application.services.apple_tv_controller import AppleTVController
from appletv_mcp.application.services.screen_capture import ScreenCaptureService
from appletv_mcp.interfaces.mcp.lifespan import AppContext


def controller(ctx: Context[AppContext]) -> AppleTVController:
    return ctx.request_context.lifespan_context.controller


def screen_capture(ctx: Context[AppContext]) -> ScreenCaptureService:
    return ctx.request_context.lifespan_context.screen_capture
