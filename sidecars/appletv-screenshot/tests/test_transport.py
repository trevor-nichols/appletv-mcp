from typing import ClassVar

import pytest
from pymobiledevice3.exceptions import (
    DeviceNotFoundError,
    NoDeviceConnectedError,
    NotPairedError,
    PairingError,
    PyMobileDevice3Exception,
    TunneldConnectionError,
    UserspaceTunnelUnavailableError,
)

from appletv_screenshot.config import SidecarConfig, Transport
from appletv_screenshot.errors import SidecarError
from appletv_screenshot.exit_codes import ExitCode
from appletv_screenshot.transport import (
    DeviceSession,
    TransportFailure,
    classify_tunnel_error,
    most_specific,
    open_device,
    open_native,
    open_tunneld,
    reported_capture_failure,
    transport_order,
)
from tests.fakes import FakeRsd, fake_session

NATIVE_TUNNEL = "pymobiledevice3.remote.native_tunnel"
TUNNELD_API = "pymobiledevice3.tunneld.api"


@pytest.mark.parametrize(
    ("preference", "system", "expected"),
    [
        (Transport.AUTO, "Darwin", [Transport.NATIVE, Transport.USERSPACE, Transport.TUNNELD]),
        (Transport.AUTO, "Linux", [Transport.USERSPACE, Transport.TUNNELD]),
        (Transport.AUTO, "Windows", [Transport.USERSPACE, Transport.TUNNELD]),
        (Transport.NATIVE, "Darwin", [Transport.NATIVE]),
        (Transport.USERSPACE, "Linux", [Transport.USERSPACE]),
        (Transport.TUNNELD, "Linux", [Transport.TUNNELD]),
    ],
)
def test_transport_order(preference: Transport, system: str, expected: list[Transport]) -> None:
    assert transport_order(preference, system) == expected


def test_native_transport_off_macos_is_unavailable_with_a_fix() -> None:
    with pytest.raises(SidecarError) as excinfo:
        transport_order(Transport.NATIVE, "Linux")
    assert excinfo.value.exit_code is ExitCode.TUNNEL_UNAVAILABLE
    assert "configure --transport userspace" in excinfo.value.detail


def test_most_specific_prefers_pairing_over_missing_tunnel() -> None:
    tunnel = SidecarError(ExitCode.TUNNEL_UNAVAILABLE, "native: no remoted")
    pairing = SidecarError(ExitCode.PAIRING_REQUIRED, "tunneld: pairing failed")
    chosen = most_specific([tunnel, pairing])
    assert chosen.exit_code is ExitCode.PAIRING_REQUIRED
    assert chosen.detail == "native: no remoted; tunneld: pairing failed"


def test_most_specific_keeps_order_on_ties_and_passes_single_through() -> None:
    first = SidecarError(ExitCode.DEVICE_NOT_FOUND, "first")
    second = SidecarError(ExitCode.DEVICE_NOT_FOUND, "second")
    assert most_specific([first, second]).detail == "first; second"
    assert most_specific([second]) is second
    with pytest.raises(ValueError, match="no failures"):
        most_specific([])


def test_reported_capture_failure_prefers_userspace_once_it_ran() -> None:
    native = TransportFailure(
        Transport.NATIVE, SidecarError(ExitCode.PAIRING_REQUIRED, "pairing failed")
    )
    userspace = TransportFailure(
        Transport.USERSPACE, SidecarError(ExitCode.DEVICE_NOT_FOUND, "not reachable")
    )
    tunneld = TransportFailure(
        Transport.TUNNELD, SidecarError(ExitCode.TUNNEL_UNAVAILABLE, "daemon down")
    )
    chosen = reported_capture_failure(Transport.AUTO, [native, userspace, tunneld])
    assert chosen.exit_code is ExitCode.DEVICE_NOT_FOUND
    assert chosen.detail == (
        "native: pairing failed; userspace: not reachable; tunneld: daemon down"
    )


