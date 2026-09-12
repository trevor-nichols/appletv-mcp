"""Reach the configured Apple TV's RemoteXPC service discovery (RSD).

Two transports are supported, both grounded in pymobiledevice3 11.12.4:

native   macOS only. Rides Apple's own `remoted` tunnel through `remotepairingd`
         (`NativeRemotedTunnel`). No root. Pairing is Apple's, not pymobiledevice3's.
tunneld  Any OS. Reuses a running `sudo pymobiledevice3 remote tunneld`, which
         pairs Wi-Fi devices with the record written by `pymobiledevice3 remote pair`.

The in-process userspace tunnel is not offered: it needs usbmux, which a Wi-Fi
Apple TV does not provide.
"""

import platform
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import Protocol

from pymobiledevice3.exceptions import (
    DeviceNotFoundError,
    NoDeviceConnectedError,
    NotPairedError,
    PairingError,
    PyMobileDevice3Exception,
    TunneldConnectionError,
    UserspaceTunnelUnavailableError,
)
from pymobiledevice3.remote.remote_service_discovery import RemoteServiceDiscoveryService

from appletv_screenshot.config import SidecarConfig, Transport
from appletv_screenshot.errors import SidecarError
from appletv_screenshot.exit_codes import ExitCode
from appletv_screenshot.target import Candidate, select_target

# pymobiledevice3 11.12.4 reports a refused/unpaired native tunnel as a
# UserspaceTunnelUnavailableError whose message starts with this text.
_NATIVE_PAIRING_FAILURE_PREFIX = "pairing failed"

_SPECIFICITY = {
    ExitCode.PAIRING_REQUIRED: 0,
    ExitCode.AMBIGUOUS_DEVICE: 1,
    ExitCode.DEVICE_NOT_FOUND: 2,
    ExitCode.TUNNEL_UNAVAILABLE: 3,
}


@dataclass(slots=True)
class DeviceSession:
    rsd: RemoteServiceDiscoveryService
    transport: Transport
    _close: Callable[[], Awaitable[None]]

    async def aclose(self) -> None:
        await self._close()


class Opener(Protocol):
    async def __call__(self, config: SidecarConfig) -> DeviceSession: ...


def transport_order(preference: Transport, system: str | None = None) -> list[Transport]:
    current = system or platform.system()
    if preference is Transport.AUTO:
        order = [Transport.NATIVE] if current == "Darwin" else []
        order.append(Transport.TUNNELD)
        return order
    if preference is Transport.NATIVE and current != "Darwin":
        raise SidecarError(
            ExitCode.TUNNEL_UNAVAILABLE,
            "the native transport needs macOS; use `configure --transport tunneld` here",
        )
    return [preference]


def most_specific(failures: list[SidecarError]) -> SidecarError:
    """Pick the failure to report when every transport failed.

    Pairing and identity problems name what the operator must fix; a missing
    tunnel daemon is the least informative and loses ties to anything else.
    """

    if not failures:
        raise ValueError("no failures to choose from")
    ranked = sorted(
        enumerate(failures), key=lambda item: (_SPECIFICITY.get(item[1].exit_code, 9), item[0])
    )
    chosen = ranked[0][1]
    if len(failures) == 1:
        return chosen
    detail = "; ".join(failure.detail for failure in failures)
    return SidecarError(chosen.exit_code, detail)


async def open_device(
    config: SidecarConfig, openers: dict[Transport, Opener] | None = None
) -> DeviceSession:
    """Open an RSD session over the first transport that succeeds."""

    table = openers or {Transport.NATIVE: open_native, Transport.TUNNELD: open_tunneld}
    failures: list[SidecarError] = []
    for transport in transport_order(config.transport):
        try:
            return await table[transport](config)
        except SidecarError as exc:
            failures.append(SidecarError(exc.exit_code, f"{transport.value}: {exc.detail}"))
    raise most_specific(failures)


