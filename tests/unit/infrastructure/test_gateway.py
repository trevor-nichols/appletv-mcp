"""Gateway status reads must not swallow transport failures as missing metadata."""

from collections.abc import Callable

import pytest
from pyatv.const import PowerState as PyatvPowerState
from pyatv.exceptions import (
    BlockedStateError,
    ConnectionLostError,
    NotSupportedError,
    ProtocolError,
)

from appletv_mcp.application.services.apple_tv_controller import AppleTVController
from appletv_mcp.domain.enums import (
    ConnectionState,
    PlaybackAction,
    PowerState,
    PowerTarget,
    PressAction,
    RemoteButton,
)
from appletv_mcp.domain.errors import CommandFailedError, UncertainExecutionError
from appletv_mcp.infrastructure.pyatv.connection_manager import ConnectionManager
from appletv_mcp.infrastructure.pyatv.gateway import PyAtvGateway
from tests.helpers.factories import make_settings
from tests.helpers.fakes import FakeAppleTV, FakeScanner, MemorySettingsRepository, discovered

PrepareFn = Callable[[FakeAppleTV, list[FakeAppleTV]], None]


def _controller(
    created: list[FakeAppleTV],
    prepare: PrepareFn | None = None,
) -> tuple[AppleTVController, ConnectionManager]:
    async def connect(_config: object) -> FakeAppleTV:
        device = FakeAppleTV()
        created.append(device)
        if prepare is not None:
            prepare(device, created)
        return device

    repo = MemorySettingsRepository(make_settings())
    manager = ConnectionManager(
        settings_repository=repo,
        storage=None,
        scan=FakeScanner([discovered()]).scan,
        connect=connect,
    )
    gateway = PyAtvGateway(manager, repo, command_timeout_seconds=5.0)
    return AppleTVController(gateway), manager


async def test_status_retries_when_playing_raises_connection_lost() -> None:
    created: list[FakeAppleTV] = []

    def prepare(device: FakeAppleTV, devices: list[FakeAppleTV]) -> None:
        if len(devices) == 1:
            device.playing_error = ConnectionLostError("gone")

    controller, manager = _controller(created, prepare)
    try:
        status = await controller.status()
        assert status.connection is ConnectionState.CONNECTED
        assert len(created) == 2
        assert created[0].close_calls == 1
        assert created[0] is not created[1]
    finally:
        await manager.close()


async def test_status_treats_unsupported_playing_as_absent_without_reconnect() -> None:
    created: list[FakeAppleTV] = []

    def prepare(device: FakeAppleTV, _devices: list[FakeAppleTV]) -> None:
        device.playing_error = NotSupportedError("no now playing")

    controller, manager = _controller(created, prepare)
    try:
        status = await controller.status()
        assert status.connection is ConnectionState.CONNECTED
        assert status.playback is None
        assert len(created) == 1
        assert created[0].close_calls == 0
    finally:
        await manager.close()


async def test_status_reports_rediscovered_address_after_ip_change() -> None:
    created: list[FakeAppleTV] = []
    moved = discovered(address="10.0.0.8")
    repo = MemorySettingsRepository(make_settings(preferred_host="192.168.1.50"))

    async def connect(_config: object) -> FakeAppleTV:
        device = FakeAppleTV()
        created.append(device)
        return device

    manager = ConnectionManager(
        settings_repository=repo,
        storage=None,
        scan=FakeScanner([moved]).scan,
        connect=connect,
    )
    gateway = PyAtvGateway(manager, repo, command_timeout_seconds=5.0)
    controller = AppleTVController(gateway)
    try:
        status = await controller.status()
        assert status.connection is ConnectionState.CONNECTED
        assert status.device.address == "10.0.0.8"
        assert repo.load().preferred_host == "10.0.0.8"
        assert len(created) == 1
    finally:
        await manager.close()


async def test_power_on_dispatches_without_await_new_state() -> None:
    created: list[FakeAppleTV] = []

    def prepare(device: FakeAppleTV, _devices: list[FakeAppleTV]) -> None:
        device.power.set_state(PyatvPowerState.Off)

    controller, manager = _controller(created, prepare)
    try:
        result = await controller.power(PowerTarget.ON)
        assert created[0].power.turn_on_calls == [False]
        assert result.power_state is PowerState.ON
        assert result.requested_state is PowerTarget.ON
        assert len(created) == 1
        assert created[0].close_calls == 0
    finally:
        await manager.close()