def test_reported_capture_failure_keeps_userspace_pairing() -> None:
    userspace = TransportFailure(
        Transport.USERSPACE, SidecarError(ExitCode.PAIRING_REQUIRED, "not paired")
    )
    tunneld = TransportFailure(
        Transport.TUNNELD, SidecarError(ExitCode.DEVICE_NOT_FOUND, "no tunnel")
    )
    chosen = reported_capture_failure(Transport.AUTO, [userspace, tunneld])
    assert chosen.exit_code is ExitCode.PAIRING_REQUIRED


def test_reported_capture_failure_ranks_when_userspace_was_not_attempted() -> None:
    native = TransportFailure(
        Transport.NATIVE, SidecarError(ExitCode.PAIRING_REQUIRED, "pairing failed")
    )
    tunneld = TransportFailure(
        Transport.TUNNELD, SidecarError(ExitCode.TUNNEL_UNAVAILABLE, "daemon down")
    )
    chosen = reported_capture_failure(Transport.AUTO, [native, tunneld])
    assert chosen.exit_code is ExitCode.PAIRING_REQUIRED
    assert chosen.detail == "native: pairing failed; tunneld: daemon down"


def test_reported_capture_failure_rejects_an_empty_list() -> None:
    with pytest.raises(ValueError, match="no failures"):
        reported_capture_failure(Transport.AUTO, [])


class _NotFoundThroughTunnelError(UserspaceTunnelUnavailableError, DeviceNotFoundError):
    """Shape of pymobiledevice3's private native not-found error: identity must win."""


@pytest.mark.parametrize(
    ("exc", "expected", "fragment"),
    [
        (DeviceNotFoundError("udid X"), ExitCode.DEVICE_NOT_FOUND, "udid X"),
        (NoDeviceConnectedError(), ExitCode.DEVICE_NOT_FOUND, "device not found"),
        (_NotFoundThroughTunnelError("gone"), ExitCode.DEVICE_NOT_FOUND, "gone"),
        (NotPairedError(), ExitCode.PAIRING_REQUIRED, "not paired"),
        (PairingError("denied"), ExitCode.PAIRING_REQUIRED, "denied"),
        (
            UserspaceTunnelUnavailableError("pairing failed (code 5): user denied"),
            ExitCode.PAIRING_REQUIRED,
            "pairing failed (code 5)",
        ),
        (
            UserspaceTunnelUnavailableError("libxpc not available"),
            ExitCode.TUNNEL_UNAVAILABLE,
            "libxpc not available",
        ),
        (TunneldConnectionError(), ExitCode.TUNNEL_UNAVAILABLE, "tunneld is not reachable"),
        (PyMobileDevice3Exception("odd"), ExitCode.TUNNEL_UNAVAILABLE, "PyMobileDevice3Exception"),
    ],
)
def test_classify_tunnel_error(exc: Exception, expected: ExitCode, fragment: str) -> None:
    error = classify_tunnel_error(exc)
    assert error.exit_code is expected
    assert fragment in error.detail


async def test_open_device_requires_a_configured_udid() -> None:
    with pytest.raises(SidecarError) as excinfo:
        await open_device(SidecarConfig())
    assert excinfo.value.exit_code is ExitCode.AMBIGUOUS_DEVICE
    assert "configure --udid" in excinfo.value.detail


async def test_open_device_falls_from_native_to_userspace_on_macos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("appletv_screenshot.transport.platform.system", lambda: "Darwin")
    session = fake_session(FakeRsd("00008110-AAAA", "AppleTV14,1"), Transport.USERSPACE)
    attempts: list[Transport] = []

    async def native(config: SidecarConfig) -> DeviceSession:
        attempts.append(Transport.NATIVE)
        raise SidecarError(ExitCode.TUNNEL_UNAVAILABLE, "remoted missing")

    async def userspace(config: SidecarConfig) -> DeviceSession:
        attempts.append(Transport.USERSPACE)
        return session

    async def tunneld(config: SidecarConfig) -> DeviceSession:
        attempts.append(Transport.TUNNELD)
        raise AssertionError("tunneld must not run after userspace succeeds")

    result = await open_device(
        SidecarConfig(udid="00008110-AAAA"),
        {
            Transport.NATIVE: native,
            Transport.USERSPACE: userspace,
            Transport.TUNNELD: tunneld,
        },
    )
    assert result is session
    assert attempts == [Transport.NATIVE, Transport.USERSPACE]


