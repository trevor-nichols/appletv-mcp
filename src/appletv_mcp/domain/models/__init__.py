"""Public domain models."""

from appletv_mcp.domain.models.capabilities import AppleTVCapabilities
from appletv_mcp.domain.models.device import AppInfo, DeviceInfo
from appletv_mcp.domain.models.playback import PlaybackInfo
from appletv_mcp.domain.models.results import (
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
from appletv_mcp.domain.models.settings import Settings
from appletv_mcp.domain.models.status import AppleTVStatus

__all__ = [
    "AppInfo",
    "AppleTVCapabilities",
    "AppleTVStatus",
    "DeviceInfo",
    "OpenAppResult",
    "OpenUrlResult",
    "PlaybackInfo",
    "PlaybackResult",
    "PowerResult",
    "PressResult",
    "SeekResult",
    "Settings",
    "SkipResult",
    "TextResult",
    "VolumeAdjustResult",
    "VolumeResult",
]
