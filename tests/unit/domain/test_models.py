"""Domain model and settings validation tests."""

import math

import pytest
from pydantic import ValidationError

from appletv_mcp.domain.enums import PowerState, PressAction, RemoteButton
from appletv_mcp.domain.errors import (
    AppleTVError,
    ScreenCaptureError,
    ScreenCaptureFailedError,
    ScreenCaptureInvalidImageError,
    ScreenCapturePairingRequiredError,
    ScreenCaptureTimeoutError,
    ScreenCaptureUnavailableError,
)
from appletv_mcp.domain.models.results import PressResult, VolumeResult
from appletv_mcp.domain.models.screen import CapturedScreen
from appletv_mcp.domain.models.settings import ScreenCaptureSettings, Settings
from tests.helpers.factories import make_settings, make_status
from tests.helpers.png import FAKE_SCREEN_PNG


def test_settings_accepts_valid_profile() -> None:
    settings = make_settings()
    assert settings.device_identifier == "AA:BB:CC:DD:EE:FF"
    assert settings.preferred_host == "192.168.1.50"


def test_settings_trims_identifier() -> None:
    settings = Settings.model_validate({"device_identifier": "  abc  "})
    assert settings.device_identifier == "abc"


def test_settings_rejects_empty_identifier() -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({"device_identifier": "   "})


def test_settings_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({"device_identifier": "abc", "credentials": "nope"})


def test_settings_rejects_non_ipv4_preferred_host() -> None:
    with pytest.raises(ValidationError):
        make_settings(preferred_host="living-room.local")


def test_settings_blank_optional_fields_become_none() -> None:
    settings = make_settings(device_name="", preferred_host="")
    assert settings.device_name is None
    assert settings.preferred_host is None


@pytest.mark.parametrize("field", ["scan_timeout_seconds", "command_timeout_seconds"])
def test_settings_rejects_non_positive_timeouts(field: str) -> None:
    with pytest.raises(ValidationError):
        make_settings(**{field: 0})
    with pytest.raises(ValidationError):
        make_settings(**{field: math.inf})


def test_enum_serialization_uses_values() -> None:
    assert PowerState.ON.value == "on"
    assert RemoteButton.BACK.value == "back"
    assert PowerState("off") is PowerState.OFF


def test_status_optional_fields_may_be_none() -> None:
    status = make_status(playback=None, media_app=None, volume_percent=None, keyboard_focus=None)
    dumped = status.model_dump()
    assert dumped["media_app"] is None
    assert dumped["playback"] is None
    assert "active_app" not in dumped


def test_volume_result_bounds() -> None:
    with pytest.raises(ValidationError):
        VolumeResult(requested_percent=101, volume_percent=None)


def test_press_result_completed_bounds() -> None:
    result = PressResult(button=RemoteButton.UP, action=PressAction.TAP, count=3, completed=2)
    assert result.completed == 2
    with pytest.raises(ValidationError):
        PressResult(button=RemoteButton.UP, action=PressAction.TAP, count=0, completed=0)


def test_v01_settings_payload_gets_default_screen_capture() -> None:
    settings = Settings.model_validate({"device_identifier": "abc", "preferred_host": "10.0.0.2"})
    assert settings.screen_capture == ScreenCaptureSettings()
    assert settings.screen_capture.command == "appletv-screenshot"
    assert settings.screen_capture.timeout_seconds == 20.0
    assert settings.screen_capture.max_image_bytes == 33_554_432


def test_screen_capture_settings_round_trip_and_trim() -> None:
    settings = Settings.model_validate(
        {
            "device_identifier": "abc",
            "screen_capture": {
                "command": "  /opt/helpers/appletv-screenshot ",
                "timeout_seconds": 5,
                "max_image_bytes": 1024,
            },
        }
    )
    assert settings.screen_capture.command == "/opt/helpers/appletv-screenshot"
    dumped = settings.model_dump(mode="json")
    assert dumped["screen_capture"] == {
        "command": "/opt/helpers/appletv-screenshot",
        "timeout_seconds": 5.0,
        "max_image_bytes": 1024,
    }
    assert Settings.model_validate(dumped) == settings


@pytest.mark.parametrize(
    "overrides",
    [
        {"command": ""},
        {"command": "   "},
        {"timeout_seconds": 0},
        {"timeout_seconds": 61},
        {"timeout_seconds": math.inf},
        {"timeout_seconds": math.nan},
        {"max_image_bytes": 0},
        {"pair_record": "secret"},
    ],
)
def test_screen_capture_settings_reject_invalid_values(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ScreenCaptureSettings.model_validate(overrides)


def test_captured_screen_is_frozen_png_only() -> None:
    screen = CapturedScreen(data=FAKE_SCREEN_PNG)
    assert screen.mime_type == "image/png"
    assert screen.data == FAKE_SCREEN_PNG
    with pytest.raises(ValidationError):
        screen.data = b"changed"
    with pytest.raises(ValidationError):
        CapturedScreen(data=b"")
    with pytest.raises(ValidationError):
        CapturedScreen.model_validate({"data": FAKE_SCREEN_PNG, "mime_type": "image/jpeg"})


def test_screen_capture_errors_are_apple_tv_errors() -> None:
    for error_type in (
        ScreenCaptureUnavailableError,
        ScreenCapturePairingRequiredError,
        ScreenCaptureTimeoutError,
        ScreenCaptureFailedError,
        ScreenCaptureInvalidImageError,
    ):
        error = error_type("boom")
        assert isinstance(error, ScreenCaptureError)
        assert isinstance(error, AppleTVError)
        assert error.message == "boom"
