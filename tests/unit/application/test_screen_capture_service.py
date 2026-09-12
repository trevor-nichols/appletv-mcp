"""ScreenCaptureService behavior: delegation, serialization, error propagation."""

import asyncio
import logging

import pytest

from appletv_mcp.application.services.screen_capture import ScreenCaptureService
from appletv_mcp.domain.errors import ScreenCaptureFailedError
from tests.helpers.png import FAKE_SCREEN_PNG
from tests.helpers.screen_capture import FakeScreenCaptureBackend


async def test_capture_returns_backend_image() -> None:
    backend = FakeScreenCaptureBackend()
    service = ScreenCaptureService(backend)
    screen = await service.capture()
    assert screen.data == FAKE_SCREEN_PNG
    assert screen.mime_type == "image/png"
    assert backend.calls == 1


async def test_concurrent_captures_are_serialized() -> None:
    hold = asyncio.Event()
    backend = FakeScreenCaptureBackend(hold=hold)
    service = ScreenCaptureService(backend)

    tasks = [asyncio.create_task(service.capture()) for _ in range(5)]
    await asyncio.sleep(0)
    assert backend.active == 1
    assert backend.calls == 1
    hold.set()
    results = await asyncio.gather(*tasks)

    assert len(results) == 5
    assert backend.calls == 5
    assert backend.max_active == 1
    assert backend.started == [1, 2, 3, 4, 5]


async def test_backend_error_propagates_and_releases_lock() -> None:
    backend = FakeScreenCaptureBackend(fail_with=ScreenCaptureFailedError("helper exit 5"))
    service = ScreenCaptureService(backend)
    with pytest.raises(ScreenCaptureFailedError, match="helper exit 5"):
        await service.capture()
    backend.fail_with = None
    screen = await service.capture()
    assert screen.data == FAKE_SCREEN_PNG


async def test_cancelled_capture_releases_lock_for_next_caller() -> None:
    hold = asyncio.Event()
    backend = FakeScreenCaptureBackend(hold=hold)
    service = ScreenCaptureService(backend)

    first = asyncio.create_task(service.capture())
    await asyncio.sleep(0)
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first

    hold.set()
    screen = await service.capture()
    assert screen.data == FAKE_SCREEN_PNG
    assert backend.active == 0


async def test_service_logs_sizes_not_bytes(caplog: pytest.LogCaptureFixture) -> None:
    backend = FakeScreenCaptureBackend()
    service = ScreenCaptureService(backend)
    with caplog.at_level(logging.DEBUG, logger="appletv_mcp"):
        await service.capture()
    joined = "\n".join(record.getMessage() for record in caplog.records)
    assert f"{len(FAKE_SCREEN_PNG)} bytes" in joined
    assert "PNG" not in joined
    assert FAKE_SCREEN_PNG[:8].decode("latin-1") not in joined
