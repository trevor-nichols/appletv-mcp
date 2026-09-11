"""Translate pyatv values into domain types. Keep raw pyatv objects here."""

from pyatv.const import (
    DeviceState,
    FeatureState,
    KeyboardFocusState,
    RepeatState,
    ShuffleState,
)
from pyatv.const import (
    MediaType as PyatvMediaType,
)
from pyatv.const import (
    PowerState as PyatvPowerState,
)
from pyatv.interface import App, AppleTV, Playing
from pyatv.interface import DeviceInfo as PyatvDeviceInfo

from appletv_mcp.domain.enums import (
    ConnectionState,
    FeatureAvailability,
    KeyboardFocus,
    MediaType,
    PlaybackState,
    PowerState,
    RepeatMode,
    ShuffleMode,
)
from appletv_mcp.domain.models.device import AppInfo, DeviceInfo
from appletv_mcp.domain.models.playback import PlaybackInfo
from appletv_mcp.domain.models.status import AppleTVStatus

_FEATURE_STATE: dict[FeatureState, FeatureAvailability] = {
    FeatureState.Available: FeatureAvailability.AVAILABLE,
    FeatureState.Unknown: FeatureAvailability.UNKNOWN,
    FeatureState.Unavailable: FeatureAvailability.UNAVAILABLE,
    FeatureState.Unsupported: FeatureAvailability.UNSUPPORTED,
}

_POWER_STATE: dict[PyatvPowerState, PowerState] = {
    PyatvPowerState.On: PowerState.ON,
    PyatvPowerState.Off: PowerState.OFF,
    PyatvPowerState.Unknown: PowerState.UNKNOWN,
}

_PLAYBACK_STATE: dict[DeviceState, PlaybackState] = {
    DeviceState.Idle: PlaybackState.IDLE,
    DeviceState.Loading: PlaybackState.LOADING,
    DeviceState.Paused: PlaybackState.PAUSED,
    DeviceState.Playing: PlaybackState.PLAYING,
    DeviceState.Stopped: PlaybackState.STOPPED,
    DeviceState.Seeking: PlaybackState.SEEKING,
}

_MEDIA_TYPE: dict[PyatvMediaType, MediaType] = {
    PyatvMediaType.Unknown: MediaType.UNKNOWN,
    PyatvMediaType.Video: MediaType.VIDEO,
    PyatvMediaType.Music: MediaType.MUSIC,
    PyatvMediaType.TV: MediaType.TV,
}

_REPEAT: dict[RepeatState, RepeatMode] = {
    RepeatState.Off: RepeatMode.OFF,
    RepeatState.Track: RepeatMode.TRACK,
    RepeatState.All: RepeatMode.ALL,
}

_SHUFFLE: dict[ShuffleState, ShuffleMode] = {
    ShuffleState.Off: ShuffleMode.OFF,
    ShuffleState.Albums: ShuffleMode.ALBUMS,
    ShuffleState.Songs: ShuffleMode.SONGS,
}

_KEYBOARD: dict[KeyboardFocusState, KeyboardFocus] = {
    KeyboardFocusState.Focused: KeyboardFocus.FOCUSED,
    KeyboardFocusState.Unfocused: KeyboardFocus.UNFOCUSED,
    KeyboardFocusState.Unknown: KeyboardFocus.UNKNOWN,
}


def normalize_feature_state(state: FeatureState) -> FeatureAvailability:
    return _FEATURE_STATE.get(state, FeatureAvailability.UNKNOWN)


def normalize_power_state(state: PyatvPowerState) -> PowerState:
    return _POWER_STATE.get(state, PowerState.UNKNOWN)


def normalize_app(app: App | None) -> AppInfo | None:
    if app is None:
        return None
    return AppInfo(name=app.name, bundle_id=app.identifier)


def normalize_device_info(
    *,
    identifier: str,
    name: str | None,
    address: str | None,
    device_info: PyatvDeviceInfo | None = None,
) -> DeviceInfo:
    model: str | None = None
    operating_system: str | None = None
    version: str | None = None
    mac: str | None = None
    if device_info is not None:
        model = device_info.model_str
        operating_system = device_info.operating_system.name
        version = device_info.version
        mac = device_info.mac
    return DeviceInfo(
        identifier=identifier,
        name=name,
        address=address,
        model=model,
        operating_system=operating_system,
        version=version,
        mac=mac,
    )


def normalize_playing(playing: Playing) -> PlaybackInfo:
    return PlaybackInfo(
        state=_PLAYBACK_STATE.get(playing.device_state, PlaybackState.UNKNOWN),
        media_type=_MEDIA_TYPE.get(playing.media_type),
        title=playing.title,
        artist=playing.artist,
        album=playing.album,
        genre=playing.genre,
        series_name=playing.series_name,
        season_number=playing.season_number,
        episode_number=playing.episode_number,
        position_seconds=playing.position,
        duration_seconds=playing.total_time,
        repeat=_REPEAT.get(playing.repeat) if playing.repeat is not None else None,
        shuffle=_SHUFFLE.get(playing.shuffle) if playing.shuffle is not None else None,
        content_identifier=playing.content_identifier,
        itunes_store_identifier=playing.itunes_store_identifier,
    )


def unreachable_status(
    *,
    identifier: str,
    name: str | None,
    address: str | None,
) -> AppleTVStatus:
    return AppleTVStatus(
        connection=ConnectionState.UNREACHABLE,
        device=DeviceInfo(identifier=identifier, name=name, address=address),
        power_state=PowerState.UNKNOWN,
        playback=None,
        media_app=None,
        volume_percent=None,
        keyboard_focus=None,
    )


def connected_status(
    atv: AppleTV,
    *,
    identifier: str,
    name: str | None,
    address: str | None,
    playing: Playing | None,
    media_app: App | None,
    volume: float | None,
    keyboard_focus: KeyboardFocusState | None,
    power_state: PyatvPowerState | None,
) -> AppleTVStatus:
    return AppleTVStatus(
        connection=ConnectionState.CONNECTED,
        device=normalize_device_info(
            identifier=identifier,
            name=name,
            address=address,
            device_info=atv.device_info,
        ),
        power_state=normalize_power_state(power_state) if power_state is not None else None,
        playback=normalize_playing(playing) if playing is not None else None,
        media_app=normalize_app(media_app),
        volume_percent=_clamp_volume(volume),
        keyboard_focus=_KEYBOARD.get(keyboard_focus) if keyboard_focus is not None else None,
    )


def _clamp_volume(volume: float | None) -> float | None:
    if volume is None:
        return None
    return max(0.0, min(100.0, float(volume)))
