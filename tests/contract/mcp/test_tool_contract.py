"""MCP public contract tests using the in-memory client."""

import base64
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp import Client
from mcp.server import MCPServer
from mcp.types import ImageContent, ListToolsResult, TextContent, Tool, ToolAnnotations

from appletv_mcp.application.services.apple_tv_controller import AppleTVController
from appletv_mcp.application.services.screen_capture import ScreenCaptureService
from appletv_mcp.domain.errors import ScreenCaptureUnavailableError
from appletv_mcp.infrastructure.screen_capture.contract import HELPER_MISSING_MESSAGE
from appletv_mcp.interfaces.mcp.lifespan import AppContext
from appletv_mcp.interfaces.mcp.server import create_mcp_server
from tests.helpers.fakes import FakeGateway
from tests.helpers.png import FAKE_SCREEN_PNG
from tests.helpers.screen_capture import FakeScreenCaptureBackend

EXPECTED_TOOLS = [
    "apple_tv_status",
    "apple_tv_capabilities",
    "apple_tv_list_apps",
    "apple_tv_power",
    "apple_tv_open_app",
    "apple_tv_open_url",
    "apple_tv_press",
    "apple_tv_playback",
    "apple_tv_seek",
    "apple_tv_skip",
    "apple_tv_set_text",
    "apple_tv_set_volume",
    "apple_tv_adjust_volume",
    "apple_tv_screenshot",
]

IMAGE_TOOLS = {"apple_tv_screenshot"}


def _server(
    gateway: FakeGateway | None = None,
    screen_backend: FakeScreenCaptureBackend | None = None,
) -> tuple[MCPServer[AppContext], FakeGateway]:
    fake = gateway or FakeGateway()
    controller = AppleTVController(fake)
    screen_capture = ScreenCaptureService(screen_backend or FakeScreenCaptureBackend())

    @asynccontextmanager
    async def lifespan(_server: MCPServer[AppContext]) -> AsyncIterator[AppContext]:
        yield AppContext(controller=controller, screen_capture=screen_capture)

    return create_mcp_server(lifespan=lifespan), fake


def _tool_map(result: ListToolsResult) -> dict[str, Tool]:
    return {tool.name: tool for tool in result.tools}


def _enum_values(schema: dict[str, Any], field: str) -> set[str]:
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return set()
    field_schema = properties.get(field)
    if not isinstance(field_schema, dict):
        return set()
    if "enum" in field_schema:
        values = field_schema["enum"]
        return {str(value) for value in values} if isinstance(values, list) else set()
    ref = field_schema.get("$ref", "")
    name = str(ref).rsplit("/", 1)[-1]
    defs = schema.get("$defs", {})
    if not isinstance(defs, dict):
        return set()
    enum_def = defs.get(name)
    if not isinstance(enum_def, dict):
        return set()
    values = enum_def.get("enum", [])
    return {str(value) for value in values} if isinstance(values, list) else set()


async def test_exact_tool_inventory() -> None:
    server, gateway = _server()
    assert server.name == "appletv-mcp"
    async with Client(server, raise_exceptions=True) as client:
        listed = await client.list_tools()
    names = [tool.name for tool in listed.tools]
    assert names == EXPECTED_TOOLS
    assert gateway.calls == []


async def test_each_tool_has_description_and_output_schema() -> None:
    server, _ = _server()
    async with Client(server, raise_exceptions=True) as client:
        listed = await client.list_tools()
    for tool in listed.tools:
        assert tool.description
        assert tool.input_schema["type"] == "object"
        if tool.name in IMAGE_TOOLS:
            assert tool.output_schema is None, tool.name
        else:
            assert tool.output_schema is not None, tool.name


async def test_screenshot_tool_shape() -> None:
    server, _ = _server()
    async with Client(server, raise_exceptions=True) as client:
        tools = _tool_map(await client.list_tools())
    assert EXPECTED_TOOLS.count("apple_tv_screenshot") == 1
    tool = tools["apple_tv_screenshot"]
    assert tool.input_schema.get("properties", {}) == {}
    assert tool.input_schema.get("required") in (None, [])
    assert tool.output_schema is None
    assert tool.annotations == ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    )
    assert tool.description is not None
    assert "point-in-time" in tool.description
    assert "black" in tool.description


async def test_screenshot_returns_one_png_image_content() -> None:
    backend = FakeScreenCaptureBackend()
    server, gateway = _server(screen_backend=backend)
    async with Client(server, raise_exceptions=True) as client:
        result = await client.call_tool("apple_tv_screenshot", {})
    assert result.is_error is False
    assert result.structured_content is None
    assert len(result.content) == 1
    block = result.content[0]
    assert isinstance(block, ImageContent)
    assert block.mime_type == "image/png"
    assert base64.b64decode(block.data, validate=True) == FAKE_SCREEN_PNG
    assert backend.calls == 1
    assert gateway.calls == []


async def test_screenshot_unavailable_becomes_tool_error() -> None:
    backend = FakeScreenCaptureBackend(
        fail_with=ScreenCaptureUnavailableError(HELPER_MISSING_MESSAGE)
    )
    server, gateway = _server(screen_backend=backend)
    async with Client(server) as client:
        result = await client.call_tool("apple_tv_screenshot", {})
    assert result.is_error is True
    assert result.structured_content is None
    assert len(result.content) == 1
    block = result.content[0]
    assert isinstance(block, TextContent)
    assert HELPER_MISSING_MESSAGE in block.text
    assert "Traceback" not in block.text
    assert gateway.calls == []


