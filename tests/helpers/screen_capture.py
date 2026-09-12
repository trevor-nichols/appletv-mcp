"""Fakes for the observation path. Independent of the pyatv fakes on purpose."""

import asyncio

from appletv_mcp.domain.errors import ScreenCaptureError
from appletv_mcp.domain.models.screen import CapturedScreen
from tests.helpers.png import FAKE_SCREEN_PNG


class FakeScreenCaptureBackend:
    """Scriptable `ScreenCaptureBackend` that records concurrency."""

    def __init__(
        self,
        *,
        png: bytes = FAKE_SCREEN_PNG,
        fail_with: ScreenCaptureError | None = None,
        hold: asyncio.Event | None = None,
    ) -> None:
        self.png = png
        self.fail_with = fail_with
        self.hold = hold
        self.calls = 0
        self.active = 0
        self.max_active = 0
        self.started: list[int] = []

    async def capture(self) -> CapturedScreen:
        self.calls += 1
        self.started.append(self.calls)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            if self.hold is not None:
                await self.hold.wait()
            await asyncio.sleep(0)
            if self.fail_with is not None:
                raise self.fail_with
            return CapturedScreen(data=self.png)
        finally:
            self.active -= 1
