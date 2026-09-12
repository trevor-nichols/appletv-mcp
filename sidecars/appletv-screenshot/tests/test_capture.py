import asyncio
from pathlib import Path
from types import TracebackType
from typing import ClassVar

import pytest
from pymobiledevice3.exceptions import (
    InvalidServiceError,
    NotPairedError,
    PyMobileDevice3Exception,
)
from pymobiledevice3.remote.remote_service_discovery import RemoteServiceDiscoveryService

from appletv_screenshot.capture import (
    capture_bytes,
    capture_to_file,
    classify_capture_error,
    take_screenshot,
    write_atomically,
)
from appletv_screenshot.config import SidecarConfig
from appletv_screenshot.errors import SidecarError
from appletv_screenshot.exit_codes import ExitCode
from tests.fakes import (
    FAKE_PNG,
    FakeRsd,
    fake_session,
    opener_returning,
    screenshot_returning,
)

DVT_PROVIDER = "pymobiledevice3.services.dvt.instruments.dvt_provider.DvtProvider"
SCREENSHOT = "pymobiledevice3.services.dvt.instruments.screenshot.Screenshot"


async def test_capture_bytes_returns_the_png_and_closes_the_session() -> None:
    rsd = FakeRsd("00008110-AAAA")
    session = fake_session(rsd)
    seen: list[object] = []

    async def screenshot(target: RemoteServiceDiscoveryService) -> bytes:
        seen.append(target)
        return FAKE_PNG

    data = await capture_bytes(
        SidecarConfig(), open_session=opener_returning(session), screenshot=screenshot
    )

    assert data == FAKE_PNG
    assert seen == [rsd]
    assert rsd.closed


async def test_slow_screenshot_times_out_and_still_closes_the_session() -> None:
    rsd = FakeRsd("00008110-AAAA")

    with pytest.raises(SidecarError) as excinfo:
        await capture_bytes(
            SidecarConfig(timeout_seconds=0.05),
            open_session=opener_returning(fake_session(rsd)),
            screenshot=screenshot_returning(FAKE_PNG, delay=5),
        )

    assert excinfo.value.exit_code is ExitCode.CAPTURE_TIMEOUT
    assert excinfo.value.detail == "capture did not finish within 0.05s"
    assert rsd.closed


async def test_slow_tunnel_counts_against_the_same_deadline() -> None:
    with pytest.raises(SidecarError) as excinfo:
        await capture_bytes(
            SidecarConfig(timeout_seconds=0.05),
            open_session=opener_returning(fake_session(FakeRsd("x")), delay=5),
            screenshot=screenshot_returning(FAKE_PNG),
        )

    assert excinfo.value.exit_code is ExitCode.CAPTURE_TIMEOUT


async def test_non_png_bytes_are_a_capture_failure() -> None:
    rsd = FakeRsd("00008110-AAAA")

    with pytest.raises(SidecarError) as excinfo:
        await capture_bytes(
            SidecarConfig(),
            open_session=opener_returning(fake_session(rsd)),
            screenshot=screenshot_returning(b"JFIF" * 4),
        )

    assert excinfo.value.exit_code is ExitCode.CAPTURE_FAILED
    assert excinfo.value.detail == "device returned 16 bytes that are not a PNG image"
    assert rsd.closed


async def test_screenshot_failure_propagates_after_closing_the_session() -> None:
    rsd = FakeRsd("00008110-AAAA")

    async def screenshot(target: RemoteServiceDiscoveryService) -> bytes:
        raise SidecarError(ExitCode.PAIRING_REQUIRED, "denied")

    with pytest.raises(SidecarError) as excinfo:
        await capture_bytes(
            SidecarConfig(), open_session=opener_returning(fake_session(rsd)), screenshot=screenshot
        )

    assert excinfo.value.exit_code is ExitCode.PAIRING_REQUIRED
    assert rsd.closed


