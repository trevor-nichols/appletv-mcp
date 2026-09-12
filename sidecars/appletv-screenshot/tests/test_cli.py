import json
import logging
from pathlib import Path

import pytest

from appletv_screenshot.cli import configure_logging, main, version_line
from appletv_screenshot.config import CONFIG_DIR_ENV, SidecarConfig
from appletv_screenshot.errors import SidecarError
from appletv_screenshot.exit_codes import CONTRACT_VERSION, ExitCode
from tests.fakes import FAKE_PNG


@pytest.fixture
def config_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    directory = tmp_path / "config"
    monkeypatch.setenv(CONFIG_DIR_ENV, str(directory))
    return directory


class _RecordedCapture:
    """Stands in for `capture_to_file`; the real one is covered in test_capture."""

    def __init__(self, failure: SidecarError | None = None) -> None:
        self.failure = failure
        self.calls: list[tuple[SidecarConfig, Path]] = []

    async def __call__(self, config: SidecarConfig, output: Path) -> int:
        self.calls.append((config, output))
        if self.failure is not None:
            raise self.failure
        return len(FAKE_PNG)


def test_capture_passes_the_loaded_config_and_resolved_path_and_keeps_stdout_empty(
    monkeypatch: pytest.MonkeyPatch,
    config_dir: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["configure", "--udid", "00008110-AAAA", "--transport", "tunneld"]) == 0
    capsys.readouterr()
    recorded = _RecordedCapture()
    monkeypatch.setattr("appletv_screenshot.cli.capture_to_file", recorded)
    (tmp_path / "shots").mkdir()
    output = tmp_path / "shots" / ".." / "shots" / "screen.png"

    assert main(["capture", "--output", str(output)]) == 0

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    (config, resolved) = recorded.calls[0]
    assert config.udid == "00008110-AAAA"
    assert resolved == (tmp_path / "shots" / "screen.png").resolve()


def test_capture_failure_is_one_stderr_line_and_the_exit_code(
    monkeypatch: pytest.MonkeyPatch,
    config_dir: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    recorded = _RecordedCapture(SidecarError(ExitCode.PAIRING_REQUIRED, "pairing failed (code 5)"))
    monkeypatch.setattr("appletv_screenshot.cli.capture_to_file", recorded)

    assert main(["capture", "--output", str(tmp_path / "screen.png")]) == 12

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "appletv-screenshot: pairing failed (code 5)\n"


def test_capture_with_an_invalid_config_file_is_config_invalid(
    monkeypatch: pytest.MonkeyPatch,
    config_dir: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text('{"pair_record": "x"}', encoding="utf-8")
    recorded = _RecordedCapture()
    monkeypatch.setattr("appletv_screenshot.cli.capture_to_file", recorded)

    assert main(["capture", "--output", str(tmp_path / "screen.png")]) == 17

    assert recorded.calls == []
    assert "Extra inputs are not permitted" in capsys.readouterr().err


def test_capture_without_output_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["capture"])
    assert excinfo.value.code == ExitCode.USAGE
    assert "--output" in capsys.readouterr().err


def test_version_flag_reports_helper_contract_and_dependency(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    line = capsys.readouterr().out.strip()
    assert line == version_line()
    assert line.startswith("appletv-screenshot 0.2.0 ")
    assert f"contract={CONTRACT_VERSION}" in line
    assert "pymobiledevice3=11.12.4" in line


def test_configure_writes_only_target_and_transport_settings(
    config_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        main(
            [
                "configure",
                "--udid",
                "00008110-AAAA",
                "--transport",
                "tunneld",
                "--tunneld-host",
                "lab-mac",
                "--tunneld-port",
                "49152",
                "--timeout",
                "12",
                "--discovery-timeout",
                "2",
            ]
        )
        == 0
    )

    saved = json.loads((config_dir / "config.json").read_text(encoding="utf-8"))
    assert saved == {
        "udid": "00008110-AAAA",
        "transport": "tunneld",
        "tunneld_host": "lab-mac",
        "tunneld_port": 49152,
        "discovery_timeout_seconds": 2.0,
        "timeout_seconds": 12.0,
    }
    out = capsys.readouterr().out
    assert out.startswith(f"wrote {config_dir / 'config.json'}\n")

    assert main(["configure", "--clear-udid"]) == 0
    saved = json.loads((config_dir / "config.json").read_text(encoding="utf-8"))
    assert saved["udid"] is None
    assert saved["tunneld_host"] == "lab-mac"


def test_configure_rejects_invalid_values_as_usage(
    config_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["configure", "--tunneld-port", "70000"]) == ExitCode.USAGE
    assert "less than or equal to 65535" in capsys.readouterr().err
    assert not (config_dir / "config.json").exists()


def test_configure_replaces_an_unreadable_file(
    config_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text("{broken", encoding="utf-8")

    assert main(["configure", "--transport", "tunneld"]) == 0

    captured = capsys.readouterr()
    assert "replacing unreadable configuration" in captured.err
    saved = json.loads((config_dir / "config.json").read_text(encoding="utf-8"))
    assert saved["transport"] == "tunneld"
    assert saved["udid"] is None


def test_identify_prints_configured_target_json(
    config_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["configure", "--udid", "00008110-AAAA", "--transport", "userspace"]) == 0
    capsys.readouterr()

    assert main(["identify"]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {
        "udid": "00008110-AAAA",
        "transport": "userspace",
        "tunneld_host": "127.0.0.1",
        "tunneld_port": 49151,
        "discovery_timeout_seconds": 3.0,
        "timeout_seconds": 15.0,
    }
    assert captured.err == ""


def test_udid_and_clear_udid_are_mutually_exclusive(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["configure", "--udid", "x", "--clear-udid"])
    assert excinfo.value.code == ExitCode.USAGE


def test_pymobiledevice3_stays_at_warning_even_when_verbose() -> None:
    configure_logging(verbose=False)
    assert logging.getLogger("pymobiledevice3").level == logging.WARNING
    configure_logging(verbose=True)
    assert logging.getLogger("pymobiledevice3").level == logging.WARNING
