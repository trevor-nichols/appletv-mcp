"""ExternalScreenCaptureBackend against a real helper subprocess."""

import asyncio
import logging
import os
import time
from pathlib import Path

import pytest

from appletv_mcp.domain.errors import (
    ScreenCaptureError,
    ScreenCaptureFailedError,
    ScreenCaptureInvalidImageError,
    ScreenCapturePairingRequiredError,
    ScreenCaptureTimeoutError,
    ScreenCaptureUnavailableError,
)
from appletv_mcp.domain.models.settings import ScreenCaptureSettings
from appletv_mcp.infrastructure.screen_capture import (
    ExternalScreenCaptureBackend,
    HelperExitCode,
    error_for_exit_status,
    resolve_screen_capture_executable,
    run_helper_command,
)
from appletv_mcp.infrastructure.screen_capture.contract import (
    AMBIGUOUS_DEVICE_MESSAGE,
    HELPER_MISSING_MESSAGE,
    INVALID_IMAGE_MESSAGE,
    PAIRING_REQUIRED_MESSAGE,
    TIMEOUT_MESSAGE,
)
from tests.helpers.fake_helper import InstalledFakeHelper, install_fake_helper
from tests.helpers.fake_screenshot_helper import STDERR_NOISE, STDOUT_NOISE
from tests.helpers.png import FAKE_SCREEN_PNG, make_png


def _backend(
    helper: InstalledFakeHelper,
    temp_root: Path,
    *,
    timeout_seconds: float = 10.0,
    max_image_bytes: int = 33_554_432,
    grace: float = 0.3,
) -> ExternalScreenCaptureBackend:
    settings = ScreenCaptureSettings(
        command=str(helper.executable),
        timeout_seconds=timeout_seconds,
        max_image_bytes=max_image_bytes,
    )
    return ExternalScreenCaptureBackend(
        settings, temp_root=temp_root, terminate_grace_seconds=grace
    )


def _temp_root(tmp_path: Path) -> Path:
    root = tmp_path / "temp-root"
    root.mkdir(exist_ok=True)
    return root


def _assert_process_gone(pid: int | None) -> None:
    assert pid is not None
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


async def _wait_for_pid(helper: InstalledFakeHelper) -> int:
    for _ in range(500):
        pid = helper.pid()
        if pid is not None:
            return pid
        await asyncio.sleep(0.01)
    raise AssertionError("fake helper never started")


async def test_success_returns_png_with_fixed_arguments_and_cleans_temp(tmp_path: Path) -> None:
    temp_root = _temp_root(tmp_path)
    helper = install_fake_helper(tmp_path, "success")
    backend = _backend(helper, temp_root)

    screen = await backend.capture()

    assert screen.data == FAKE_SCREEN_PNG
    assert screen.mime_type == "image/png"
    argv = helper.argv()
    assert argv[:2] == ["capture", "--output"]
    output = Path(argv[2])
    assert output.is_absolute()
    assert output.name == "screen.png"
    assert output.parent.parent == temp_root
    assert helper.cwd() == output.parent
    assert list(temp_root.iterdir()) == []


async def test_missing_helper_raises_unavailable_without_spawning(tmp_path: Path) -> None:
    settings = ScreenCaptureSettings(command=str(tmp_path / "nope" / "appletv-screenshot"))
    backend = ExternalScreenCaptureBackend(settings, temp_root=_temp_root(tmp_path))
    with pytest.raises(ScreenCaptureUnavailableError, match="could not be found"):
        await backend.capture()
    assert list((tmp_path / "temp-root").iterdir()) == []


async def test_unstartable_helper_raises_unavailable(tmp_path: Path) -> None:
    temp_root = _temp_root(tmp_path)
    broken = tmp_path / "appletv-screenshot"
    broken.write_bytes(b"\x00\x01\x02 not an executable image")
    broken.chmod(0o700)
    backend = ExternalScreenCaptureBackend(
        ScreenCaptureSettings(command=str(broken)), temp_root=temp_root
    )
    with pytest.raises(ScreenCaptureUnavailableError, match="could not be started"):
        await backend.capture()
    assert list(temp_root.iterdir()) == []


