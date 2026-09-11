"""Current device and playback status."""

from pydantic import BaseModel, ConfigDict, Field

from appletv_mcp.domain.enums import ConnectionState, KeyboardFocus, PowerState
from appletv_mcp.domain.models.device import AppInfo, DeviceInfo
from appletv_mcp.domain.models.playback import PlaybackInfo


class AppleTVStatus(BaseModel):
    """Structured status for the configured Apple TV.

    `media_app` is the application associated with currently playing media. It
    is not a guaranteed foreground or currently visible application.
    """

    model_config = ConfigDict(extra="forbid")

    connection: ConnectionState
    device: DeviceInfo
    power_state: PowerState | None = None
    playback: PlaybackInfo | None = None
    media_app: AppInfo | None = None
    volume_percent: float | None = Field(default=None, ge=0, le=100)
    keyboard_focus: KeyboardFocus | None = None
