"""Semantic Apple TV operations used by MCP tools and the CLI."""

import asyncio
import logging
import math
from collections.abc import Awaitable, Callable
from urllib.parse import urlparse

from agenai_appletv_mcp.application.policies.capabilities import ensure_executable
from agenai_appletv_mcp.application.policies.retry import execute as execute_with_retry
from agenai_appletv_mcp.application.ports.apple_tv import AppleTVGateway
from agenai_appletv_mcp.application.services.app_resolution import filter_apps, resolve_app
from agenai_appletv_mcp.domain.enums import (
    KeyboardFocus,
    NormalizedOperation,
    OperationKind,
    PlaybackAction,
    PowerTarget,
    PressAction,
    RemoteButton,
    SkipDirection,
    VolumeDirection,
)
from agenai_appletv_mcp.domain.errors import (
    CommandTimeoutError,
    DeviceConnectionError,
    DeviceNotFoundError,
    DeviceUnreachableError,
    InvalidInputError,
    InvalidUrlError,
    KeyboardNotFocusedError,
)
from agenai_appletv_mcp.domain.models.capabilities import AppleTVCapabilities
from agenai_appletv_mcp.domain.models.device import AppInfo
from agenai_appletv_mcp.domain.models.results import (
    OpenAppResult,
    OpenUrlResult,
    PlaybackResult,
    PowerResult,
    PressResult,
    SeekResult,
    SkipResult,
    TextResult,
    VolumeAdjustResult,
    VolumeResult,
)
from agenai_appletv_mcp.domain.models.status import AppleTVStatus

logger = logging.getLogger(__name__)

_BUTTON_OPERATIONS: dict[RemoteButton, NormalizedOperation] = {
    RemoteButton.UP: NormalizedOperation.NAVIGATE_UP,
    RemoteButton.DOWN: NormalizedOperation.NAVIGATE_DOWN,
    RemoteButton.LEFT: NormalizedOperation.NAVIGATE_LEFT,
    RemoteButton.RIGHT: NormalizedOperation.NAVIGATE_RIGHT,
    RemoteButton.SELECT: NormalizedOperation.NAVIGATE_SELECT,
    RemoteButton.BACK: NormalizedOperation.NAVIGATE_BACK,
    RemoteButton.HOME: NormalizedOperation.NAVIGATE_HOME,
}

_PLAYBACK_OPERATIONS: dict[PlaybackAction, NormalizedOperation] = {
    PlaybackAction.PLAY: NormalizedOperation.PLAY,
    PlaybackAction.PAUSE: NormalizedOperation.PAUSE,
    PlaybackAction.TOGGLE: NormalizedOperation.TOGGLE,
    PlaybackAction.STOP: NormalizedOperation.STOP,
    PlaybackAction.NEXT: NormalizedOperation.NEXT,
    PlaybackAction.PREVIOUS: NormalizedOperation.PREVIOUS,
}

_IDEMPOTENT_PLAYBACK = {PlaybackAction.PLAY, PlaybackAction.PAUSE, PlaybackAction.STOP}


