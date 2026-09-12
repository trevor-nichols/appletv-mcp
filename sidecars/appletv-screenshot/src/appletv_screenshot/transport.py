"""Reach the configured Apple TV's RemoteXPC service discovery (RSD).

Four transports, grounded in pymobiledevice3 11.12.4:

native     macOS only. Rides Apple's `remoted` tunnel (`NativeRemotedTunnel`).
userspace  Any OS. In-process PyTCP tunnel over RemotePairing bonjour. No root,
           no usbmux, no `tunneld`. This is the no-root path for a Wi-Fi Apple TV.
tunneld    Any OS. Reuses a running `sudo pymobiledevice3 remote tunneld`.
auto       native (macOS only), then userspace, then tunneld.

`PreferredRsdTunnel` is not used as the auto policy. In 11.12.4 it wraps
`UserspaceRsdTunnel`, which calls `create_using_usbmux` before RemotePairing, so a
Wi-Fi Apple TV never reaches the working path. Device selection also stays here
so capture cannot follow `serial=None` (first device).
"""

import platform
from collections.abc import Awaitable, Callable
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
from appletv_screenshot.target import require_apple_tv_product, require_configured_udid

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
        order.append(Transport.USERSPACE)
        order.append(Transport.TUNNELD)
        return order
    if preference is Transport.NATIVE and current != "Darwin":
        raise SidecarError(
            ExitCode.TUNNEL_UNAVAILABLE,
            "the native transport needs macOS; use `configure --transport userspace` here",
        )
    return [preference]


@dataclass(frozen=True, slots=True)
class TransportFailure:
    transport: Transport
    error: SidecarError


def most_specific(failures: list[SidecarError]) -> SidecarError:
    """Rank failures inside one credential domain.

    Pairing and identity name what the operator must fix in that domain. A missing
    tunnel daemon is the least informative and loses ties to anything else. AUTO
    does not use this ranking when userspace already ran. See
    `reported_capture_failure`.
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


def reported_capture_failure(
    preference: Transport, failures: list[TransportFailure]
) -> SidecarError:
    """Choose the failure AUTO or a pinned transport reports after every attempt failed.

    AUTO still tries native, then userspace, then tunneld. Diagnosis is separate.
    Pairing is per credential domain. Once userspace ran, that outcome is the
    report. Native pairing does not outrank a later userspace device or tunnel
    failure. If userspace never ran, ranking among the attempts that did can
    still prefer pairing.
    """

    if not failures:
        raise ValueError("no failures to choose from")
    chosen = _diagnostic_error(preference, failures)
    detail = "; ".join(f"{item.transport.value}: {item.error.detail}" for item in failures)
    return SidecarError(chosen.exit_code, detail)


def _diagnostic_error(preference: Transport, failures: list[TransportFailure]) -> SidecarError:
    if preference is Transport.AUTO:
        for item in failures:
            if item.transport is Transport.USERSPACE:
                return item.error
    return most_specific([item.error for item in failures])


async def open_device(
    config: SidecarConfig, openers: dict[Transport, Opener] | None = None
) -> DeviceSession:
    """Open an RSD session over the first transport that succeeds."""

    require_configured_udid(config.udid)
    table = openers or _default_openers()
    failures: list[TransportFailure] = []
    for transport in transport_order(config.transport):
        try:
            session = await table[transport](config)
        except SidecarError as exc:
            failures.append(TransportFailure(transport, exc))
            continue
        try:
            require_apple_tv_product(
                session.rsd.udid or config.udid or "", session.rsd.product_type
            )
        except SidecarError:
            await session.aclose()
            raise
        return session
    raise reported_capture_failure(config.transport, failures)


def _default_openers() -> dict[Transport, Opener]:
    from appletv_screenshot.userspace import open_userspace

    return {
        Transport.NATIVE: open_native,
        Transport.USERSPACE: open_userspace,
        Transport.TUNNELD: open_tunneld,
    }


async def open_native(config: SidecarConfig) -> DeviceSession:
    from pymobiledevice3.remote.native_tunnel import NativeRemotedTunnel

    udid = require_configured_udid(config.udid)
    tunnel = NativeRemotedTunnel(serial=udid)
    try:
        rsd = await tunnel.aopen()
    except PyMobileDevice3Exception as exc:
        raise classify_tunnel_error(exc) from exc
    except OSError as exc:
        raise SidecarError(ExitCode.TUNNEL_UNAVAILABLE, f"native tunnel failed: {exc}") from exc
    return DeviceSession(rsd=rsd, transport=Transport.NATIVE, _close=tunnel.aclose)


async def open_tunneld(config: SidecarConfig) -> DeviceSession:
    from pymobiledevice3.tunneld.api import get_tunneld_device_by_udid

    udid = require_configured_udid(config.udid)
    host, port = config.tunneld_address
    try:
        rsd = await get_tunneld_device_by_udid(udid, config.tunneld_address)
    except TunneldConnectionError as exc:
        raise SidecarError(
            ExitCode.TUNNEL_UNAVAILABLE,
            f"no tunneld reachable at {host}:{port}; start it with "
            "`sudo pymobiledevice3 remote tunneld`",
        ) from exc
    except PyMobileDevice3Exception as exc:
        raise classify_tunnel_error(exc) from exc
    if rsd is None:
        raise SidecarError(
            ExitCode.DEVICE_NOT_FOUND,
            f"tunneld at {host}:{port} has no tunnel for {udid}; pair with "
            "`pymobiledevice3 remote pair` and check the daemon's device list",
        )
    return DeviceSession(rsd=rsd, transport=Transport.TUNNELD, _close=rsd.close)


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