def test_resolve_executable_by_name_on_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    helper = install_fake_helper(tmp_path, "success", name="custom-shot")
    monkeypatch.setenv("PATH", str(tmp_path))
    assert resolve_screen_capture_executable(ScreenCaptureSettings(command="custom-shot")) == (
        helper.executable
    )
    assert resolve_screen_capture_executable(ScreenCaptureSettings(command="other-shot")) is None


def test_resolve_executable_by_path_requires_executable_file(tmp_path: Path) -> None:
    helper = install_fake_helper(tmp_path, "success")
    assert resolve_screen_capture_executable(
        ScreenCaptureSettings(command=str(helper.executable))
    ) == (helper.executable)
    plain = tmp_path / "not-executable"
    plain.write_text("#!/bin/sh\n", encoding="utf-8")
    plain.chmod(0o600)
    assert resolve_screen_capture_executable(ScreenCaptureSettings(command=str(plain))) is None
    assert resolve_screen_capture_executable(ScreenCaptureSettings(command=str(tmp_path))) is None


@pytest.mark.parametrize(
    ("code", "error_type", "fragment"),
    [
        (HelperExitCode.USAGE, ScreenCaptureFailedError, "helper contract"),
        (HelperExitCode.DEVICE_NOT_FOUND, ScreenCaptureFailedError, "could not find"),
        (HelperExitCode.AMBIGUOUS_DEVICE, ScreenCaptureFailedError, "unambiguous Apple TV target"),
        (HelperExitCode.PAIRING_REQUIRED, ScreenCapturePairingRequiredError, "pairing"),
        (HelperExitCode.TUNNEL_UNAVAILABLE, ScreenCaptureFailedError, "RemoteXPC tunnel"),
        (HelperExitCode.CAPTURE_FAILED, ScreenCaptureFailedError, "did not return a screenshot"),
        (HelperExitCode.OUTPUT_WRITE_FAILED, ScreenCaptureFailedError, "could not write"),
        (HelperExitCode.CAPTURE_TIMEOUT, ScreenCaptureTimeoutError, "timed out"),
        (HelperExitCode.CONFIG_INVALID, ScreenCaptureFailedError, "own configuration"),
        (99, ScreenCaptureFailedError, "status 99"),
    ],
)
async def test_exit_codes_map_to_domain_errors(
    tmp_path: Path,
    code: int,
    error_type: type[ScreenCaptureError],
    fragment: str,
) -> None:
    temp_root = _temp_root(tmp_path)
    helper = install_fake_helper(tmp_path, f"exit:{int(code)}")
    backend = _backend(helper, temp_root)
    with pytest.raises(error_type, match=fragment) as info:
        await backend.capture()
    assert STDERR_NOISE not in info.value.message
    assert STDOUT_NOISE not in info.value.message
    assert list(temp_root.iterdir()) == []


async def test_spec_error_texts_are_used_verbatim(tmp_path: Path) -> None:
    pairing = install_fake_helper(
        tmp_path, f"exit:{int(HelperExitCode.PAIRING_REQUIRED)}", name="helper-pairing"
    )
    with pytest.raises(ScreenCapturePairingRequiredError) as info:
        await _backend(pairing, _temp_root(tmp_path)).capture()
    assert info.value.message == PAIRING_REQUIRED_MESSAGE
    ambiguous = install_fake_helper(
        tmp_path, f"exit:{int(HelperExitCode.AMBIGUOUS_DEVICE)}", name="helper-ambiguous"
    )
    with pytest.raises(ScreenCaptureFailedError) as ambiguous_info:
        await _backend(ambiguous, _temp_root(tmp_path)).capture()
    assert ambiguous_info.value.message == AMBIGUOUS_DEVICE_MESSAGE
    assert HELPER_MISSING_MESSAGE.startswith("Screen capture is unavailable")
    assert TIMEOUT_MESSAGE == "Apple TV screen capture timed out before a screenshot was returned."


