"""Opt-in live screen capture. Disabled unless APPLE_TV_INTEGRATION_TESTS=1.

Capturing the screen changes nothing on the Apple TV, so these run with the
read-only flag alone. They skip when the helper is not installed and fail on
any other capture error, because with the helper present an unpaired or
unreachable device is a real finding.
"""

import asyncio

import pytest

from appletv_mcp.composition import Runtime
from appletv_mcp.infrastructure.config.repository import FileSettingsRepository
from appletv_mcp.infrastructure.screen_capture import (
    inspect_png,
    resolve_screen_capture_executable,
)

pytestmark = pytest.mark.live


def _require_helper() -> None:
    settings = FileSettingsRepository().load()
    if resolve_screen_capture_executable(settings.screen_capture) is None:
        pytest.skip(f"{settings.screen_capture.command} is not installed")


async def test_live_screenshot_is_a_png_with_dimensions(runtime: Runtime) -> None:
    _require_helper()

    screen = await runtime.screen_capture.capture()

    assert screen.mime_type == "image/png"
    info = inspect_png(screen.data)
    assert info is not None
    assert info.width > 0
    assert info.height > 0
    assert info.size == len(screen.data)


async def test_live_concurrent_screenshots_both_succeed(runtime: Runtime) -> None:
    _require_helper()

    first, second = await asyncio.gather(
        runtime.screen_capture.capture(), runtime.screen_capture.capture()
    )

    assert inspect_png(first.data) is not None
    assert inspect_png(second.data) is not None