def test_capture_to_file_writes_the_png_atomically(tmp_path: Path) -> None:
    output = tmp_path / "screen.png"

    size = asyncio.run(
        capture_to_file(
            SidecarConfig(),
            output,
            open_session=opener_returning(fake_session(FakeRsd("x"))),
            screenshot=screenshot_returning(FAKE_PNG),
        )
    )

    assert size == len(FAKE_PNG)
    assert output.read_bytes() == FAKE_PNG
    assert sorted(path.name for path in tmp_path.iterdir()) == ["screen.png"]


def test_write_atomically_into_a_missing_directory_is_an_output_failure(tmp_path: Path) -> None:
    output = tmp_path / "missing" / "screen.png"

    with pytest.raises(SidecarError) as excinfo:
        write_atomically(output, FAKE_PNG)

    assert excinfo.value.exit_code is ExitCode.OUTPUT_WRITE_FAILED
    assert str(output.parent) in excinfo.value.detail


def test_write_atomically_replaces_an_existing_file(tmp_path: Path) -> None:
    output = tmp_path / "screen.png"
    output.write_bytes(b"old")

    write_atomically(output, FAKE_PNG)

    assert output.read_bytes() == FAKE_PNG


@pytest.mark.parametrize(
    ("exc", "expected", "fragment"),
    [
        (
            InvalidServiceError("Failed to start service", "00008110-AAAA", "17.4"),
            ExitCode.CAPTURE_FAILED,
            "Developer Mode",
        ),
        (NotPairedError(), ExitCode.PAIRING_REQUIRED, "not paired"),
        (
            PyMobileDevice3Exception("boom"),
            ExitCode.CAPTURE_FAILED,
            "PyMobileDevice3Exception: boom",
        ),
    ],
)
def test_classify_capture_error(
    exc: PyMobileDevice3Exception, expected: ExitCode, fragment: str
) -> None:
    error = classify_capture_error(exc)
    assert error.exit_code is expected
    assert fragment in error.detail


class _FakeDvtProvider:
    entered: ClassVar[list[object]] = []

    def __init__(self, rsd: object) -> None:
        self.rsd = rsd

    async def __aenter__(self) -> _FakeDvtProvider:
        _FakeDvtProvider.entered.append(self.rsd)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None


class _FakeScreenshot:
    result: ClassVar[bytes] = FAKE_PNG
    failure: ClassVar[Exception | None] = None

    def __init__(self, dvt: object) -> None:
        self.dvt = dvt

    async def __aenter__(self) -> _FakeScreenshot:
        if _FakeScreenshot.failure is not None:
            raise _FakeScreenshot.failure
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    async def get_screenshot(self) -> bytes:
        return _FakeScreenshot.result


@pytest.fixture
def dvt(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeDvtProvider.entered = []
    _FakeScreenshot.failure = None
    monkeypatch.setattr(DVT_PROVIDER, _FakeDvtProvider)
    monkeypatch.setattr(SCREENSHOT, _FakeScreenshot)


async def test_take_screenshot_runs_one_dvt_session(dvt: None) -> None:
    rsd = FakeRsd("00008110-AAAA")

    data = await take_screenshot(rsd)

    assert data == FAKE_PNG
    assert _FakeDvtProvider.entered == [rsd]


async def test_take_screenshot_maps_a_missing_service_to_capture_failed(dvt: None) -> None:
    _FakeScreenshot.failure = InvalidServiceError(
        "Failed to start service", "00008110-AAAA", "17.4"
    )

    with pytest.raises(SidecarError) as excinfo:
        await take_screenshot(FakeRsd("x"))

    assert excinfo.value.exit_code is ExitCode.CAPTURE_FAILED
    assert "developer disk image" in excinfo.value.detail


async def test_take_screenshot_maps_a_dropped_connection_to_capture_failed(dvt: None) -> None:
    _FakeScreenshot.failure = ConnectionResetError("peer reset")

    with pytest.raises(SidecarError) as excinfo:
        await take_screenshot(FakeRsd("x"))

    assert excinfo.value.exit_code is ExitCode.CAPTURE_FAILED
    assert "peer reset" in excinfo.value.detail
