"""Opt-in live Apple TV tests. Disabled unless APPLE_TV_INTEGRATION_TESTS=1.

Read-only checks run with that flag. Write checks also require
APPLE_TV_LIVE_WRITES=1 so ordinary integration opt-in stays non-disruptive.
"""

import os
from collections.abc import AsyncIterator

import pytest

from appletv_mcp.composition import Runtime, create_runtime
from appletv_mcp.domain.enums import ConnectionState, FeatureAvailability
from appletv_mcp.domain.errors import DeviceNotConfiguredError
from appletv_mcp.domain.models.status import AppleTVStatus
from appletv_mcp.infrastructure.config.repository import FileSettingsRepository

pytestmark = pytest.mark.live


@pytest.fixture
async def runtime() -> AsyncIterator[Runtime]:
    try:
        FileSettingsRepository().load()
    except DeviceNotConfiguredError as exc:
        pytest.skip(str(exc))
    created = await create_runtime()
    try:
        yield created
    finally:
        await created.aclose()


async def _require_connected(runtime: Runtime) -> AppleTVStatus:
    status = await runtime.controller.status()
    if status.connection is ConnectionState.UNREACHABLE:
        pytest.skip("Apple TV is not currently reachable")
    return status


async def test_live_status_and_capabilities(runtime: Runtime) -> None:
    status = await _require_connected(runtime)
    assert status.device.identifier
    caps = await runtime.controller.capabilities()
    assert caps.play in FeatureAvailability
    apps = await runtime.controller.list_apps()
    assert isinstance(apps, list)


async def test_live_reconnect_after_invalidate(runtime: Runtime) -> None:
    await _require_connected(runtime)
    runtime.connection_manager.invalidate()
    status = await runtime.controller.status()
    assert status.connection in {ConnectionState.CONNECTED, ConnectionState.UNREACHABLE}


async def test_live_writes_require_extra_flag(runtime: Runtime) -> None:
    if os.environ.get("APPLE_TV_LIVE_WRITES") != "1":
        pytest.skip("write tests require APPLE_TV_LIVE_WRITES=1")
    await _require_connected(runtime)
    caps = await runtime.controller.capabilities()
    if caps.volume_set is FeatureAvailability.AVAILABLE:
        current = await runtime.controller.status()
        percent = current.volume_percent if current.volume_percent is not None else 20.0
        result = await runtime.controller.set_volume(percent)
        assert result.requested_percent == percent
    apps = await runtime.controller.list_apps()
    if apps and caps.launch_app in {FeatureAvailability.AVAILABLE, FeatureAvailability.UNKNOWN}:
        launched = await runtime.controller.open_app(apps[0].bundle_id)
        assert launched.launched is True


async def test_live_env_flag_documented() -> None:
    assert os.environ.get("APPLE_TV_INTEGRATION_TESTS") == "1"
