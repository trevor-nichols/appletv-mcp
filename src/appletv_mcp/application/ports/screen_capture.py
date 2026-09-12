"""Port that keeps screen-capture transport details out of the application layer."""

from typing import Protocol

from appletv_mcp.domain.models.screen import CapturedScreen


class ScreenCaptureBackend(Protocol):
    """Produce one validated PNG of the configured Apple TV's screen.

    Implementations own process execution, timeouts, temporary files, and the
    translation of transport failures into `ScreenCaptureError` subclasses.
    """

    async def capture(self) -> CapturedScreen:
        """Capture the current screen or raise a `ScreenCaptureError`."""
        ...
