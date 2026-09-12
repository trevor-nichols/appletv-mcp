"""Semantic screen observation, kept apart from the pyatv control path."""

import asyncio
import logging

from appletv_mcp.application.ports.screen_capture import ScreenCaptureBackend
from appletv_mcp.domain.models.screen import CapturedScreen

logger = logging.getLogger(__name__)


class ScreenCaptureService:
    """Serialize screenshot requests and delegate them to one backend.

    The lock is independent of the controller's command lock: a screenshot
    must never wait behind remote-control traffic, and the helper process
    behind the backend can only serve one capture at a time.
    """

    def __init__(self, backend: ScreenCaptureBackend) -> None:
        self._backend = backend
        self._lock = asyncio.Lock()

    async def capture(self) -> CapturedScreen:
        async with self._lock:
            logger.debug("Screen capture requested")
            screen = await self._backend.capture()
            logger.debug("Screen capture completed with %d bytes", len(screen.data))
            return screen
