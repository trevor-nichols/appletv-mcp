"""One-shot capture: open a device session, take one screenshot, write it, close."""

import asyncio
import logging
import os
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path

from pymobiledevice3.exceptions import (
    InvalidServiceError,
    NotPairedError,
    PairingError,
    PyMobileDevice3Exception,
)
from pymobiledevice3.remote.remote_service_discovery import RemoteServiceDiscoveryService

from appletv_screenshot.config import SidecarConfig
from appletv_screenshot.errors import SidecarError
from appletv_screenshot.exit_codes import ExitCode
from appletv_screenshot.transport import DeviceSession, open_device

logger = logging.getLogger(__name__)

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

OpenDevice = Callable[[SidecarConfig], Awaitable[DeviceSession]]
TakeScreenshot = Callable[[RemoteServiceDiscoveryService], Awaitable[bytes]]


async def take_screenshot(rsd: RemoteServiceDiscoveryService) -> bytes:
    from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
    from pymobiledevice3.services.dvt.instruments.screenshot import Screenshot

    try:
        async with DvtProvider(rsd) as dvt, Screenshot(dvt) as screenshot:
            return await screenshot.get_screenshot()
    except PyMobileDevice3Exception as exc:
        raise classify_capture_error(exc) from exc
    except OSError as exc:
        raise SidecarError(
            ExitCode.CAPTURE_FAILED, f"connection to the device failed: {exc}"
        ) from exc


def classify_capture_error(exc: PyMobileDevice3Exception) -> SidecarError:
    if isinstance(exc, InvalidServiceError):
        return SidecarError(
            ExitCode.CAPTURE_FAILED,
            "the device does not offer the DVT screenshot service; check that Developer Mode "
            f"is enabled and the developer disk image is mounted ({exc})",
        )
    if isinstance(exc, (NotPairedError, PairingError)):
        return SidecarError(ExitCode.PAIRING_REQUIRED, str(exc) or "device is not paired")
    return SidecarError(ExitCode.CAPTURE_FAILED, f"{type(exc).__name__}: {exc}")


async def capture_bytes(
    config: SidecarConfig,
    *,
    open_session: OpenDevice = open_device,
    screenshot: TakeScreenshot = take_screenshot,
) -> bytes:
    try:
        async with asyncio.timeout(config.timeout_seconds):
            session = await open_session(config)
            try:
                logger.info("connected over %s transport", session.transport.value)
                data = await screenshot(session.rsd)
            finally:
                await session.aclose()
    except TimeoutError:
        raise SidecarError(
            ExitCode.CAPTURE_TIMEOUT,
            f"capture did not finish within {config.timeout_seconds:g}s",
        ) from None
    if not data.startswith(PNG_SIGNATURE):
        raise SidecarError(
            ExitCode.CAPTURE_FAILED,
            f"device returned {len(data)} bytes that are not a PNG image",
        )
    return data


async def capture_to_file(
    config: SidecarConfig,
    output: Path,
    *,
    open_session: OpenDevice = open_device,
    screenshot: TakeScreenshot = take_screenshot,
) -> int:
    """Capture one screenshot into `output` and return its size in bytes."""

    data = await capture_bytes(config, open_session=open_session, screenshot=screenshot)
    write_atomically(output, data)
    return len(data)


def write_atomically(output: Path, data: bytes) -> None:
    """Write via a sibling temp file so a reader never sees a partial PNG."""

    try:
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
        )
    except OSError as exc:
        raise SidecarError(
            ExitCode.OUTPUT_WRITE_FAILED, f"cannot create output in {output.parent}: {exc}"
        ) from exc
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(output)
    except OSError as exc:
        temp_path.unlink(missing_ok=True)
        raise SidecarError(ExitCode.OUTPUT_WRITE_FAILED, f"cannot write {output}: {exc}") from exc
