"""Atomic configuration persistence tests."""

import json
from pathlib import Path

import pytest

from agenai_appletv_mcp.domain.errors import ConfigurationError, DeviceNotConfiguredError
from agenai_appletv_mcp.infrastructure.config.repository import FileSettingsRepository
from tests.helpers.factories import make_settings


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


def test_preferred_host_update(tmp_path: Path) -> None:
    repo = FileSettingsRepository(tmp_path / "config.json")
    repo.save(make_settings(preferred_host="192.168.1.50"))
    updated = repo.update_preferred_host("10.0.0.9")
    assert updated.preferred_host == "10.0.0.9"
    assert repo.load().device_identifier == updated.device_identifier
    assert repo.load().preferred_host == "10.0.0.9"
