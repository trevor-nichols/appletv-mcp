"""Ports that keep `pyatv` types out of the application layer."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from agenai_appletv_mcp.domain.enums import (
    FeatureAvailability,
    NormalizedOperation,
    PlaybackAction,
    PowerState,
    PressAction,
    RemoteButton,
    SkipDirection,
    VolumeDirection,
)
from agenai_appletv_mcp.domain.models.capabilities import AppleTVCapabilities
from agenai_appletv_mcp.domain.models.device import AppInfo
from agenai_appletv_mcp.domain.models.status import AppleTVStatus


@dataclass(frozen=True, slots=True)
class DiscoveredDevice:
    """A network-visible Apple TV candidate."""

    identifier: str
    all_identifiers: tuple[str, ...]
    name: str
    address: str
    model: str | None = None
    config: object | None = None

    def matches(self, identifier: str) -> bool:
        return identifier == self.identifier or identifier in self.all_identifiers


class AppleTVGateway(Protocol):
    """Device operations used by the controller.

    Implementations own discovery, connection, `pyatv` calls, and exception
    translation. The controller never receives a raw `pyatv` object.
    """

    async def close(self) -> None: ...

    def invalidate(self) -> None: ...

    async def reconnect(self) -> None: ...

    def unreachable_status(self) -> AppleTVStatus: ...

    async def read_status(self) -> AppleTVStatus: ...

    async def read_capabilities(self) -> AppleTVCapabilities: ...

    async def read_apps(self) -> list[AppInfo]: ...

    async def feature_state(self, operation: NormalizedOperation) -> FeatureAvailability: ...

    async def turn_on(self, *, await_new_state: bool) -> PowerState: ...

    async def turn_off(self, *, await_new_state: bool) -> PowerState: ...

    async def current_power_state(self) -> PowerState: ...

    async def launch_app(self, bundle_id_or_url: str) -> None: ...

    async def press(self, button: RemoteButton, action: PressAction) -> None: ...

    async def playback(self, action: PlaybackAction) -> None: ...

    async def seek(self, position_seconds: int) -> None: ...

    async def skip(self, direction: SkipDirection, seconds: float) -> None: ...

    async def set_text(self, text: str) -> None: ...

    async def set_volume(self, percent: float) -> float | None: ...

    async def volume_step(self, direction: VolumeDirection) -> None: ...

    async def current_volume(self) -> float | None: ...


class DeviceScanner(Protocol):
    async def scan(
        self,
        *,
        timeout: float,
        identifier: str | None = None,
        hosts: Sequence[str] | None = None,
    ) -> list[DiscoveredDevice]: ...
