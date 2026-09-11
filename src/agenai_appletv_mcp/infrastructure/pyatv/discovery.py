"""Network discovery of Apple TVs through pyatv."""

import asyncio
import logging
from collections.abc import Sequence

import pyatv
from pyatv.interface import BaseConfig, Storage

from agenai_appletv_mcp.application.ports.apple_tv import DiscoveredDevice
from agenai_appletv_mcp.domain.errors import CommandTimeoutError, DeviceUnreachableError
from agenai_appletv_mcp.infrastructure.pyatv.exception_map import translate_exception

logger = logging.getLogger(__name__)


class PyAtvScanner:
    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    async def scan(
        self,
        *,
        timeout: float,
        identifier: str | None = None,
        hosts: Sequence[str] | None = None,
    ) -> list[DiscoveredDevice]:
        loop = asyncio.get_running_loop()
        pyatv_timeout = max(1, round(timeout))
        try:
            async with asyncio.timeout(timeout):
                configs = await pyatv.scan(
                    loop,
                    timeout=pyatv_timeout,
                    identifier=identifier,
                    hosts=list(hosts) if hosts else None,
                    storage=self._storage,
                )
        except TimeoutError as exc:
            raise CommandTimeoutError(
                "Apple TV discovery timed out.",
                may_have_been_delivered=False,
            ) from exc
        except Exception as exc:
            mapped = translate_exception(exc, operation="discovery", may_have_been_delivered=False)
            if mapped is exc:
                raise DeviceUnreachableError(
                    "Apple TV discovery failed.",
                    may_have_been_delivered=False,
                ) from exc
            raise mapped from exc
        devices = [_to_discovered(config) for config in configs if config.identifier]
        logger.info("Discovered %d Apple TV candidate(s)", len(devices))
        return devices


def _to_discovered(config: BaseConfig) -> DiscoveredDevice:
    identifier = config.identifier or ""
    return DiscoveredDevice(
        identifier=identifier,
        all_identifiers=tuple(config.all_identifiers),
        name=config.name,
        address=str(config.address),
        model=config.device_info.model_str,
        config=config,
    )
