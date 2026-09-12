"""Atomic configuration persistence tests."""

import json
from pathlib import Path

import pytest

from appletv_mcp.domain.errors import ConfigurationError, DeviceNotConfiguredError
from appletv_mcp.domain.models.settings import ScreenCaptureSettings
from appletv_mcp.infrastructure.config.paths import CONFIG_DIR_ENV, config_dir
from appletv_mcp.infrastructure.config.repository import FileSettingsRepository
from tests.helpers.factories import make_settings


def test_config_dir_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert CONFIG_DIR_ENV == "APPLETV_MCP_CONFIG_DIR"
    monkeypatch.setenv(CONFIG_DIR_ENV, str(tmp_path))
    assert config_dir() == tmp_path


def test_round_trip_save_load(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    repo = FileSettingsRepository(path)
    settings = make_settings()
    repo.save(settings)
    loaded = repo.load()
    assert loaded == settings
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "credentials" not in payload
    assert payload["device_identifier"] == settings.device_identifier


def test_missing_file_raises(tmp_path: Path) -> None:
    repo = FileSettingsRepository(tmp_path / "missing.json")
    with pytest.raises(DeviceNotConfiguredError):
        repo.load()


def test_invalid_json_raises(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="not valid JSON"):
        FileSettingsRepository(path).load()


def test_invalid_settings_raise(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text('{"device_identifier": ""}', encoding="utf-8")
    with pytest.raises(ConfigurationError, match="invalid"):
        FileSettingsRepository(path).load()


def test_extra_fields_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        '{"device_identifier": "abc", "pairing_blob": "secret"}',
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError):
        FileSettingsRepository(path).load()


def test_atomic_replacement(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    repo = FileSettingsRepository(path)
    repo.save(make_settings(device_name="One"))
    repo.save(make_settings(device_name="Two"))
    assert repo.load().device_name == "Two"
    leftovers = list(tmp_path.glob(".config.json.*.tmp"))
    assert leftovers == []


def test_v01_config_file_loads_with_default_screen_capture(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "device_identifier": "AA:BB:CC:DD:EE:FF",
                "device_name": "Living Room",
                "preferred_host": "192.168.1.50",
                "scan_timeout_seconds": 5.0,
                "command_timeout_seconds": 10.0,
            }
        ),
        encoding="utf-8",
    )
    loaded = FileSettingsRepository(path).load()
    assert loaded.screen_capture.command == "appletv-screenshot"
    assert loaded.screen_capture.timeout_seconds == 20.0


def test_screen_capture_settings_persist_without_secrets(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    repo = FileSettingsRepository(path)
    settings = make_settings().model_copy(
        update={
            "screen_capture": ScreenCaptureSettings(
                command="/opt/bin/appletv-screenshot", timeout_seconds=8
            )
        }
    )
    repo.save(settings)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["screen_capture"] == {
        "command": "/opt/bin/appletv-screenshot",
        "timeout_seconds": 8.0,
        "max_image_bytes": 33_554_432,
    }
    assert repo.load().screen_capture.command == "/opt/bin/appletv-screenshot"


def test_preferred_host_update(tmp_path: Path) -> None:
    repo = FileSettingsRepository(tmp_path / "config.json")
    repo.save(make_settings(preferred_host="192.168.1.50"))
    updated = repo.update_preferred_host("10.0.0.9")
    assert updated.preferred_host == "10.0.0.9"
    assert repo.load().device_identifier == updated.device_identifier
    assert repo.load().preferred_host == "10.0.0.9"


def test_preferred_host_update_rejects_invalid_host(tmp_path: Path) -> None:
    repo = FileSettingsRepository(tmp_path / "config.json")
    repo.save(make_settings(preferred_host="192.168.1.50"))
    with pytest.raises(ConfigurationError, match="preferred_host"):
        repo.update_preferred_host("living-room.local")
    assert repo.load().preferred_host == "192.168.1.50"