class AppleTVController:
    """Orchestrates capability checks, app resolution, retries, and locking."""

    def __init__(self, gateway: AppleTVGateway) -> None:
        self._gateway = gateway
        self._command_lock = asyncio.Lock()

    async def close(self) -> None:
        await self._gateway.close()

    async def status(self) -> AppleTVStatus:
        try:
            return await self._read(OperationKind.READ, "status", self._gateway.read_status)
        except (
            DeviceNotFoundError,
            DeviceUnreachableError,
            DeviceConnectionError,
            CommandTimeoutError,
        ):
            return self._gateway.unreachable_status()

    async def capabilities(self) -> AppleTVCapabilities:
        return await self._read(OperationKind.READ, "capabilities", self._gateway.read_capabilities)

    async def list_apps(self, query: str | None = None) -> list[AppInfo]:
        async def _list() -> list[AppInfo]:
            await self._require(NormalizedOperation.LIST_APPS)
            apps = await self._gateway.read_apps()
            return filter_apps(apps, query)

        return await self._read(OperationKind.READ, "list apps", _list)

    async def power(self, state: PowerTarget) -> PowerResult:
        operation = (
            NormalizedOperation.POWER_ON
            if state is PowerTarget.ON
            else NormalizedOperation.POWER_OFF
        )

        async def _power() -> PowerResult:
            await self._require(operation)
            if state is PowerTarget.ON:
                observed = await self._gateway.turn_on(await_new_state=True)
            else:
                observed = await self._gateway.turn_off(await_new_state=True)
            return PowerResult(requested_state=state, power_state=observed)

        return await self._write(OperationKind.IDEMPOTENT_WRITE, f"power {state.value}", _power)

    async def open_app(self, app: str) -> OpenAppResult:
        async def _open() -> OpenAppResult:
            await self._require(NormalizedOperation.LAUNCH_APP)
            await self._require(NormalizedOperation.LIST_APPS)
            apps = await self._gateway.read_apps()
            resolved = resolve_app(app, apps)
            await self._gateway.launch_app(resolved.bundle_id)
            return OpenAppResult(name=resolved.name, bundle_id=resolved.bundle_id, launched=True)

        return await self._write(OperationKind.IDEMPOTENT_WRITE, "open app", _open)

    async def open_url(self, url: str) -> OpenUrlResult:
        validated = validate_deep_link(url)

        async def _open() -> OpenUrlResult:
            await self._require(NormalizedOperation.LAUNCH_APP)
            await self._gateway.launch_app(validated)
            return OpenUrlResult(url=validated, accepted=True)

        return await self._write(OperationKind.NON_IDEMPOTENT, "open url", _open)

    async def press(self, button: RemoteButton, action: PressAction, count: int) -> PressResult:
        completed = 0

        async def _press() -> PressResult:
            nonlocal completed
            await self._require(_BUTTON_OPERATIONS[button])
            remaining = count - completed
            for _ in range(remaining):
                await self._gateway.press(button, action)
                completed += 1
            return PressResult(button=button, action=action, count=count, completed=completed)

        return await self._write(
            OperationKind.NON_IDEMPOTENT,
            f"{button.value} button",
            _press,
        )

    async def playback(self, action: PlaybackAction) -> PlaybackResult:
        kind = (
            OperationKind.IDEMPOTENT_WRITE
            if action in _IDEMPOTENT_PLAYBACK
            else OperationKind.NON_IDEMPOTENT
        )

        async def _playback() -> PlaybackResult:
            await self._require(_PLAYBACK_OPERATIONS[action])
            await self._gateway.playback(action)
            return PlaybackResult(action=action, accepted=True)

        return await self._write(kind, f"playback {action.value}", _playback)

    async def seek(self, position_seconds: int) -> SeekResult:
        async def _seek() -> SeekResult:
            await self._require(NormalizedOperation.SEEK)
            await self._gateway.seek(position_seconds)
            return SeekResult(requested_position_seconds=position_seconds, accepted=True)

        return await self._write(OperationKind.IDEMPOTENT_WRITE, "seek", _seek)

    async def skip(self, direction: SkipDirection, seconds: float) -> SkipResult:
        if not math.isfinite(seconds) or seconds < 0:
            raise InvalidInputError(
                "Skip seconds must be finite and greater than or equal to zero."
            )
        operation = (
            NormalizedOperation.SKIP_FORWARD
            if direction is SkipDirection.FORWARD
            else NormalizedOperation.SKIP_BACKWARD
        )

        async def _skip() -> SkipResult:
            await self._require(operation)
            await self._gateway.skip(direction, seconds)
            return SkipResult(direction=direction, requested_seconds=seconds, accepted=True)

        return await self._write(OperationKind.NON_IDEMPOTENT, f"skip {direction.value}", _skip)

    async def set_text(self, text: str) -> TextResult:
        logger.debug("Sending %d characters to Apple TV keyboard", len(text))

        async def _set_text() -> TextResult:
            await self._require(NormalizedOperation.TEXT_SET)
            focus = await self._keyboard_focus()
            if focus is KeyboardFocus.UNFOCUSED:
                raise KeyboardNotFocusedError(
                    "Text input is unavailable because no text field is focused."
                )
            await self._gateway.set_text(text)
            return TextResult(characters=len(text), accepted=True)

        return await self._write(OperationKind.IDEMPOTENT_WRITE, "set text", _set_text)

    async def set_volume(self, percent: float) -> VolumeResult:
        async def _set_volume() -> VolumeResult:
            await self._require(NormalizedOperation.VOLUME_SET)
            observed = await self._gateway.set_volume(percent)
            return VolumeResult(requested_percent=percent, volume_percent=observed)

        return await self._write(OperationKind.IDEMPOTENT_WRITE, "set volume", _set_volume)

    async def adjust_volume(self, direction: VolumeDirection, steps: int) -> VolumeAdjustResult:
        operation = (
            NormalizedOperation.VOLUME_UP
            if direction is VolumeDirection.UP
            else NormalizedOperation.VOLUME_DOWN
        )
        completed = 0

        async def _adjust() -> VolumeAdjustResult:
            nonlocal completed
            await self._require(operation)
            remaining = steps - completed
            for _ in range(remaining):
                await self._gateway.volume_step(direction)
                completed += 1
            volume = await self._safe_volume()
            return VolumeAdjustResult(
                direction=direction,
                requested_steps=steps,
                completed_steps=completed,
                volume_percent=volume,
            )

        return await self._write(
            OperationKind.NON_IDEMPOTENT,
            f"volume {direction.value}",
            _adjust,
        )

    async def _require(self, operation: NormalizedOperation) -> None:
        state = await self._gateway.feature_state(operation)
        ensure_executable(operation, state)

    async def _keyboard_focus(self) -> KeyboardFocus | None:
        status = await self._gateway.read_status()
        return status.keyboard_focus

    async def _safe_volume(self) -> float | None:
        try:
            return await self._gateway.current_volume()
        except Exception:
            logger.debug("Unable to read volume after adjustment", exc_info=True)
            return None

    async def _read[T](
        self, kind: OperationKind, label: str, action: Callable[[], Awaitable[T]]
    ) -> T:
        return await execute_with_retry(self._gateway, kind, label, action)

    async def _write[T](
        self, kind: OperationKind, label: str, action: Callable[[], Awaitable[T]]
    ) -> T:
        async with self._command_lock:
            return await execute_with_retry(self._gateway, kind, label, action)


def validate_deep_link(url: str) -> str:
    """Reject empty, control-character, or schemeless URLs. Custom schemes are allowed."""

    stripped = url.strip()
    if not stripped:
        raise InvalidUrlError("URL must not be empty.")
    if any(ord(char) < 32 or ord(char) == 127 for char in stripped):
        raise InvalidUrlError("URL contains control characters.")
    parsed = urlparse(stripped)
    scheme = parsed.scheme
    if not scheme:
        raise InvalidUrlError("URL must include a scheme.")
    if not _is_valid_scheme(scheme):
        raise InvalidUrlError("URL scheme is invalid.")
    return stripped


def _is_valid_scheme(scheme: str) -> bool:
    if not scheme or not scheme[0].isalpha():
        return False
    return all(char.isalnum() or char in "+.-" for char in scheme)
