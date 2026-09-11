"""Status and feature normalizers."""

from pyatv.const import FeatureState, MediaType
from pyatv.const import PowerState as PyPower
from pyatv.interface import App, Playing

from appletv_mcp.domain.enums import FeatureAvailability, PowerState
from appletv_mcp.domain.enums import MediaType as DomainMedia
from appletv_mcp.infrastructure.pyatv.normalizers import (
    normalize_app,
    normalize_feature_state,
    normalize_playing,
    normalize_power_state,
    unreachable_status,
)


def test_feature_states() -> None:
    assert normalize_feature_state(FeatureState.Available) is FeatureAvailability.AVAILABLE
    assert normalize_feature_state(FeatureState.Unknown) is FeatureAvailability.UNKNOWN
    assert normalize_feature_state(FeatureState.Unavailable) is FeatureAvailability.UNAVAILABLE
    assert normalize_feature_state(FeatureState.Unsupported) is FeatureAvailability.UNSUPPORTED


def test_power_and_app_and_playing() -> None:
    assert normalize_power_state(PyPower.On) is PowerState.ON
    app = normalize_app(App("Netflix", "com.netflix.Netflix"))
    assert app is not None
    assert app.bundle_id == "com.netflix.Netflix"
    playing = normalize_playing(
        Playing(media_type=MediaType.Video, title="Severance", position=12, total_time=60)
    )
    assert playing.media_type is DomainMedia.VIDEO
    assert playing.title == "Severance"
    assert playing.position_seconds == 12


def test_unreachable_status_does_not_fabricate_media() -> None:
    status = unreachable_status(identifier="abc", name="TV", address="10.0.0.1")
    assert status.media_app is None
    assert status.playback is None
    assert status.volume_percent is None
