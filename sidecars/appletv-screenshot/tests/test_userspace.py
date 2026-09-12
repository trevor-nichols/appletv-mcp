from collections.abc import AsyncIterator, Iterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from pymobiledevice3.exceptions import DeviceNotFoundError
from pymobiledevice3.remote import tunnel_service
from pymobiledevice3.remote.common import TunnelProtocol
from pymobiledevice3.remote.tunnel_service import TunnelResult
from pymobiledevice3.remote.userspace_tunnel import UserspaceTun

from appletv_screenshot.config import SidecarConfig, Transport
from appletv_screenshot.errors import SidecarError
from appletv_screenshot.exit_codes import ExitCode
from appletv_screenshot.userspace import open_userspace, session_from_provider
from tests.fakes import FakeRsd, fake_session

REMOTE_PAIRING = "pymobiledevice3.remote.tunnel_service"
USERSPACE_TUNNEL = "pymobiledevice3.remote.userspace_tunnel"


@dataclass
class _FakePairing:
    remote_identifier: str
    remote_device_model: str
    closed: bool = False

    async def close(self) -> None:
        self.closed = True


async def test_open_userspace_requires_a_configured_udid() -> None:
    with pytest.raises(SidecarError) as excinfo:
        await open_userspace(SidecarConfig())
    assert excinfo.value.exit_code is ExitCode.AMBIGUOUS_DEVICE
    assert "configure --udid" in excinfo.value.detail


async def test_open_userspace_uses_the_matching_apple_tv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    phone = _FakePairing("00008101-CCCC", "iPhone14,2")
    tv = _FakePairing("00008110-AAAA", "AppleTV14,1")
    session = fake_session(FakeRsd("00008110-AAAA", "AppleTV14,1"), Transport.USERSPACE)
    connected: list[str] = []

    async def browse(
        *, bonjour_timeout: float = 3.0, udid: str | None = None
    ) -> list[_FakePairing]:
        assert udid == "00008110-AAAA"
        assert bonjour_timeout == 3.0
        return [phone, tv]

    async def connect(provider: _FakePairing) -> object:
        connected.append(provider.remote_identifier)
        return session

    monkeypatch.setattr(f"{REMOTE_PAIRING}.get_remote_pairing_tunnel_services", browse)
    monkeypatch.setattr("appletv_screenshot.userspace.session_from_provider", connect)

    result = await open_userspace(SidecarConfig(udid="00008110-AAAA"))

    assert result is session
    assert connected == ["00008110-AAAA"]
    assert phone.closed
    assert not tv.closed


async def test_open_userspace_rejects_a_configured_iphone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    phone = _FakePairing("00008101-CCCC", "iPhone14,2")

    async def browse(
        *, bonjour_timeout: float = 3.0, udid: str | None = None
    ) -> list[_FakePairing]:
        return [phone]

    monkeypatch.setattr(f"{REMOTE_PAIRING}.get_remote_pairing_tunnel_services", browse)

    with pytest.raises(SidecarError) as excinfo:
        await open_userspace(SidecarConfig(udid="00008101-CCCC"))

    assert excinfo.value.exit_code is ExitCode.DEVICE_NOT_FOUND
    assert "not an Apple TV" in excinfo.value.detail
    assert phone.closed


async def test_open_userspace_with_no_matching_service_is_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def browse(
        *, bonjour_timeout: float = 3.0, udid: str | None = None
    ) -> list[_FakePairing]:
        return []

    monkeypatch.setattr(f"{REMOTE_PAIRING}.get_remote_pairing_tunnel_services", browse)

    with pytest.raises(SidecarError) as excinfo:
        await open_userspace(SidecarConfig(udid="00008110-AAAA"))

    assert excinfo.value.exit_code is ExitCode.DEVICE_NOT_FOUND
    assert "00008110-AAAA is not reachable" in excinfo.value.detail


class _FakeTun(UserspaceTun):
    def __init__(self) -> None:
        self.peer: str | None = None

    def set_peer(self, device_addr: str) -> None:
        self.peer = device_addr


def _tunnel_result(tun: object) -> TunnelResult:
    return TunnelResult(
        interface="utun-userspace",
        address="fd12:3456::1",
        port=58783,
        protocol=TunnelProtocol.TCP,
        # Test double. session_from_provider only reads client.tun.
        client=SimpleNamespace(tun=tun),  # type: ignore[arg-type]
    )


@dataclass
class _RecordingProvider:
    events: list[str]
    tunnel_result: TunnelResult | None = None
    tunnel_error: BaseException | None = None
    remote_identifier: str = "00008110-AAAA"
    remote_device_model: str = "AppleTV14,1"

    def start_tcp_tunnel(self) -> AbstractAsyncContextManager[TunnelResult]:
        events = self.events
        result = self.tunnel_result
        error = self.tunnel_error

        @asynccontextmanager
        async def tunnel() -> AsyncIterator[TunnelResult]:
            events.append("tunnel-enter")
            if error is not None:
                raise error
            if result is None:
                raise AssertionError("tunnel_result is required when start_tcp_tunnel succeeds")
            try:
                yield result
            finally:
                events.append("tunnel-exit")

        return tunnel()

    async def close(self) -> None:
        self.events.append("provider-close")


