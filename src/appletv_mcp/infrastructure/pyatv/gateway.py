"""Translate controller operations into pyatv 0.18.0 calls."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from pyatv.const import FeatureName, InputAction
from pyatv.interface import AppleTV

from appletv_mcp.application.ports.settings import SettingsRepository
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
from appletv_mcp.domain.errors import AppleTVError, DeviceNotConfiguredError
from appletv_mcp.domain.models.capabilities import AppleTVCapabilities
from appletv_mcp.domain.models.device import AppInfo
from appletv_mcp.domain.models.status import AppleTVStatus
from appletv_mcp.infrastructure.pyatv.connection_manager import ConnectionManager
from appletv_mcp.infrastructure.pyatv.exception_map import (
    is_optional_absence,
    translate_exception,
)
from appletv_mcp.infrastructure.pyatv.feature_map import FEATURE_MAP
from appletv_mcp.infrastructure.pyatv.normalizers import (
    connected_status,
    normalize_app,
    normalize_feature_state,
    normalize_power_state,
    unreachable_status,
)

logger = logging.getLogger(__name__)

_INPUT_ACTION = {
    PressAction.TAP: InputAction.SingleTap,
    PressAction.DOUBLE_TAP: InputAction.DoubleTap,
    PressAction.HOLD: InputAction.Hold,
}

_REMOTE_PRESS = {
    RemoteButton.UP: "up",
    RemoteButton.DOWN: "down",
    RemoteButton.LEFT: "left",
    RemoteButton.RIGHT: "right",
    RemoteButton.SELECT: "select",
    RemoteButton.BACK: "menu",
    RemoteButton.HOME: "home",
}

_PLAYBACK_METHOD = {
    PlaybackAction.PLAY: "play",
    PlaybackAction.PAUSE: "pause",
    PlaybackAction.TOGGLE: "play_pause",
    PlaybackAction.STOP: "stop",
    PlaybackAction.NEXT: "next",
    PlaybackAction.PREVIOUS: "previous",
}


class PyAtvGateway:
    """Infrastructure implementation of `AppleTVGateway`."""

    def __init__(
        self,
        connection_manager: ConnectionManager,
        settings_repository: SettingsRepository,
        command_timeout_seconds: float,
    ) -> None:
        self._connections = connection_manager
        self._settings_repository = settings_repository
        self._timeout = command_timeout_seconds

    async def close(self) -> None:
        await self._connections.close()

    def invalidate(self) -> None:
        self._connections.invalidate()

    async def disconnect(self) -> None:
        await self._connections.disconnect()

    async def reconnect(self) -> None:
        await self._connections.reconnect()

    def unreachable_status(self) -> AppleTVStatus:
        identifier, name, address = self._identity()
        return unreachable_status(identifier=identifier, name=name, address=address)

    async def read_status(self) -> AppleTVStatus:
        async def _read(atv: AppleTV) -> AppleTVStatus:
            identifier, name, address = self._identity()
            playing = await _optional(atv.metadata.playing())
            media_app = _optional_value(lambda: atv.metadata.app)
            volume = _optional_value(lambda: atv.audio.volume)
            keyboard = _optional_value(lambda: atv.keyboard.text_focus_state)
            power = _optional_value(lambda: atv.power.power_state)
            return connected_status(
                atv,
                identifier=identifier,
                name=name or atv.device_info.model_str,
                address=self._connections.current_address or address,
                playing=playing,
                media_app=media_app,
                volume=volume,
                keyboard_focus=keyboard,
                power_state=power,
            )

        return await self._observe("status", _read)

    async def read_capabilities(self) -> AppleTVCapabilities:
        states: dict[str, FeatureAvailability] = {}

        async def _read(atv: AppleTV) -> AppleTVCapabilities:
            for operation, feature in FEATURE_MAP.items():
                states[operation.value] = _feature_availability(atv, feature)
            return AppleTVCapabilities.model_validate(states)

        return await self._observe("capabilities", _read)

    async def read_apps(self) -> list[AppInfo]:
        async def _read(atv: AppleTV) -> list[AppInfo]:
            apps = await atv.apps.app_list()
            return [info for app in apps if (info := normalize_app(app)) is not None]

        return await self._observe("list apps", _read)

    async def feature_state(self, operation: NormalizedOperation) -> FeatureAvailability:
        feature = FEATURE_MAP[operation]

        async def _read(atv: AppleTV) -> FeatureAvailability:
            return _feature_availability(atv, feature)

        return await self._observe(f"feature {operation.value}", _read)

    async def turn_on(self) -> PowerState:
        async def _call(atv: AppleTV) -> PowerState:
            # Companion (pyatv 0.18.0's preferred power protocol) raises
            # NotImplementedError when await_new_state=True, even though TurnOn
            # is advertised as available. Dispatch without waiting, then snapshot.
            await atv.power.turn_on(await_new_state=False)
            return self._best_effort_power_state(atv)

        return await self._command("power on", _call)

    async def turn_off(self) -> PowerState:
        async def _call(atv: AppleTV) -> PowerState:
            await atv.power.turn_off(await_new_state=False)
            return self._best_effort_power_state(atv)

        return await self._command("power off", _call)

    async def current_power_state(self) -> PowerState:
        async def _read(atv: AppleTV) -> PowerState:
            return normalize_power_state(atv.power.power_state)

        return await self._observe("power state", _read)

    async def launch_app(self, bundle_id_or_url: str) -> None:
        async def _call(atv: AppleTV) -> None:
            await atv.apps.launch_app(bundle_id_or_url)

        await self._command("launch app", _call)

    async def press(self, button: RemoteButton, action: PressAction) -> None:
        input_action = _INPUT_ACTION[action]
        method_name = _REMOTE_PRESS[button]

        async def _call(atv: AppleTV) -> None:
            method = getattr(atv.remote_control, method_name)
            await method(input_action)

        await self._command(f"{button.value} button", _call)

    async def playback(self, action: PlaybackAction) -> None:
        method_name = _PLAYBACK_METHOD[action]

        async def _call(atv: AppleTV) -> None:
            method = getattr(atv.remote_control, method_name)
            await method()

        await self._command(f"playback {action.value}", _call)

    async def seek(self, position_seconds: int) -> None:
        async def _call(atv: AppleTV) -> None:
            await atv.remote_control.set_position(position_seconds)

        await self._command("seek", _call)

    async def skip(self, direction: SkipDirection, seconds: float) -> None:
        interval = seconds if seconds > 0 else 0.0

        async def _call(atv: AppleTV) -> None:
            if direction is SkipDirection.FORWARD:
                await atv.remote_control.skip_forward(interval)
            else:
                await atv.remote_control.skip_backward(interval)

        await self._command(f"skip {direction.value}", _call)

    async def set_text(self, text: str) -> None:
        async def _call(atv: AppleTV) -> None:
            await atv.keyboard.text_set(text)

        logger.debug("Sending %d characters to Apple TV keyboard", len(text))
        await self._command("set text", _call)

    async def set_volume(self, percent: float) -> float | None:
        async def _call(atv: AppleTV) -> float | None:
            await atv.audio.set_volume(percent)
            return _optional_value(lambda: atv.audio.volume)

        return await self._command("set volume", _call)

    async def volume_step(self, direction: VolumeDirection) -> None:
        async def _call(atv: AppleTV) -> None:
            if direction is VolumeDirection.UP:
                await atv.audio.volume_up()
            else:
                await atv.audio.volume_down()

        await self._command(f"volume {direction.value}", _call)

    async def current_volume(self) -> float | None:
        async def _read(atv: AppleTV) -> float | None:
            return _optional_value(lambda: atv.audio.volume)

        return await self._observe("volume", _read)

    def _best_effort_power_state(self, atv: AppleTV) -> PowerState:
        """Read power_state without failing a command that already executed.

        Do not reconnect here: a post-shutdown connect/wake can undo turn-off.
        """

        try:
            return normalize_power_state(atv.power.power_state)
        except Exception as exc:
            logger.debug("Power state could not be observed after command", exc_info=True)
            if not is_optional_absence(exc):
                self.invalidate()
            return PowerState.UNKNOWN

    async def _observe[T](self, operation: str, func: Callable[[AppleTV], Awaitable[T]]) -> T:
        return await self._run(operation, func, delivery_risk=False)

    async def _command[T](self, operation: str, func: Callable[[AppleTV], Awaitable[T]]) -> T:
        return await self._run(operation, func, delivery_risk=True)

    async def _run[T](
        self,
        operation: str,
        func: Callable[[AppleTV], Awaitable[T]],
        *,
        delivery_risk: bool,
    ) -> T:
        delivered = False
        try:
            atv = await self._connections.get()
            async with asyncio.timeout(self._timeout):
                delivered = delivery_risk
                return await func(atv)
        except AppleTVError:
            raise
        except Exception as exc:
            mapped = translate_exception(
                exc,
                operation=operation,
                may_have_been_delivered=delivered,
                connection_stale=not self._connections.cached,
            )
            if mapped is not exc:
                raise mapped from exc
            logger.exception("Unexpected error during %s", operation)
            raise

    def _identity(self) -> tuple[str, str | None, str | None]:
        try:
            settings = self._settings_repository.load()
        except DeviceNotConfiguredError:
            return "unconfigured", None, None
        return (
            settings.device_identifier,
            settings.device_name,
            self._connections.current_address or settings.preferred_host,
        )


def _feature_availability(atv: AppleTV, feature: FeatureName) -> FeatureAvailability:
    info = atv.features.get_feature(feature)
    return normalize_feature_state(info.state)


def _optional_value[T](func: Callable[[], T]) -> T | None:
    try:
        return func()
    except Exception as exc:
        if is_optional_absence(exc):
            logger.debug("Optional device property is unavailable", exc_info=True)
            return None
        raise


async def _optional[T](awaitable: Awaitable[T]) -> T | None:
    try:
        return await awaitable
    except Exception as exc:
        if is_optional_absence(exc):
            logger.debug("Optional device call failed", exc_info=True)
            return None
        raise