def test_error_for_exit_status_edge_cases() -> None:
    with pytest.raises(ValueError):
        error_for_exit_status(0)
    signalled = error_for_exit_status(-9)
    assert isinstance(signalled, ScreenCaptureFailedError)
    assert "signal 9" in signalled.message


async def test_output_written_before_failure_is_discarded(tmp_path: Path) -> None:
    temp_root = _temp_root(tmp_path)
    helper = install_fake_helper(tmp_path, f"write-then-exit:{int(HelperExitCode.CAPTURE_FAILED)}")
    with pytest.raises(ScreenCaptureFailedError):
        await _backend(helper, temp_root).capture()
    assert list(temp_root.iterdir()) == []


async def test_timeout_terminates_helper_and_cleans_up(tmp_path: Path) -> None:
    temp_root = _temp_root(tmp_path)
    helper = install_fake_helper(tmp_path, "hang")
    backend = _backend(helper, temp_root, timeout_seconds=0.5)

    started = time.monotonic()
    with pytest.raises(ScreenCaptureTimeoutError) as info:
        await backend.capture()
    elapsed = time.monotonic() - started

    assert info.value.message == TIMEOUT_MESSAGE
    assert elapsed < 5
    _assert_process_gone(helper.pid())
    assert list(temp_root.iterdir()) == []


async def test_timeout_kills_helper_that_ignores_sigterm(tmp_path: Path) -> None:
    temp_root = _temp_root(tmp_path)
    helper = install_fake_helper(tmp_path, "hang-ignore-term")
    backend = _backend(helper, temp_root, timeout_seconds=0.5, grace=0.3)

    with pytest.raises(ScreenCaptureTimeoutError):
        await backend.capture()

    _assert_process_gone(helper.pid())
    assert list(temp_root.iterdir()) == []


async def test_run_helper_command_cancellation_stops_child(tmp_path: Path) -> None:
    helper = install_fake_helper(tmp_path, "hang")
    task = asyncio.create_task(run_helper_command(helper.executable, ["--version"]))
    pid = await _wait_for_pid(helper)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    _assert_process_gone(pid)


async def test_cancellation_stops_helper_and_cleans_up(tmp_path: Path) -> None:
    temp_root = _temp_root(tmp_path)
    helper = install_fake_helper(tmp_path, "hang")
    backend = _backend(helper, temp_root, timeout_seconds=30)

    task = asyncio.create_task(backend.capture())
    pid = await _wait_for_pid(helper)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    _assert_process_gone(pid)
    assert list(temp_root.iterdir()) == []


@pytest.mark.parametrize("mode", ["no-output", "empty", "garbage"])
async def test_unusable_output_is_invalid_image(tmp_path: Path, mode: str) -> None:
    temp_root = _temp_root(tmp_path)
    helper = install_fake_helper(tmp_path, mode)
    with pytest.raises(ScreenCaptureInvalidImageError) as info:
        await _backend(helper, temp_root).capture()
    assert info.value.message == INVALID_IMAGE_MESSAGE
    assert list(temp_root.iterdir()) == []


async def test_oversize_output_is_rejected_by_size_before_reading(tmp_path: Path) -> None:
    big = make_png(filler=b"x" * 4096)
    helper = install_fake_helper(tmp_path, "success", png=big)
    backend = _backend(helper, _temp_root(tmp_path), max_image_bytes=1024)
    with pytest.raises(ScreenCaptureInvalidImageError, match="above the configured limit"):
        await backend.capture()


async def test_helper_noise_never_reaches_logs(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    helper = install_fake_helper(tmp_path, "success")
    backend = _backend(helper, _temp_root(tmp_path))
    with caplog.at_level(logging.DEBUG, logger="appletv_mcp"):
        await backend.capture()
    joined = "\n".join(record.getMessage() for record in caplog.records)
    assert "Starting screen-capture helper" in joined
    assert "Captured 2x2 PNG" in joined
    assert STDOUT_NOISE not in joined
    assert STDERR_NOISE not in joined
    assert "0xDEADBEEF" not in joined
    assert FAKE_SCREEN_PNG[:8].decode("latin-1") not in joined