async def test_server_instructions_describe_screenshot_semantics() -> None:
    server, _ = _server()
    async with Client(server, raise_exceptions=True) as client:
        instructions = client.instructions
    assert instructions is not None
    assert "apple_tv_screenshot" in instructions
    assert "point-in-time" in instructions
    assert "black" in instructions
    assert "cannot see the Apple TV screen" not in instructions


async def test_read_only_annotations() -> None:
    server, _ = _server()
    async with Client(server, raise_exceptions=True) as client:
        tools = _tool_map(await client.list_tools())
    for name in ("apple_tv_status", "apple_tv_capabilities", "apple_tv_list_apps"):
        annotations = tools[name].annotations
        assert annotations is not None
        assert annotations.read_only_hint is True
        assert annotations.open_world_hint is False


async def test_idempotent_and_relative_annotations() -> None:
    server, _ = _server()
    async with Client(server, raise_exceptions=True) as client:
        tools = _tool_map(await client.list_tools())
    volume = tools["apple_tv_set_volume"].annotations
    assert volume == ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    )
    press = tools["apple_tv_press"].annotations
    assert press is not None
    assert press.idempotent_hint is False
    adjust = tools["apple_tv_adjust_volume"].annotations
    assert adjust is not None
    assert adjust.idempotent_hint is False
    open_url = tools["apple_tv_open_url"].annotations
    assert open_url is not None
    assert open_url.idempotent_hint is False
    open_app = tools["apple_tv_open_app"].annotations
    assert open_app is not None
    assert open_app.idempotent_hint is True
    power = tools["apple_tv_power"].annotations
    assert power is not None
    assert power.idempotent_hint is False


async def test_enum_and_numeric_constraints() -> None:
    server, _ = _server()
    async with Client(server, raise_exceptions=True) as client:
        tools = _tool_map(await client.list_tools())
    power_schema = tools["apple_tv_power"].input_schema
    assert _enum_values(power_schema, "state") == {"on", "off"}
    volume = tools["apple_tv_set_volume"].input_schema["properties"]["percent"]
    assert volume["minimum"] == 0
    assert volume["maximum"] == 100
    count = tools["apple_tv_press"].input_schema["properties"]["count"]
    assert count["minimum"] == 1
    assert count["maximum"] == 10
    seek = tools["apple_tv_seek"].input_schema["properties"]["position_seconds"]
    assert seek["minimum"] == 0
    skip = tools["apple_tv_skip"].input_schema["properties"]["seconds"]
    assert skip["minimum"] == 0
    steps = tools["apple_tv_adjust_volume"].input_schema["properties"]["steps"]
    assert steps["minimum"] == 1
    assert steps["maximum"] == 10
    press_schema = tools["apple_tv_press"].input_schema
    assert _enum_values(press_schema, "button") == {
        "up",
        "down",
        "left",
        "right",
        "select",
        "back",
        "home",
    }


async def test_required_and_optional_arguments() -> None:
    server, _ = _server()
    async with Client(server, raise_exceptions=True) as client:
        tools = _tool_map(await client.list_tools())
    assert tools["apple_tv_status"].input_schema.get("required") in (None, [])
    assert "query" not in tools["apple_tv_list_apps"].input_schema.get("required", [])
    assert tools["apple_tv_open_app"].input_schema["required"] == ["app"]
    assert tools["apple_tv_power"].input_schema["required"] == ["state"]
    assert "count" not in tools["apple_tv_press"].input_schema.get("required", [])


async def test_structured_status_and_capabilities() -> None:
    server, _ = _server()
    async with Client(server, raise_exceptions=True) as client:
        status = await client.call_tool("apple_tv_status", {})
        caps = await client.call_tool("apple_tv_capabilities", {})
    assert status.is_error is False
    assert status.structured_content is not None
    assert status.structured_content["media_app"]["bundle_id"] == "com.apple.TV"
    assert "active_app" not in status.structured_content
    assert caps.structured_content is not None
    assert caps.structured_content["play"] == "available"


async def test_tool_error_sets_is_error() -> None:
    server, gateway = _server()
    async with Client(server) as client:
        result = await client.call_tool("apple_tv_open_app", {"app": "Netflox"})
    assert result.is_error is True
    assert result.structured_content is None
    assert any(
        isinstance(block, TextContent) and "Netflox" in block.text for block in result.content
    )
    assert gateway.launch_log == []


async def test_invalid_arguments_rejected_before_controller() -> None:
    server, gateway = _server()
    async with Client(server) as client:
        result = await client.call_tool("apple_tv_set_volume", {"percent": 150})
    assert result.is_error or result.structured_content is None
    assert all(call[0] != "set_volume" for call in gateway.calls)


async def test_no_pairing_or_raw_pyatv_tools() -> None:
    server, _ = _server()
    async with Client(server, raise_exceptions=True) as client:
        names = [tool.name for tool in (await client.list_tools()).tools]
    forbidden = {"pair", "unpair", "credentials", "companion_launch_app", "mrp_button_command"}
    assert forbidden.isdisjoint(names)