async def test_open_device_on_linux_tries_userspace_before_tunneld(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("appletv_screenshot.transport.platform.system", lambda: "Linux")
    session = fake_session(FakeRsd("00008110-AAAA", "AppleTV14,1"), Transport.USERSPACE)
    attempts: list[Transport] = []

    async def userspace(config: SidecarConfig) -> DeviceSession:
        attempts.append(Transport.USERSPACE)
        return session

    async def tunneld(config: SidecarConfig) -> DeviceSession:
        attempts.append(Transport.TUNNELD)
        raise AssertionError("tunneld must not run after userspace succeeds")

    result = await open_device(
        SidecarConfig(udid="00008110-AAAA"),
        {Transport.USERSPACE: userspace, Transport.TUNNELD: tunneld},
    )
    assert result is session
    assert attempts == [Transport.USERSPACE]


async def test_open_device_falls_through_to_the_next_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("appletv_screenshot.transport.platform.system", lambda: "Darwin")
    session = fake_session(FakeRsd("00008110-AAAA", "AppleTV14,1"))
    attempts: list[Transport] = []

    async def native(config: SidecarConfig) -> DeviceSession:
        attempts.append(Transport.NATIVE)
        raise SidecarError(ExitCode.TUNNEL_UNAVAILABLE, "remoted missing")

    async def userspace(config: SidecarConfig) -> DeviceSession:
        attempts.append(Transport.USERSPACE)
        raise SidecarError(ExitCode.TUNNEL_UNAVAILABLE, "no RemotePairing service")

    async def tunneld(config: SidecarConfig) -> DeviceSession:
        attempts.append(Transport.TUNNELD)
        return session

    result = await open_device(
        SidecarConfig(udid="00008110-AAAA"),
        {
            Transport.NATIVE: native,
            Transport.USERSPACE: userspace,
            Transport.TUNNELD: tunneld,
        },
    )
    assert result is session
    assert attempts == [Transport.NATIVE, Transport.USERSPACE, Transport.TUNNELD]


async def test_open_device_rejects_an_iphone_after_connect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("appletv_screenshot.transport.platform.system", lambda: "Linux")
    session = fake_session(FakeRsd("00008101-CCCC", "iPhone14,2"), Transport.USERSPACE)
    closed = False

    async def userspace(config: SidecarConfig) -> DeviceSession:
        return session

    original = session._close

    async def tracking_close() -> None:
        nonlocal closed
        closed = True
        await original()

    session._close = tracking_close

    with pytest.raises(SidecarError) as excinfo:
        await open_device(
            SidecarConfig(udid="00008101-CCCC", transport=Transport.USERSPACE),
            {Transport.USERSPACE: userspace},
        )
    assert excinfo.value.exit_code is ExitCode.DEVICE_NOT_FOUND
    assert "not an Apple TV" in excinfo.value.detail
    assert closed


async def test_open_device_auto_reports_userspace_not_native_pairing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("appletv_screenshot.transport.platform.system", lambda: "Darwin")

    async def native(config: SidecarConfig) -> DeviceSession:
        raise SidecarError(ExitCode.PAIRING_REQUIRED, "pairing failed (code 5)")

    async def userspace(config: SidecarConfig) -> DeviceSession:
        raise SidecarError(ExitCode.DEVICE_NOT_FOUND, "configured device is not reachable")

    async def tunneld(config: SidecarConfig) -> DeviceSession:
        raise SidecarError(ExitCode.TUNNEL_UNAVAILABLE, "no tunneld reachable")

    with pytest.raises(SidecarError) as excinfo:
        await open_device(
            SidecarConfig(udid="00008110-AAAA"),
            {
                Transport.NATIVE: native,
                Transport.USERSPACE: userspace,
                Transport.TUNNELD: tunneld,
            },
        )
    assert excinfo.value.exit_code is ExitCode.DEVICE_NOT_FOUND
    assert "native: pairing failed (code 5)" in excinfo.value.detail
    assert "userspace: configured device is not reachable" in excinfo.value.detail
    assert "tunneld: no tunneld reachable" in excinfo.value.detail


async def test_open_device_auto_still_reports_userspace_pairing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("appletv_screenshot.transport.platform.system", lambda: "Linux")

    async def userspace(config: SidecarConfig) -> DeviceSession:
        raise SidecarError(ExitCode.PAIRING_REQUIRED, "device is not paired")

    async def tunneld(config: SidecarConfig) -> DeviceSession:
        raise SidecarError(ExitCode.DEVICE_NOT_FOUND, "no tunnel for udid")

    with pytest.raises(SidecarError) as excinfo:
        await open_device(
            SidecarConfig(udid="00008110-AAAA"),
            {Transport.USERSPACE: userspace, Transport.TUNNELD: tunneld},
        )
    assert excinfo.value.exit_code is ExitCode.PAIRING_REQUIRED
    assert "userspace: device is not paired" in excinfo.value.detail
    assert "tunneld: no tunnel for udid" in excinfo.value.detail


async def test_open_device_auto_keeps_all_transport_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("appletv_screenshot.transport.platform.system", lambda: "Darwin")

    async def native(config: SidecarConfig) -> DeviceSession:
        raise SidecarError(ExitCode.TUNNEL_UNAVAILABLE, "remoted missing")

    async def userspace(config: SidecarConfig) -> DeviceSession:
        raise SidecarError(ExitCode.TUNNEL_UNAVAILABLE, "no RemotePairing service")

    async def tunneld(config: SidecarConfig) -> DeviceSession:
        raise SidecarError(ExitCode.PAIRING_REQUIRED, "pairing failed (code 5)")

    with pytest.raises(SidecarError) as excinfo:
        await open_device(
            SidecarConfig(udid="00008110-AAAA"),
            {
                Transport.NATIVE: native,
                Transport.USERSPACE: userspace,
                Transport.TUNNELD: tunneld,
            },
        )
    assert excinfo.value.exit_code is ExitCode.TUNNEL_UNAVAILABLE
    assert "native: remoted missing" in excinfo.value.detail
    assert "userspace: no RemotePairing service" in excinfo.value.detail
    assert "tunneld: pairing failed (code 5)" in excinfo.value.detail


class _FakeNativeTunnel:
    instances: ClassVar[list[_FakeNativeTunnel]] = []
    rsd: ClassVar[FakeRsd | None] = None
    failure: ClassVar[Exception | None] = None

    def __init__(self, serial: str | None = None) -> None:
        self.serial = serial
        self.closed = False
        _FakeNativeTunnel.instances.append(self)

    async def aopen(self) -> FakeRsd:
        if _FakeNativeTunnel.failure is not None:
            raise _FakeNativeTunnel.failure
        assert _FakeNativeTunnel.rsd is not None
        return _FakeNativeTunnel.rsd

    async def aclose(self) -> None:
        self.closed = True


@pytest.fixture
def native_tunnel(monkeypatch: pytest.MonkeyPatch) -> type[_FakeNativeTunnel]:
    _FakeNativeTunnel.instances = []
    _FakeNativeTunnel.rsd = FakeRsd("00008110-AAAA", "AppleTV14,1")
    _FakeNativeTunnel.failure = None
    monkeypatch.setattr(f"{NATIVE_TUNNEL}.NativeRemotedTunnel", _FakeNativeTunnel)
    return _FakeNativeTunnel


async def test_open_native_uses_the_configured_udid_as_serial(
    native_tunnel: type[_FakeNativeTunnel],
) -> None:
    session = await open_native(SidecarConfig(udid="00008110-AAAA"))

    assert session.transport is Transport.NATIVE
    assert session.rsd is native_tunnel.rsd
    assert [tunnel.serial for tunnel in native_tunnel.instances] == ["00008110-AAAA"]
    await session.aclose()
    assert native_tunnel.instances[0].closed


async def test_open_native_without_a_udid_is_ambiguous(
    native_tunnel: type[_FakeNativeTunnel],
) -> None:
    with pytest.raises(SidecarError) as excinfo:
        await open_native(SidecarConfig())
    assert excinfo.value.exit_code is ExitCode.AMBIGUOUS_DEVICE
    assert native_tunnel.instances == []


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (
            UserspaceTunnelUnavailableError("pairing failed (code 5): denied"),
            ExitCode.PAIRING_REQUIRED,
        ),
        (UserspaceTunnelUnavailableError("libxpc missing"), ExitCode.TUNNEL_UNAVAILABLE),
        (DeviceNotFoundError("00008110-AAAA"), ExitCode.DEVICE_NOT_FOUND),
        (OSError("socket closed"), ExitCode.TUNNEL_UNAVAILABLE),
    ],
)
async def test_open_native_classifies_open_failures(
    native_tunnel: type[_FakeNativeTunnel], failure: Exception, expected: ExitCode
) -> None:
    native_tunnel.failure = failure

    with pytest.raises(SidecarError) as excinfo:
        await open_native(SidecarConfig(udid="00008110-AAAA"))

    assert excinfo.value.exit_code is expected