class _FakeDialPlane:
    def __init__(self, tun: object, address: str, events: list[str]) -> None:
        self.tun = tun
        self.address = address
        self.events = events

    async def __aenter__(self) -> _FakeDialPlane:
        self.events.append("dial-enter")
        return self

    async def __aexit__(self, *_exc: object) -> None:
        self.events.append("dial-exit")

    async def dial(self, *args: object, **kwargs: object) -> None:
        raise AssertionError("dial is unused in these tests")


class _FakeSessionRsd:
    def __init__(
        self,
        address: tuple[str, int],
        *,
        open_connection: object = None,
        auxiliary_metadata: object = None,
        events: list[str] | None = None,
        connect_error: BaseException | None = None,
        product_type: str = "AppleTV14,1",
    ) -> None:
        self.address = address
        self.open_connection = open_connection
        self.auxiliary_metadata = auxiliary_metadata
        self.udid = "00008110-AAAA"
        self.product_type = product_type
        self.events = events if events is not None else []
        self.connect_error = connect_error

    async def connect(self) -> None:
        self.events.append("rsd-connect")
        if self.connect_error is not None:
            raise self.connect_error

    async def close(self) -> None:
        self.events.append("rsd-close")


def _patch_session_stack(
    monkeypatch: pytest.MonkeyPatch,
    events: list[str],
    *,
    connect_error: BaseException | None = None,
) -> None:
    def dial_plane(tun: object, address: str) -> _FakeDialPlane:
        return _FakeDialPlane(tun, address, events)

    def rsd_factory(
        address: tuple[str, int],
        *,
        open_connection: object = None,
        auxiliary_metadata: object = None,
    ) -> _FakeSessionRsd:
        return _FakeSessionRsd(
            address,
            open_connection=open_connection,
            auxiliary_metadata=auxiliary_metadata,
            events=events,
            connect_error=connect_error,
        )

    monkeypatch.setattr(f"{USERSPACE_TUNNEL}.UserspaceDialPlane", dial_plane)
    monkeypatch.setattr("appletv_screenshot.userspace.RemoteServiceDiscoveryService", rsd_factory)


@pytest.fixture
def reset_userspace_flag() -> Iterator[None]:
    tunnel_service.USE_USERSPACE_TUNNEL = False
    yield
    tunnel_service.USE_USERSPACE_TUNNEL = False


async def test_session_from_provider_success_resets_flag_and_closes_in_stack_order(
    monkeypatch: pytest.MonkeyPatch, reset_userspace_flag: None
) -> None:
    events: list[str] = []
    tun = _FakeTun()
    provider = _RecordingProvider(events, tunnel_result=_tunnel_result(tun))
    _patch_session_stack(monkeypatch, events)

    session = await session_from_provider(provider)

    assert session.transport is Transport.USERSPACE
    assert tun.peer == "fd12:3456::1"
    assert tunnel_service.USE_USERSPACE_TUNNEL is True
    assert events == ["tunnel-enter", "dial-enter", "rsd-connect"]
    await session.aclose()
    assert tunnel_service.USE_USERSPACE_TUNNEL is False
    assert events == [
        "tunnel-enter",
        "dial-enter",
        "rsd-connect",
        "rsd-close",
        "dial-exit",
        "tunnel-exit",
        "provider-close",
    ]


async def test_session_from_provider_resets_flag_when_start_tcp_tunnel_fails(
    monkeypatch: pytest.MonkeyPatch, reset_userspace_flag: None
) -> None:
    events: list[str] = []
    provider = _RecordingProvider(events, tunnel_error=OSError("tunnel refused"))
    _patch_session_stack(monkeypatch, events)

    with pytest.raises(SidecarError) as excinfo:
        await session_from_provider(provider)

    assert excinfo.value.exit_code is ExitCode.TUNNEL_UNAVAILABLE
    assert "tunnel refused" in excinfo.value.detail
    assert tunnel_service.USE_USERSPACE_TUNNEL is False
    assert events == ["tunnel-enter", "provider-close"]


async def test_session_from_provider_rejects_a_non_userspace_tun(
    monkeypatch: pytest.MonkeyPatch, reset_userspace_flag: None
) -> None:
    events: list[str] = []
    provider = _RecordingProvider(events, tunnel_result=_tunnel_result(object()))
    _patch_session_stack(monkeypatch, events)

    with pytest.raises(SidecarError) as excinfo:
        await session_from_provider(provider)

    assert excinfo.value.exit_code is ExitCode.TUNNEL_UNAVAILABLE
    assert "in-process TUN" in excinfo.value.detail
    assert tunnel_service.USE_USERSPACE_TUNNEL is False
    assert events == ["tunnel-enter", "tunnel-exit", "provider-close"]


async def test_session_from_provider_unwinds_when_rsd_connect_fails(
    monkeypatch: pytest.MonkeyPatch, reset_userspace_flag: None
) -> None:
    events: list[str] = []
    tun = _FakeTun()
    provider = _RecordingProvider(events, tunnel_result=_tunnel_result(tun))
    _patch_session_stack(monkeypatch, events, connect_error=DeviceNotFoundError("gone"))

    with pytest.raises(SidecarError) as excinfo:
        await session_from_provider(provider)

    assert excinfo.value.exit_code is ExitCode.DEVICE_NOT_FOUND
    assert tunnel_service.USE_USERSPACE_TUNNEL is False
    assert events == [
        "tunnel-enter",
        "dial-enter",
        "rsd-connect",
        "rsd-close",
        "dial-exit",
        "tunnel-exit",
        "provider-close",
    ]
