"""Normalized enumerations for the Apple TV control contract."""

from enum import StrEnum


class ConnectionState(StrEnum):
    CONNECTED = "connected"
    UNREACHABLE = "unreachable"


class PowerTarget(StrEnum):
    ON = "on"
    OFF = "off"


class PowerState(StrEnum):
    ON = "on"
    OFF = "off"
    UNKNOWN = "unknown"


class FeatureAvailability(StrEnum):
    AVAILABLE = "available"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"


class RemoteButton(StrEnum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    SELECT = "select"
    BACK = "back"
    HOME = "home"


class PressAction(StrEnum):
    TAP = "tap"
    DOUBLE_TAP = "double_tap"
    HOLD = "hold"


class PlaybackAction(StrEnum):
    PLAY = "play"
    PAUSE = "pause"
    TOGGLE = "toggle"
    STOP = "stop"
    NEXT = "next"
    PREVIOUS = "previous"


class SkipDirection(StrEnum):
    FORWARD = "forward"
    BACKWARD = "backward"


class VolumeDirection(StrEnum):
    UP = "up"
    DOWN = "down"


class PlaybackState(StrEnum):
    IDLE = "idle"
    LOADING = "loading"
    PAUSED = "paused"
    PLAYING = "playing"
    STOPPED = "stopped"
    SEEKING = "seeking"
    UNKNOWN = "unknown"


class MediaType(StrEnum):
    UNKNOWN = "unknown"
    VIDEO = "video"
    MUSIC = "music"
    TV = "tv"


class RepeatMode(StrEnum):
    OFF = "off"
    TRACK = "track"
    ALL = "all"


class ShuffleMode(StrEnum):
    OFF = "off"
    ALBUMS = "albums"
    SONGS = "songs"


class KeyboardFocus(StrEnum):
    FOCUSED = "focused"
    UNFOCUSED = "unfocused"
    UNKNOWN = "unknown"


class NormalizedOperation(StrEnum):
    POWER_ON = "power_on"
    POWER_OFF = "power_off"
    LIST_APPS = "list_apps"
    LAUNCH_APP = "launch_app"
    NAVIGATE_UP = "navigate_up"
    NAVIGATE_DOWN = "navigate_down"
    NAVIGATE_LEFT = "navigate_left"
    NAVIGATE_RIGHT = "navigate_right"
    NAVIGATE_SELECT = "navigate_select"
    NAVIGATE_BACK = "navigate_back"
    NAVIGATE_HOME = "navigate_home"
    PLAY = "play"
    PAUSE = "pause"
    TOGGLE = "toggle"
    STOP = "stop"
    NEXT = "next"
    PREVIOUS = "previous"
    SEEK = "seek"
    SKIP_FORWARD = "skip_forward"
    SKIP_BACKWARD = "skip_backward"
    TEXT_SET = "text_set"
    VOLUME_GET = "volume_get"
    VOLUME_SET = "volume_set"
    VOLUME_UP = "volume_up"
    VOLUME_DOWN = "volume_down"
    KEYBOARD_FOCUS = "keyboard_focus"


class OperationKind(StrEnum):
    READ = "read"
    IDEMPOTENT_WRITE = "idempotent_write"
    NON_IDEMPOTENT = "non_idempotent"
    # Semantically idempotent, but reconnect/wake makes automatic replay unsafe
    # (e.g. power off after an uncertain Sleep dispatch).
    REPLAY_UNSAFE = "replay_unsafe"
