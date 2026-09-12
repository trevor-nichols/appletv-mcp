"""In-process userspace RSD over RemotePairing.

Apple TVs are reached over Wi-Fi RemotePairing, not usbmux. pymobiledevice3 11.12.4's
`UserspaceRsdTunnel` calls `create_using_usbmux` first and only falls back to
RemotePairing after a USB lockdown session exists, so this module starts at
`get_remote_pairing_tunnel_services` and then uses the same userspace TUN and
dial-plane that `UserspaceRsdTunnel` composes.
"""

from collections.abc import Iterable
from contextlib import AbstractAsyncContextManager, AsyncExitStack
from typing import Protocol

from pymobiledevice3.exceptions import (
    NotPairedError,
    PairingError,
    PyMobileDevice3Exception,
)
from pymobiledevice3.remote.remote_service_discovery import RemoteServiceDiscoveryService
from pymobiledevice3.remote.tunnel_service import TunnelResult

from appletv_screenshot.config import SidecarConfig, Transport
from appletv_screenshot.errors import SidecarError
from appletv_screenshot.exit_codes import ExitCode
from appletv_screenshot.target import (
    Candidate,
    require_apple_tv_product,
    require_configured_udid,
    select_target,
)
from appletv_screenshot.transport import DeviceSession, classify_tunnel_error


class RemotePairingProvider(Protocol):
    remote_identifier: str

    @property
    def remote_device_model(self) -> str: ...

    def start_tcp_tunnel(self) -> AbstractAsyncContextManager[TunnelResult]: ...

    async def close(self) -> None: ...


async def open_userspace(config: SidecarConfig) -> DeviceSession:
    """Open an in-process userspace RSD session to the configured Apple TV."""

    from pymobiledevice3.remote.tunnel_service import get_remote_pairing_tunnel_services

    udid = require_configured_udid(config.udid)
    try:
        services = await get_remote_pairing_tunnel_services(
            bonjour_timeout=config.discovery_timeout_seconds,
            udid=udid,
        )
    except PyMobileDevice3Exception as exc:
        raise classify_tunnel_error(exc) from exc

    try:
        chosen = _pick_apple_tv_service(list(services), udid)
    except SidecarError:
        await _close_providers(services)
        raise
    await _close_providers(service for service in services if service is not chosen)
    return await session_from_provider(chosen)


def _pick_apple_tv_service(
    services: list[RemotePairingProvider], udid: str
) -> RemotePairingProvider:
    candidates: list[Candidate] = []
    for service in services:
        identifier = service.remote_identifier
        if not identifier:
            continue
        candidates.append(Candidate(udid=identifier, product_type=_provider_product_type(service)))
    selected = select_target(candidates, udid)
    return next(service for service in services if service.remote_identifier == selected)


def _provider_product_type(service: RemotePairingProvider) -> str | None:
    try:
        model = service.remote_device_model
    except AssertionError, AttributeError:
        return None
    return model if isinstance(model, str) and model else None


async def session_from_provider(provider: RemotePairingProvider) -> DeviceSession:
    """Attach a userspace TUN plus dial-plane to an already-connected pairing service."""

    from pymobiledevice3.remote import tunnel_service
    from pymobiledevice3.remote.userspace_tunnel import UserspaceDialPlane, UserspaceTun

    tunnel_service.USE_USERSPACE_TUNNEL = True
    stack = AsyncExitStack()
    try:
        stack.push_async_callback(provider.close)
        result = await stack.enter_async_context(provider.start_tcp_tunnel())
        tun = result.client.tun
        if not isinstance(tun, UserspaceTun):
            raise SidecarError(
                ExitCode.TUNNEL_UNAVAILABLE,
                "userspace tunnel did not install an in-process TUN device",
            )
        tun.set_peer(result.address)
        dial_plane = await stack.enter_async_context(UserspaceDialPlane(tun, result.address))
        rsd = RemoteServiceDiscoveryService(
            (result.address, result.port),
            open_connection=dial_plane.dial,
            auxiliary_metadata=result.auxiliary_metadata,
        )
        stack.push_async_callback(rsd.close)
        await rsd.connect()
        require_apple_tv_product(rsd.udid or provider.remote_identifier, rsd.product_type)
    except SidecarError:
        await stack.aclose()
        tunnel_service.USE_USERSPACE_TUNNEL = False
        raise
    except (NotPairedError, PairingError) as exc:
        await stack.aclose()
        tunnel_service.USE_USERSPACE_TUNNEL = False
        raise classify_tunnel_error(exc) from exc
    except PyMobileDevice3Exception as exc:
        await stack.aclose()
        tunnel_service.USE_USERSPACE_TUNNEL = False
        raise classify_tunnel_error(exc) from exc
    except OSError as exc:
        await stack.aclose()
        tunnel_service.USE_USERSPACE_TUNNEL = False
        raise SidecarError(ExitCode.TUNNEL_UNAVAILABLE, f"userspace tunnel failed: {exc}") from exc
    except BaseException:
        await stack.aclose()
        tunnel_service.USE_USERSPACE_TUNNEL = False
        raise

    async def close() -> None:
        tunnel_service.USE_USERSPACE_TUNNEL = False
        await stack.aclose()

    return DeviceSession(rsd=rsd, transport=Transport.USERSPACE, _close=close)


async def _close_providers(providers: Iterable[RemotePairingProvider]) -> None:
    for provider in providers:
        await provider.close()