async def open_native(config: SidecarConfig) -> DeviceSession:
    from pymobiledevice3.remote.native_tunnel import NativeRemotedTunnel, browse_native_devices

    udid = config.udid
    if udid is None:
        try:
            devices = await browse_native_devices(timeout=config.discovery_timeout_seconds)
        except PyMobileDevice3Exception as exc:
            raise classify_tunnel_error(exc) from exc
        candidates = [
            Candidate(udid=str(info["udid"]), name=_optional_str(info.get("name")))
            for info in devices
            if isinstance(info.get("udid"), str)
        ]
        udid = select_target(candidates, None)
    tunnel = NativeRemotedTunnel(serial=udid)
    try:
        rsd = await tunnel.aopen()
    except PyMobileDevice3Exception as exc:
        raise classify_tunnel_error(exc) from exc
    except OSError as exc:
        raise SidecarError(ExitCode.TUNNEL_UNAVAILABLE, f"native tunnel failed: {exc}") from exc
    return DeviceSession(rsd=rsd, transport=Transport.NATIVE, _close=tunnel.aclose)


async def open_tunneld(config: SidecarConfig) -> DeviceSession:
    from pymobiledevice3.tunneld.api import get_tunneld_device_by_udid, get_tunneld_devices

    host, port = config.tunneld_address
    try:
        if config.udid is not None:
            rsd = await get_tunneld_device_by_udid(config.udid, config.tunneld_address)
            if rsd is None:
                raise SidecarError(
                    ExitCode.DEVICE_NOT_FOUND,
                    f"tunneld at {host}:{port} has no tunnel for {config.udid}; pair with "
                    "`pymobiledevice3 remote pair` and check the daemon's device list",
                )
            return DeviceSession(rsd=rsd, transport=Transport.TUNNELD, _close=rsd.close)
        rsds = await get_tunneld_devices(config.tunneld_address)
    except TunneldConnectionError as exc:
        raise SidecarError(
            ExitCode.TUNNEL_UNAVAILABLE,
            f"no tunneld reachable at {host}:{port}; start it with "
            "`sudo pymobiledevice3 remote tunneld`",
        ) from exc
    except PyMobileDevice3Exception as exc:
        raise classify_tunnel_error(exc) from exc

    candidates = [
        Candidate(udid=rsd.udid, name=rsd.product_type) for rsd in rsds if rsd.udid is not None
    ]
    try:
        udid = select_target(candidates, None)
    except SidecarError:
        await _close_all(rsds)
        raise
    chosen = next(rsd for rsd in rsds if rsd.udid == udid)
    await _close_all(rsd for rsd in rsds if rsd is not chosen)
    return DeviceSession(rsd=chosen, transport=Transport.TUNNELD, _close=chosen.close)


def classify_tunnel_error(exc: Exception) -> SidecarError:
    """Map a pymobiledevice3 failure while reaching the device to an exit code."""

    if isinstance(exc, (DeviceNotFoundError, NoDeviceConnectedError)):
        return SidecarError(ExitCode.DEVICE_NOT_FOUND, str(exc) or "device not found")
    if isinstance(exc, (NotPairedError, PairingError)):
        return SidecarError(ExitCode.PAIRING_REQUIRED, str(exc) or "device is not paired")
    if isinstance(exc, UserspaceTunnelUnavailableError):
        message = str(exc)
        if message.startswith(_NATIVE_PAIRING_FAILURE_PREFIX):
            return SidecarError(ExitCode.PAIRING_REQUIRED, message)
        return SidecarError(ExitCode.TUNNEL_UNAVAILABLE, message or "tunnel unavailable")
    if isinstance(exc, TunneldConnectionError):
        return SidecarError(ExitCode.TUNNEL_UNAVAILABLE, "tunneld is not reachable")
    return SidecarError(ExitCode.TUNNEL_UNAVAILABLE, f"{type(exc).__name__}: {exc}")


async def _close_all(rsds: Iterable[RemoteServiceDiscoveryService]) -> None:
    for rsd in rsds:
        await rsd.close()


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