async def test_open_tunneld_returns_the_configured_device(monkeypatch: pytest.MonkeyPatch) -> None:
    rsd = FakeRsd("00008110-AAAA")
    seen: list[tuple[str, tuple[str, int]]] = []

    async def by_udid(udid: str, address: tuple[str, int] = ("127.0.0.1", 49151)) -> FakeRsd:
        seen.append((udid, address))
        return rsd

    monkeypatch.setattr(f"{TUNNELD_API}.get_tunneld_device_by_udid", by_udid)

    session = await open_tunneld(
        SidecarConfig(udid="00008110-AAAA", tunneld_host="lab-mac", tunneld_port=49152)
    )

    assert session.transport is Transport.TUNNELD
    assert session.rsd is rsd
    assert seen == [("00008110-AAAA", ("lab-mac", 49152))]
    assert not rsd.closed
    await session.aclose()
    assert rsd.closed


async def test_open_tunneld_without_a_tunnel_for_the_udid_is_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def by_udid(udid: str, address: tuple[str, int] = ("127.0.0.1", 49151)) -> None:
        return None

    monkeypatch.setattr(f"{TUNNELD_API}.get_tunneld_device_by_udid", by_udid)

    with pytest.raises(SidecarError) as excinfo:
        await open_tunneld(SidecarConfig(udid="00008110-AAAA"))

    assert excinfo.value.exit_code is ExitCode.DEVICE_NOT_FOUND
    assert "no tunnel for 00008110-AAAA" in excinfo.value.detail
    assert "pymobiledevice3 remote pair" in excinfo.value.detail


async def test_open_tunneld_without_a_daemon_names_the_fix(monkeypatch: pytest.MonkeyPatch) -> None:
    async def by_udid(udid: str, address: tuple[str, int] = ("127.0.0.1", 49151)) -> None:
        raise TunneldConnectionError()

    monkeypatch.setattr(f"{TUNNELD_API}.get_tunneld_device_by_udid", by_udid)

    with pytest.raises(SidecarError) as excinfo:
        await open_tunneld(SidecarConfig(udid="00008110-AAAA"))

    assert excinfo.value.exit_code is ExitCode.TUNNEL_UNAVAILABLE
    assert "127.0.0.1:49151" in excinfo.value.detail
    assert "sudo pymobiledevice3 remote tunneld" in excinfo.value.detail
