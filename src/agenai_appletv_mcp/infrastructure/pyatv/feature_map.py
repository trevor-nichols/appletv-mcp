"""Single mapping from normalized operations to pyatv 0.18.0 FeatureName members."""

from pyatv.const import FeatureName

from agenai_appletv_mcp.domain.enums import NormalizedOperation

FEATURE_MAP: dict[NormalizedOperation, FeatureName] = {
    NormalizedOperation.POWER_ON: FeatureName.TurnOn,
    NormalizedOperation.POWER_OFF: FeatureName.TurnOff,
    NormalizedOperation.LIST_APPS: FeatureName.AppList,
    NormalizedOperation.LAUNCH_APP: FeatureName.LaunchApp,
    NormalizedOperation.NAVIGATE_UP: FeatureName.Up,
    NormalizedOperation.NAVIGATE_DOWN: FeatureName.Down,
    NormalizedOperation.NAVIGATE_LEFT: FeatureName.Left,
    NormalizedOperation.NAVIGATE_RIGHT: FeatureName.Right,
    NormalizedOperation.NAVIGATE_SELECT: FeatureName.Select,
    NormalizedOperation.NAVIGATE_BACK: FeatureName.Menu,
    NormalizedOperation.NAVIGATE_HOME: FeatureName.Home,
    NormalizedOperation.PLAY: FeatureName.Play,
    NormalizedOperation.PAUSE: FeatureName.Pause,
    NormalizedOperation.TOGGLE: FeatureName.PlayPause,
    NormalizedOperation.STOP: FeatureName.Stop,
    NormalizedOperation.NEXT: FeatureName.Next,
    NormalizedOperation.PREVIOUS: FeatureName.Previous,
    NormalizedOperation.SEEK: FeatureName.SetPosition,
    NormalizedOperation.SKIP_FORWARD: FeatureName.SkipForward,
    NormalizedOperation.SKIP_BACKWARD: FeatureName.SkipBackward,
    NormalizedOperation.TEXT_SET: FeatureName.TextSet,
    NormalizedOperation.VOLUME_GET: FeatureName.Volume,
    NormalizedOperation.VOLUME_SET: FeatureName.SetVolume,
    NormalizedOperation.VOLUME_UP: FeatureName.VolumeUp,
    NormalizedOperation.VOLUME_DOWN: FeatureName.VolumeDown,
    NormalizedOperation.KEYBOARD_FOCUS: FeatureName.TextFocusState,
}
