"""In-memory fakes for application and infrastructure tests."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from types import SimpleNamespace
from typing import Any

from pyatv.const import FeatureState
from pyatv.const import PowerState as PyatvPowerState
from pyatv.exceptions import NotSupportedError
from pyatv.interface import FeatureInfo

from appletv_mcp.application.ports.apple_tv import DiscoveredDevice
from appletv_mcp.domain.enums import (
    FeatureAvailability,
    NormalizedOperation,
    PlaybackAction,
    PowerState,
    PressAction,
    RemoteButton,
    SkipDirection,
    VolumeDirection,
)
from appletv_mcp.domain.models.capabilities import AppleTVCapabilities
from appletv_mcp.domain.models.device import AppInfo
from appletv_mcp.domain.models.settings import Settings
from appletv_mcp.domain.models.status import AppleTVStatus
from tests.helpers.factories import (
    DEFAULT_IDENTIFIER,
    make_app,
    make_capabilities,
    make_status,
)


class MemorySettingsRepository:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings
        self.saves: list[Settings] = []

    def exists(self) -> bool:
        return self._settings is not None

    def load(self) -> Settings:
        if self._settings is None:
            from appletv_mcp.domain.errors import DeviceNotConfiguredError

            raise DeviceNotConfiguredError("No Apple TV is configured.")
        return self._settings

    def save(self, settings: Settings) -> None:
        self._settings = settings
        self.saves.append(settings)

    def update_preferred_host(self, host: str) -> Settings:
        settings = self.load().model_copy(update={"preferred_host": host})
        self.save(settings)
        return settings


class FakeAppleTV:
    def __init__(self) -> None:
        self.listener: Any = None
        self.close_calls = 0
        self.playing_error: Exception | None = None
        self.feature_error: Exception | None = None
        self.command_error: Exception | None = None
        self.power_observe_error: Exception | None = None
        self.metadata = _FakeMetadata(self)
        self.audio = _FakeAudio()
        self.keyboard = _FakeKeyboard()
        self.power = _FakePower(self)
        self.features = _FakeFeatures(self)
        self.remote_control = _FakeRemoteControl(self)
        self.apps = _FakeApps(self)
        self.device_info = SimpleNamespace(
            model_str="Apple TV 4K",
            operating_system=SimpleNamespace(name="TvOS"),
            version=None,
            mac=None,
        )

    def close(self) -> set[asyncio.Task[Any]]:
        self.close_calls += 1
        if self.listener is not None:
            self.listener.connection_closed()
        return set()


class _FakeMetadata:
    def __init__(self, owner: FakeAppleTV) -> None:
        self._owner = owner

    async def playing(self) -> object:
        if self._owner.playing_error is not None:
            raise self._owner.playing_error
        raise NotSupportedError()

    @property
    def app(self) -> object:
        raise NotSupportedError()


class _FakeAudio:
    @property
    def volume(self) -> float:
        raise NotSupportedError()


class _FakeKeyboard:
    @property
    def text_focus_state(self) -> object:
        raise NotSupportedError()


class _FakePower:
    def __init__(self, owner: FakeAppleTV) -> None:
        self._owner = owner
        self._state: PyatvPowerState | None = None
        self.turn_on_calls: list[bool] = []
        self.turn_off_calls: list[bool] = []

    @property
    def power_state(self) -> PyatvPowerState:
        if self._owner.power_observe_error is not None:
            raise self._owner.power_observe_error
        if self._state is None:
            raise NotSupportedError()
        return self._state

    def set_state(self, state: PyatvPowerState) -> None:
        self._state = state

    async def turn_on(self, await_new_state: bool = False) -> None:
        self.turn_on_calls.append(await_new_state)
        if await_new_state:
            raise NotImplementedError("not supported by Companion yet")
        if self._owner.command_error is not None:
            raise self._owner.command_error
        if self._state is not None:
            self._state = PyatvPowerState.On

    async def turn_off(self, await_new_state: bool = False) -> None:
        self.turn_off_calls.append(await_new_state)
        if await_new_state:
            raise NotImplementedError("not supported by Companion yet")
        if self._owner.command_error is not None:
            raise self._owner.command_error
        if self._state is not None:
            self._state = PyatvPowerState.Off


class _FakeFeatures:
    def __init__(self, owner: FakeAppleTV) -> None:
        self._owner = owner

    def get_feature(self, _feature_name: object) -> FeatureInfo:
        if self._owner.feature_error is not None:
            raise self._owner.feature_error
        return FeatureInfo(FeatureState.Available)


class _FakeRemoteControl:
    def __init__(self, owner: FakeAppleTV) -> None:
        self._owner = owner
        self.calls: list[str] = []

    def __getattr__(self, name: str) -> Callable[..., Awaitable[None]]:
        async def _call(*_args: object, **_kwargs: object) -> None:
            self.calls.append(name)
            if self._owner.command_error is not None:
                raise self._owner.command_error

        return _call


class _FakeApps:
    def __init__(self, owner: FakeAppleTV) -> None:
        self._owner = owner
        self.launch_log: list[str] = []

    async def app_list(self) -> list[object]:
        if self._owner.feature_error is not None:
            raise self._owner.feature_error
        return []

    async def launch_app(self, bundle_id_or_url: str) -> None:
        if self._owner.command_error is not None:
            raise self._owner.command_error
        self.launch_log.append(bundle_id_or_url)


class FakeScanner:
    def __init__(self, devices: Sequence[DiscoveredDevice] | None = None) -> None:
        self.devices = list(devices or [])
        self.calls: list[dict[str, Any]] = []
        self.error: Exception | None = None
        self.delay = 0.0

    async def scan(
        self,
        *,
        timeout: float,
        identifier: str | None = None,
        hosts: Sequence[str] | None = None,
    ) -> list[DiscoveredDevice]:
        self.calls.append(
            {"timeout": timeout, "identifier": identifier, "hosts": list(hosts or [])}
        )
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        found = list(self.devices)
        if hosts:
            found = [device for device in found if device.address in hosts]
        if identifier:
            found = [device for device in found if device.matches(identifier)]
        return found


class FakeGateway:
    def __init__(self) -> None:
        self.status_value = make_status()
        self.capabilities_value = make_capabilities()
        self.apps: list[AppInfo] = [
            make_app("Netflix", "com.netflix.Netflix"),
            make_app("YouTube", "com.google.ios.youtube"),
            make_app("TV", "com.apple.TV"),
        ]
        self.features: dict[NormalizedOperation, FeatureAvailability] = dict.fromkeys(
            NormalizedOperation, FeatureAvailability.AVAILABLE
        )
        self.power_state = PowerState.ON
        self.observed_power: PowerState | None = None
        self.volume: float | None = 20.0
        self.calls: list[tuple[str, object]] = []
        self.fail_with: Exception | None = None
        self.fail_on: set[str] = set()
        self.fail_after_calls: dict[str, int] = {}
        self._call_counts: dict[str, int] = {}
        self.invalidate_calls = 0
        self.reconnect_calls = 0
        self.disconnect_calls = 0
        self.closed = False
        self.launch_log: list[str] = []
        self.press_log: list[tuple[RemoteButton, PressAction]] = []
        self.playback_log: list[PlaybackAction] = []
        self.skip_log: list[tuple[SkipDirection, float]] = []
        self.text_log: list[str] = []
        self.volume_log: list[tuple[str, object]] = []

    def fail(self, exc: Exception, *operations: str) -> None:
        self.fail_with = exc
        self.fail_on = set(operations)

    async def close(self) -> None:
        self.closed = True

    def invalidate(self) -> None:
        self.invalidate_calls += 1

    async def disconnect(self) -> None:
        self.disconnect_calls += 1

    async def reconnect(self) -> None:
        self.reconnect_calls += 1

    def unreachable_status(self) -> AppleTVStatus:
        return make_status(
            connection="unreachable", playback=None, media_app=None, volume_percent=None
        )

    async def read_status(self) -> AppleTVStatus:
        self._before("status")
        return self.status_value

    async def read_capabilities(self) -> AppleTVCapabilities:
        self._before("capabilities")
        return self.capabilities_value

    async def read_apps(self) -> list[AppInfo]:
        self._before("list_apps")
        return list(self.apps)

    async def feature_state(self, operation: NormalizedOperation) -> FeatureAvailability:
        self._before("feature_state")
        return self.features[operation]

    async def turn_on(self) -> PowerState:
        self._before("turn_on")
        if self.observed_power is not None:
            return self.observed_power
        self.power_state = PowerState.ON
        return self.power_state

    async def turn_off(self) -> PowerState:
        self._before("turn_off")
        if self.observed_power is not None:
            return self.observed_power
        self.power_state = PowerState.OFF
        return self.power_state

    async def current_power_state(self) -> PowerState:
        self._before("current_power_state")
        return self.power_state

    async def launch_app(self, bundle_id_or_url: str) -> None:
        self._before("launch_app")
        self.launch_log.append(bundle_id_or_url)

    async def press(self, button: RemoteButton, action: PressAction) -> None:
        self._before("press")
        self.press_log.append((button, action))

    async def playback(self, action: PlaybackAction) -> None:
        self._before("playback")
        self.playback_log.append(action)

    async def seek(self, position_seconds: int) -> None:
        self._before("seek")
        self.calls.append(("seek", position_seconds))

    async def skip(self, direction: SkipDirection, seconds: float) -> None:
        self._before("skip")
        self.skip_log.append((direction, seconds))

    async def set_text(self, text: str) -> None:
        self._before("set_text")
        self.text_log.append(text)

    async def set_volume(self, percent: float) -> float | None:
        self._before("set_volume")
        self.volume = percent
        self.volume_log.append(("set", percent))
        return self.volume

    async def volume_step(self, direction: VolumeDirection) -> None:
        self._before("volume_step")
        self.volume_log.append(("step", direction))

    async def current_volume(self) -> float | None:
        self._before("current_volume")
        return self.volume

    def _before(self, operation: str) -> None:
        self._call_counts[operation] = self._call_counts.get(operation, 0) + 1
        self.calls.append((operation, None))
        if self.fail_with is None:
            return
        if self.fail_on and operation not in self.fail_on:
            return
        limit = self.fail_after_calls.get(operation)
        if limit is not None and self._call_counts[operation] <= limit:
            return
        raise self.fail_with


def discovered(
    *,
    identifier: str = DEFAULT_IDENTIFIER,
    name: str = "Living Room",
    address: str = "192.168.1.50",
    extras: Sequence[str] = (),
    device_model: str | None = "Gen4K",
    model: str | None = "Apple TV 4K",
) -> DiscoveredDevice:
    return DiscoveredDevice(
        identifier=identifier,
        all_identifiers=(identifier, *extras),
        name=name,
        address=address,
        model=model,
        device_model=device_model,
        config=object(),
    )


ConnectFn = Callable[[object], Awaitable[FakeAppleTV]]
