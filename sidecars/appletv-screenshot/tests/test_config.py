import json
import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from appletv_screenshot.config import (
    APP_NAME,
    CONFIG_DIR_ENV,
    SidecarConfig,
    Transport,
    config_dir,
    config_path,
    load_config,
    save_config,
)
from appletv_screenshot.errors import SidecarError
from appletv_screenshot.exit_codes import ExitCode


def test_defaults_target_a_running_tunneld_with_auto_transport() -> None:
    config = SidecarConfig()
    assert config.udid is None
    assert config.transport is Transport.AUTO
    assert config.tunneld_address == ("127.0.0.1", 49151)
    assert config.discovery_timeout_seconds == 3.0
    assert config.timeout_seconds == 15.0


def test_blank_udid_becomes_none_and_values_are_trimmed() -> None:
    assert SidecarConfig(udid="   ").udid is None
    assert SidecarConfig(udid=" 00008110-AAAA ").udid == "00008110-AAAA"


@pytest.mark.parametrize(
    "payload",
    [
        {"tunneld_port": 0},
        {"tunneld_port": 65536},
        {"tunneld_host": ""},
        {"timeout_seconds": 0},
        {"timeout_seconds": 56},
        {"timeout_seconds": math.inf},
        {"discovery_timeout_seconds": math.nan},
        {"transport": "usb"},
        {"pair_record": "secret"},
    ],
)
def test_invalid_values_are_rejected(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        SidecarConfig.model_validate(payload)


def test_env_override_selects_the_config_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(CONFIG_DIR_ENV, str(tmp_path))
    assert config_dir() == tmp_path
    assert config_path() == tmp_path / "config.json"


def test_default_config_directory_is_named_after_the_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(CONFIG_DIR_ENV, raising=False)
    assert config_dir().name == APP_NAME


def test_missing_file_loads_defaults(tmp_path: Path) -> None:
    assert load_config(tmp_path / "config.json") == SidecarConfig()


def test_save_then_load_round_trips_and_leaves_no_temp_files(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "config.json"
    config = SidecarConfig(udid="00008110-AAAA", transport=Transport.TUNNELD, tunneld_port=49152)

    assert save_config(config, target) == target
    assert load_config(target) == config
    assert sorted(path.name for path in target.parent.iterdir()) == ["config.json"]
    text = target.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert json.loads(text) == {
        "udid": "00008110-AAAA",
        "transport": "tunneld",
        "tunneld_host": "127.0.0.1",
        "tunneld_port": 49152,
        "discovery_timeout_seconds": 3.0,
        "timeout_seconds": 15.0,
    }


@pytest.mark.parametrize(
    ("content", "fragment"),
    [
        ("{not json", "cannot read"),
        ("[]", "must contain a JSON object"),
        ('{"udid": "x", "pair_record": "s"}', "Extra inputs are not permitted"),
        ('{"tunneld_port": 70000}', "less than or equal to 65535"),
    ],
)
def test_unusable_file_is_config_invalid(tmp_path: Path, content: str, fragment: str) -> None:
    target = tmp_path / "config.json"
    target.write_text(content, encoding="utf-8")
    with pytest.raises(SidecarError) as excinfo:
        load_config(target)
    assert excinfo.value.exit_code is ExitCode.CONFIG_INVALID
    assert fragment in excinfo.value.detail
    assert str(target) in excinfo.value.detail
