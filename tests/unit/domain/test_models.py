"""Domain model and settings validation tests."""

import math

import pytest
from pydantic import ValidationError

from appletv_mcp.domain.enums import PowerState, PressAction, RemoteButton
from appletv_mcp.domain.models.results import PressResult, VolumeResult
from appletv_mcp.domain.models.settings import Settings
from tests.helpers.factories import make_settings, make_status


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
