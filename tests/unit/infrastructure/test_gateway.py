"""Gateway status reads must not swallow transport failures as missing metadata."""

from collections.abc import Callable

from pyatv.exceptions import ConnectionLostError, NotSupportedError

from appletv_mcp.application.services.apple_tv_controller import AppleTVController
from appletv_mcp.domain.enums import ConnectionState
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
