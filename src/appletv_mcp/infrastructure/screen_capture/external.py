"""Screen capture through the external `appletv-screenshot` helper process."""

import asyncio
import logging
import os
import shutil
import tempfile
import time
from asyncio.subprocess import DEVNULL, Process
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
_OUTPUT_FILENAME = "screen.png"
_TEMP_PREFIX = "appletv-mcp-screen-"


def resolve_screen_capture_executable(settings: ScreenCaptureSettings) -> Path | None:
    """Locate the helper without running it. `None` means the backend is absent."""

    command = Path(settings.command)
    if len(command.parts) > 1:
        return command if command.is_file() and os.access(command, os.X_OK) else None
    found = shutil.which(settings.command)
    return Path(found) if found is not None else None


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
            async with asyncio.timeout(self._settings.timeout_seconds):
                returncode = await process.wait()
        except TimeoutError:
            await self._stop(process)
            logger.warning(
                "Screen-capture helper exceeded %.1fs and was stopped",
                self._settings.timeout_seconds,
            )
            raise ScreenCaptureTimeoutError(TIMEOUT_MESSAGE) from None
        except asyncio.CancelledError:
            await self._stop(process)
            raise
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

    async def _stop(self, process: Process) -> None:
        if process.returncode is not None:
            return
        try:
            process.terminate()
        except ProcessLookupError:
            return
        try:
            async with asyncio.timeout(self._terminate_grace_seconds):
                await process.wait()
        except TimeoutError:
            logger.warning("Screen-capture helper ignored SIGTERM; killing it")
            process.kill()
            await process.wait()

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
