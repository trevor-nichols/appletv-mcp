"""Interactive device profile setup."""

import math
from collections.abc import Callable, Sequence
from typing import TextIO

from appletv_mcp.application.ports.apple_tv import DiscoveredDevice
from appletv_mcp.application.services.apple_tv_controller import AppleTVController
from appletv_mcp.composition import create_runtime
from appletv_mcp.domain.errors import AppleTVError, PairingRequiredError
from appletv_mcp.domain.models.settings import Settings
from appletv_mcp.infrastructure.config.repository import FileSettingsRepository
from appletv_mcp.infrastructure.pyatv.device_models import partition_discovered_devices
from appletv_mcp.infrastructure.pyatv.discovery import PyAtvScanner
from appletv_mcp.infrastructure.pyatv.storage import PyAtvStorageAdapter
from appletv_mcp.interfaces.cli.rendering import render_capability_summary, render_device_row

Selector = Callable[[Sequence[DiscoveredDevice]], DiscoveredDevice]


class ConfigureError(Exception):
    def __init__(self, message: str, *, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def validate_scan_timeout(value: float) -> float:
    if not math.isfinite(value) or value <= 0:
        raise ConfigureError("Scan timeout must be a finite number greater than zero.")
    return value


async def run_configure(
    *,
    stdin: TextIO,
    stdout: TextIO,
    scan_timeout_seconds: float = 5.0,
    selector: Selector | None = None,
    settings_repository: FileSettingsRepository | None = None,
    storage: PyAtvStorageAdapter | None = None,
) -> int:
    timeout = validate_scan_timeout(scan_timeout_seconds)
    repository = settings_repository or FileSettingsRepository()
    storage_adapter = storage or PyAtvStorageAdapter()
    runtime = None
    try:
        pyatv_storage = await storage_adapter.load()
        scanner = PyAtvScanner(pyatv_storage)
        stdout.write("Scanning for Apple TVs...\n")
        devices = await scanner.scan(timeout=timeout)
        candidates = _apple_tv_candidates(devices, stdout)
        stdout.write("Discovered devices:\n")
        for index, device in enumerate(candidates, start=1):
            stdout.write(
                render_device_row(index, device.name, device.identifier, device.address) + "\n"
            )
        chosen = (selector or _prompt_selector(stdin, stdout))(candidates)
        settings = Settings(
            device_identifier=chosen.identifier,
            device_name=chosen.name,
            preferred_host=chosen.address,
            scan_timeout_seconds=timeout,
        )
        repository.save(settings)
        stdout.write(
            f"Saved identifier={settings.device_identifier} host={settings.preferred_host}\n"
        )
        runtime = await create_runtime(settings_repository=repository, storage=storage_adapter)
        await _verify(runtime.controller, stdout)
        stdout.write(f"Configuration written to {repository.path}\n")
        return 0
    except ConfigureError:
        raise
    except AppleTVError as exc:
        raise ConfigureError(exc.message) from exc
    finally:
        if runtime is not None:
            await runtime.aclose()
        else:
            await storage_adapter.close()


def _apple_tv_candidates(
    devices: Sequence[DiscoveredDevice], stdout: TextIO
) -> list[DiscoveredDevice]:
    apple_tvs, unknowns, others = partition_discovered_devices(list(devices))
    if others:
        names = ", ".join(device.name for device in others)
        stdout.write(f"Ignored non-Apple-TV device(s): {names}\n")
    if unknowns:
        stdout.write(
            "Warning: one or more devices have an unknown model and may not be Apple TVs.\n"
        )
    candidates = [*apple_tvs, *unknowns]
    if not candidates:
        detail = ""
        if others:
            detail = f" Found non-TV device(s): {', '.join(device.name for device in others)}."
        raise ConfigureError(
            "No Apple TVs were discovered. Confirm the TV is on the same network "
            "and that pairing exists in `atvremote` storage (`atvremote wizard`)."
            + detail
        )
    return candidates


def _prompt_selector(stdin: TextIO, stdout: TextIO) -> Selector:
    def select(devices: Sequence[DiscoveredDevice]) -> DiscoveredDevice:
        if len(devices) == 1:
            stdout.write("Only one device found; selecting it.\n")
            return devices[0]
        stdout.write(f"Enter device number (1-{len(devices)}): ")
        stdout.flush()
        raw = stdin.readline().strip()
        try:
            index = int(raw)
        except ValueError as exc:
            raise ConfigureError("Selection must be a number.") from exc
        if index < 1 or index > len(devices):
            raise ConfigureError("Selection is out of range.")
        return devices[index - 1]

    return select


async def _verify(controller: AppleTVController, stdout: TextIO) -> None:
    try:
        status = await controller.status()
        stdout.write(
            f"Connected to {status.device.name or status.device.identifier} "
            f"({status.connection.value}).\n"
        )
        capabilities = await controller.capabilities()
        stdout.write("Capability summary:\n")
        for line in render_capability_summary(
            {key: value.value for key, value in capabilities.as_mapping().items()}
        ):
            stdout.write(f"  {line}\n")
    except PairingRequiredError as exc:
        raise ConfigureError(str(exc)) from exc
    except AppleTVError as exc:
        raise ConfigureError(f"Configuration saved but verification failed: {exc.message}") from exc
