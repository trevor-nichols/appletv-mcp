"""Reusable model factories for tests."""

from agenai_appletv_mcp.domain.enums import (
    ConnectionState,
    FeatureAvailability,
    KeyboardFocus,
    NormalizedOperation,
    PlaybackState,
    PowerState,
)
from agenai_appletv_mcp.domain.models.capabilities import AppleTVCapabilities
from agenai_appletv_mcp.domain.models.device import AppInfo, DeviceInfo
from agenai_appletv_mcp.domain.models.playback import PlaybackInfo
from agenai_appletv_mcp.domain.models.settings import Settings
from agenai_appletv_mcp.domain.models.status import AppleTVStatus

DEFAULT_IDENTIFIER = "AA:BB:CC:DD:EE:FF"


def make_settings(**overrides: object) -> Settings:
    payload: dict[str, object] = {
        "device_identifier": DEFAULT_IDENTIFIER,
        "device_name": "Living Room",
        "preferred_host": "192.168.1.50",
        "scan_timeout_seconds": 5.0,
        "command_timeout_seconds": 10.0,
    }
    payload.update(overrides)
    return Settings.model_validate(payload)


def make_app(name: str = "Netflix", bundle_id: str = "com.netflix.Netflix") -> AppInfo:
    return AppInfo(name=name, bundle_id=bundle_id)


def make_capabilities(
    default: FeatureAvailability = FeatureAvailability.AVAILABLE,
    **overrides: FeatureAvailability,
) -> AppleTVCapabilities:
    payload = {operation.value: default for operation in NormalizedOperation}
    payload.update(overrides)
    return AppleTVCapabilities.model_validate(payload)


def make_status(**overrides: object) -> AppleTVStatus:
    payload: dict[str, object] = {
        "connection": ConnectionState.CONNECTED,
        "device": DeviceInfo(
            identifier=DEFAULT_IDENTIFIER,
            name="Living Room",
            address="192.168.1.50",
            model="Apple TV 4K",
            operating_system="TvOS",
            version="18.0",
            mac=DEFAULT_IDENTIFIER,
        ),
        "power_state": PowerState.ON,
        "playback": PlaybackInfo(state=PlaybackState.PAUSED, title="Severance"),
        "media_app": make_app("TV", "com.apple.TV"),
        "volume_percent": 20.0,
        "keyboard_focus": KeyboardFocus.UNFOCUSED,
    }
    payload.update(overrides)
    return AppleTVStatus.model_validate(payload)
