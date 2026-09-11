"""Discovery, connect, cache, reconnect, and shutdown for one Apple TV."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import pyatv
from pyatv.interface import AppleTV, BaseConfig, DeviceListener, Storage

from agenai_appletv_mcp.application.ports.apple_tv import DiscoveredDevice
from agenai_appletv_mcp.application.ports.settings import SettingsRepository
from agenai_appletv_mcp.domain.errors import (
    DeviceConnectionError,
    DeviceNotConfiguredError,
    DeviceNotFoundError,
    DeviceUnreachableError,
)
from agenai_appletv_mcp.domain.models.settings import Settings
from agenai_appletv_mcp.infrastructure.pyatv.exception_map import translate_exception

logger = logging.getLogger(__name__)

ScanFn = Callable[..., Awaitable[list[DiscoveredDevice]]]
ConnectFn = Callable[[object], Awaitable[Any]]


class ConnectionManager(DeviceListener):
    """Lazy connection owner. Startup must not require the Apple TV to be online."""

    def __init__(
        self,
        *,
        settings_repository: SettingsRepository,
        storage: Storage | None = None,
        scan: ScanFn,
        connect: ConnectFn | None = None,
    ) -> None:
        self._settings_repository = settings_repository
        self._storage = storage
        self._scan = scan
        self._connect = connect or self._default_connect
        self._connect_lock = asyncio.Lock()
        self._atv: AppleTV | None = None
        self._address: str | None = None
        self._closed = False

    @property
    def cached(self) -> bool:
        return self._atv is not None

    @property
    def current_address(self) -> str | None:
        return self._address

    async def get(self) -> AppleTV:
        async with self._connect_lock:
            self._ensure_open()
            if self._atv is not None:
                return self._atv
            return await self._establish()

    async def reconnect(self) -> AppleTV:
        async with self._connect_lock:
            self._ensure_open()
            await self._close_cached()
            return await self._establish()

    def invalidate(self) -> None:
        self._atv = None
        self._address = None

    async def close(self) -> None:
        async with self._connect_lock:
            self._closed = True
            await self._close_cached()

    def connection_lost(self, exception: Exception) -> None:
        logger.warning("Apple TV connection lost: %s", exception)
        self.invalidate()

    def connection_closed(self) -> None:
        logger.info("Apple TV connection closed")
        self.invalidate()

    async def _establish(self) -> AppleTV:
        settings = self._load_settings()
        device = await self._discover(settings)
        atv = await self._connect_device(device, settings)
        self._atv = atv
        self._address = device.address
        atv.listener = self
        self._maybe_persist_host(settings, device.address)
        logger.info(
            "Connected to Apple TV identifier=%s host=%s",
            settings.device_identifier,
            device.address,
        )
        return atv

    def _load_settings(self) -> Settings:
        try:
            return self._settings_repository.load()
        except DeviceNotConfiguredError:
            raise
        except Exception as exc:
            raise DeviceNotConfiguredError(str(exc)) from exc

    async def _discover(self, settings: Settings) -> DiscoveredDevice:
        timeout = settings.scan_timeout_seconds
        identifier = settings.device_identifier
        if settings.preferred_host:
            targeted = await self._scan_preferred_host(settings.preferred_host, identifier, timeout)
            if targeted is not None:
                return targeted
        matches = await self._scan(
            timeout=timeout,
            identifier=identifier,
            hosts=None,
        )
        for device in matches:
            if device.matches(identifier):
                return device
        label = settings.device_name or identifier
        raise DeviceNotFoundError(f'Configured Apple TV "{label}" was not found on the network.')

    async def _scan_preferred_host(
        self,
        host: str,
        identifier: str,
        timeout: float,
    ) -> DiscoveredDevice | None:
        try:
            found = await self._scan(timeout=timeout, identifier=None, hosts=[host])
        except Exception as exc:
            logger.info("Preferred-host scan at %s failed: %s", host, exc)
            return None
        for device in found:
            if device.matches(identifier):
                return device
            logger.warning(
                "Preferred host %s belongs to a different Apple TV (identifier %s); ignoring it",
                host,
                device.identifier,
            )
        return None

    async def _connect_device(self, device: DiscoveredDevice, settings: Settings) -> AppleTV:
        if device.config is None:
            raise DeviceUnreachableError(
                "Discovery returned a device without a connectable configuration.",
                may_have_been_delivered=False,
            )
        try:
            async with asyncio.timeout(settings.command_timeout_seconds):
                return await self._connect(device.config)
        except TimeoutError as exc:
            raise DeviceUnreachableError(
                "Connecting to the Apple TV timed out.",
                may_have_been_delivered=False,
            ) from exc
        except Exception as exc:
            mapped = translate_exception(exc, operation="connect", may_have_been_delivered=False)
            if mapped is exc:
                raise DeviceUnreachableError(
                    "Apple TV could not be reached.",
                    may_have_been_delivered=False,
                ) from exc
            raise mapped from exc

    def _maybe_persist_host(self, settings: Settings, address: str) -> None:
        if settings.preferred_host == address:
            return
        try:
            self._settings_repository.update_preferred_host(address)
        except Exception:
            logger.exception("Failed to persist updated preferred_host=%s", address)

    async def _close_cached(self) -> None:
        atv = self._atv
        self._atv = None
        self._address = None
        if atv is None:
            return
        try:
            pending = atv.close()
        except Exception:
            logger.debug("Error while closing Apple TV connection", exc_info=True)
            return
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    def _ensure_open(self) -> None:
        if self._closed:
            raise DeviceConnectionError(
                "The Apple TV connection manager has been shut down.",
                may_have_been_delivered=False,
            )

    async def _default_connect(self, config: object) -> AppleTV:
        if self._storage is None:
            raise DeviceConnectionError(
                "pyatv storage is not available.",
                may_have_been_delivered=False,
            )
        if not isinstance(config, BaseConfig):
            raise DeviceUnreachableError(
                "Discovery returned a device without a connectable configuration.",
                may_have_been_delivered=False,
            )
        loop = asyncio.get_running_loop()
        return await pyatv.connect(config, loop, storage=self._storage)