async def test_power_off_unverifiable_state_does_not_reconnect() -> None:
    created: list[FakeAppleTV] = []

    def prepare(device: FakeAppleTV, _devices: list[FakeAppleTV]) -> None:
        device.power.set_state(PyatvPowerState.On)
        device.power_observe_error = ConnectionLostError("sleeping")

    controller, manager = _controller(created, prepare)
    try:
        result = await controller.power(PowerTarget.OFF)
        assert created[0].power.turn_off_calls == [False]
        assert result.power_state is PowerState.UNKNOWN
        assert len(created) == 1
        assert manager.cached is False
    finally:
        await manager.close()


@pytest.mark.parametrize("kind", ["press", "toggle", "open_url"])
async def test_capability_preflight_connection_lost_is_not_uncertain(kind: str) -> None:
    created: list[FakeAppleTV] = []

    def prepare(device: FakeAppleTV, devices: list[FakeAppleTV]) -> None:
        if len(devices) == 1:
            device.feature_error = ConnectionLostError("gone")

    controller, manager = _controller(created, prepare)
    try:
        await _run_non_idempotent(controller, kind)
        assert len(created) == 2
        assert created[0].close_calls == 1
        assert created[0] is not created[1]
    finally:
        await manager.close()


@pytest.mark.parametrize("kind", ["press", "toggle", "open_url"])
async def test_command_dispatch_connection_lost_is_uncertain(kind: str) -> None:
    created: list[FakeAppleTV] = []

    def prepare(device: FakeAppleTV, _devices: list[FakeAppleTV]) -> None:
        device.command_error = ConnectionLostError("gone")

    controller, manager = _controller(created, prepare)
    try:
        with pytest.raises(UncertainExecutionError, match="not retried"):
            await _run_non_idempotent(controller, kind)
        assert len(created) == 1
        assert created[0].close_calls == 1
    finally:
        await manager.close()


async def test_blocked_state_during_command_is_not_uncertain() -> None:
    created: list[FakeAppleTV] = []

    def prepare(device: FakeAppleTV, devices: list[FakeAppleTV]) -> None:
        if len(devices) == 1:
            device.command_error = BlockedStateError("already closed")

    controller, manager = _controller(created, prepare)
    try:
        result = await controller.press(RemoteButton.RIGHT, PressAction.TAP, 1)
        assert result.completed == 1
        assert len(created) == 2
        assert created[0].close_calls == 1
    finally:
        await manager.close()


def _protocol_timeout() -> ProtocolError:
    error = ProtocolError("Command _hidC failed")
    error.__cause__ = TimeoutError("response wait")
    return error


async def test_protocol_error_timeout_cause_is_uncertain_for_press() -> None:
    created: list[FakeAppleTV] = []

    def prepare(device: FakeAppleTV, _devices: list[FakeAppleTV]) -> None:
        device.command_error = _protocol_timeout()

    controller, manager = _controller(created, prepare)
    try:
        with pytest.raises(UncertainExecutionError, match="not retried"):
            await controller.press(RemoteButton.RIGHT, PressAction.TAP, 1)
        assert len(created) == 1
        assert created[0].close_calls == 1
    finally:
        await manager.close()


async def test_genuine_protocol_error_is_not_retried() -> None:
    created: list[FakeAppleTV] = []

    def prepare(device: FakeAppleTV, _devices: list[FakeAppleTV]) -> None:
        device.command_error = ProtocolError("Command failed: missing field")

    controller, manager = _controller(created, prepare)
    try:
        with pytest.raises(CommandFailedError, match="protocol error"):
            await controller.press(RemoteButton.RIGHT, PressAction.TAP, 1)
        assert len(created) == 1
    finally:
        await manager.close()


async def _run_non_idempotent(controller: AppleTVController, kind: str) -> None:
    if kind == "press":
        await controller.press(RemoteButton.RIGHT, PressAction.TAP, 1)
        return
    if kind == "toggle":
        await controller.playback(PlaybackAction.TOGGLE)
        return
    await controller.open_url("youtube://watch?v=1")
