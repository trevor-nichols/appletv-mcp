"""Fakes shared by the sidecar tests. None of them touch a device."""

import asyncio
from collections.abc import Awaitable, Callable

from pymobiledevice3.remote.remote_service_discovery import RemoteServiceDiscoveryService

from appletv_screenshot.config import SidecarConfig, Transport
from appletv_screenshot.transport import DeviceSession

FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24


class FakeRsd(RemoteServiceDiscoveryService):
    """A real RSD object that never connects; only identity and close are observed."""

    def __init__(self, udid: str | None, product_type: str | None = None) -> None:
        super().__init__(("::1", 0))
        self.udid = udid
        self.product_type = product_type
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def fake_session(rsd: FakeRsd, transport: Transport = Transport.TUNNELD) -> DeviceSession:
    return DeviceSession(rsd=rsd, transport=transport, _close=rsd.close)


def opener_returning(
    session: DeviceSession, *, delay: float = 0.0
) -> Callable[[SidecarConfig], Awaitable[DeviceSession]]:
    async def open_session(config: SidecarConfig) -> DeviceSession:
        if delay:
            await asyncio.sleep(delay)
        return session

    return open_session


def screenshot_returning(
    data: bytes, *, delay: float = 0.0
) -> Callable[[RemoteServiceDiscoveryService], Awaitable[bytes]]:
    async def screenshot(rsd: RemoteServiceDiscoveryService) -> bytes:
        if delay:
            await asyncio.sleep(delay)
        return data

    return screenshot
