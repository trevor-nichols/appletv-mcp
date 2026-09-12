"""Screen capture through the external `appletv-screenshot` helper process."""

import asyncio
import logging
import os
import shutil
import tempfile
import time
from asyncio.subprocess import DEVNULL, PIPE, Process
from collections.abc import Awaitable, Sequence
from pathlib import Path

from appletv_mcp.domain.errors import (
    ScreenCaptureInvalidImageError,
    ScreenCaptureTimeoutError,
    ScreenCaptureUnavailableError,
)
from appletv_mcp.domain.models.screen import CapturedScreen
from appletv_mcp.domain.models.settings import ScreenCaptureSettings
from appletv_mcp.infrastructure.screen_capture.contract import (
    HELPER_CAPTURE_SUBCOMMAND,
    HELPER_MISSING_MESSAGE,
    HELPER_OUTPUT_FLAG,
    INVALID_IMAGE_MESSAGE,
    TIMEOUT_MESSAGE,
    HelperExitCode,
    error_for_exit_status,
)
from appletv_mcp.infrastructure.screen_capture.png import inspect_png

logger = logging.getLogger(__name__)

DEFAULT_TERMINATE_GRACE_SECONDS = 2.0
HELPER_PROBE_TIMEOUT_SECONDS = 5.0
_OUTPUT_FILENAME = "screen.png"
_TEMP_PREFIX = "appletv-mcp-screen-"


def resolve_screen_capture_executable(settings: ScreenCaptureSettings) -> Path | None:
    """Locate the helper without running it. `None` means the backend is absent."""

    command = Path(settings.command)
    if len(command.parts) > 1:
        return command if command.is_file() and os.access(command, os.X_OK) else None
    found = shutil.which(settings.command)
    return Path(found) if found is not None else None


async def run_helper_command(
    executable: Path,
    arguments: Sequence[str],
    *,
    timeout_seconds: float = HELPER_PROBE_TIMEOUT_SECONDS,
    terminate_grace_seconds: float = DEFAULT_TERMINATE_GRACE_SECONDS,
) -> tuple[int, str]:
    """Run the helper with stdout captured. Used by doctor probes, not by capture."""

    process = await asyncio.create_subprocess_exec(
        str(executable),
        *arguments,
        stdin=DEVNULL,
        stdout=PIPE,
        stderr=DEVNULL,
    )
    stdout, _stderr = await _await_helper(
        process, process.communicate(), timeout_seconds, terminate_grace_seconds
    )
    text = stdout.decode("utf-8", errors="replace").strip()
    returncode = process.returncode
    return (returncode if returncode is not None else 1), text


async def _await_helper[T](
    process: Process,
    operation: Awaitable[T],
    timeout_seconds: float,
    terminate_grace_seconds: float,
) -> T:
    try:
        async with asyncio.timeout(timeout_seconds):
            return await operation
    except TimeoutError:
        await _stop_process(process, terminate_grace_seconds)
        raise
    except asyncio.CancelledError:
        await _stop_process(process, terminate_grace_seconds)
        raise


async def _stop_process(process: Process, terminate_grace_seconds: float) -> None:
    if process.returncode is not None:
        return
    try:
        process.terminate()
    except ProcessLookupError:
        return
    try:
        async with asyncio.timeout(terminate_grace_seconds):
            await process.wait()
    except TimeoutError:
        logger.warning("Screen-capture helper ignored SIGTERM; killing it")
        process.kill()
        await process.wait()


class ExternalScreenCaptureBackend:
    """Run one helper process per capture and return its validated PNG."""

    def __init__(
        self,
        settings: ScreenCaptureSettings,
        *,
        temp_root: Path | None = None,
        terminate_grace_seconds: float = DEFAULT_TERMINATE_GRACE_SECONDS,
    ) -> None:
        self._settings = settings
        self._temp_root = temp_root
        self._terminate_grace_seconds = terminate_grace_seconds

    async def capture(self) -> CapturedScreen:
        executable = resolve_screen_capture_executable(self._settings)
        if executable is None:
            raise ScreenCaptureUnavailableError(HELPER_MISSING_MESSAGE)
        workdir = Path(tempfile.mkdtemp(prefix=_TEMP_PREFIX, dir=self._temp_root))
        try:
            output = workdir / _OUTPUT_FILENAME
            await self._run_helper(executable, workdir, output)
            return self._load_output(output)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    async def _run_helper(self, executable: Path, workdir: Path, output: Path) -> None:
        started = time.monotonic()
        logger.debug("Starting screen-capture helper %s", executable)
        try:
            process = await asyncio.create_subprocess_exec(
                str(executable),
                HELPER_CAPTURE_SUBCOMMAND,
                HELPER_OUTPUT_FLAG,
                str(output),
                cwd=workdir,
                stdin=DEVNULL,
                stdout=DEVNULL,
                stderr=DEVNULL,
            )
        except OSError as exc:
            logger.warning("Screen-capture helper %s could not start: %s", executable, exc)
            raise ScreenCaptureUnavailableError(
                "Screen capture is unavailable because the configured screenshot helper could "
                f"not be started ({exc.strerror or 'unknown error'}). Run `appletv-mcp doctor`."
            ) from exc
        try:
            returncode = await _await_helper(
                process,
                process.wait(),
                self._settings.timeout_seconds,
                self._terminate_grace_seconds,
            )
        except TimeoutError:
            logger.warning(
                "Screen-capture helper exceeded %.1fs and was stopped",
                self._settings.timeout_seconds,
            )
            raise ScreenCaptureTimeoutError(TIMEOUT_MESSAGE) from None
        elapsed = time.monotonic() - started
        if returncode != HelperExitCode.SUCCESS:
            error = error_for_exit_status(returncode)
            logger.warning(
                "Screen-capture helper exited with status %d after %.2fs: %s",
                returncode,
                elapsed,
                type(error).__name__,
            )
            raise error
        logger.debug("Screen-capture helper exited successfully after %.2fs", elapsed)

    def _load_output(self, output: Path) -> CapturedScreen:
        try:
            size = output.stat().st_size
        except FileNotFoundError:
            raise ScreenCaptureInvalidImageError(INVALID_IMAGE_MESSAGE) from None
        limit = self._settings.max_image_bytes
        if size > limit:
            raise ScreenCaptureInvalidImageError(
                f"The screen-capture helper returned a {size}-byte image, above the configured "
                f"limit of {limit} bytes."
            )
        data = output.read_bytes()
        info = inspect_png(data)
        if info is None:
            raise ScreenCaptureInvalidImageError(INVALID_IMAGE_MESSAGE)
        logger.debug("Captured %dx%d PNG (%d bytes)", info.width, info.height, info.size)
        return CapturedScreen(data=data)
