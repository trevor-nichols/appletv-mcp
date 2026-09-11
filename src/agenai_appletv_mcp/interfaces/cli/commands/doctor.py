"""Non-destructive setup diagnostics."""

from collections.abc import Awaitable, Callable
from typing import TextIO

from agenai_appletv_mcp.application.ports.apple_tv import DiscoveredDevice
from agenai_appletv_mcp.composition import Runtime, create_runtime
from agenai_appletv_mcp.domain.enums import FeatureAvailability, NormalizedOperation
from agenai_appletv_mcp.domain.errors import AppleTVError
from agenai_appletv_mcp.domain.models.capabilities import AppleTVCapabilities
from agenai_appletv_mcp.infrastructure.config.repository import FileSettingsRepository
from agenai_appletv_mcp.infrastructure.pyatv.discovery import PyAtvScanner
from agenai_appletv_mcp.infrastructure.pyatv.storage import PyAtvStorageAdapter
from agenai_appletv_mcp.interfaces.cli.rendering import CheckResult

RuntimeFactory = Callable[[], Awaitable[Runtime]]


async def run_doctor(
    *,
    stdout: TextIO,
    settings_repository: FileSettingsRepository | None = None,
    storage: PyAtvStorageAdapter | None = None,
    scanner: PyAtvScanner | None = None,
    runtime_factory: RuntimeFactory | None = None,
) -> int:
    checks: list[CheckResult] = []
    repository = settings_repository or FileSettingsRepository()
    storage_adapter = storage or PyAtvStorageAdapter()

    settings = None
    try:
        settings = repository.load()
        checks.append(CheckResult("Configuration", True, f"loaded from {repository.path}"))
    except AppleTVError as exc:
        checks.append(CheckResult("Configuration", False, exc.message))
        _write_checks(stdout, checks)
        return 1

    try:
        pyatv_storage = await storage_adapter.load()
        checks.append(CheckResult("pyatv storage", True, "loaded"))
    except AppleTVError as exc:
        checks.append(CheckResult("pyatv storage", False, exc.message))
        _write_checks(stdout, checks)
        return 1

    scanner = scanner or PyAtvScanner(pyatv_storage)
    discovered: DiscoveredDevice | None = None
    try:
        devices = await scanner.scan(
            timeout=settings.scan_timeout_seconds,
            identifier=settings.device_identifier,
        )
        for device in devices:
            if device.matches(settings.device_identifier):
                discovered = device
                break
        if discovered is None:
            checks.append(
                CheckResult(
                    "Device discovery",
                    False,
                    f"identifier {settings.device_identifier} was not found",
                )
            )
        else:
            checks.append(
                CheckResult(
                    "Device discovery",
                    True,
                    f"{discovered.name} at {discovered.address}",
                )
            )
            matched = discovered.matches(settings.device_identifier)
            checks.append(
                CheckResult(
                    "Stable identifier",
                    matched,
                    "matched" if matched else "mismatch",
                )
            )
            if settings.preferred_host is None:
                checks.append(
                    CheckResult(
                        "Preferred host",
                        True,
                        f"unset; discovered {discovered.address}",
                        required=False,
                    )
                )
            elif discovered.address == settings.preferred_host:
                checks.append(CheckResult("Preferred host", True, settings.preferred_host))
            else:
                checks.append(
                    CheckResult(
                        "Preferred host",
                        True,
                        f"configured {settings.preferred_host}, currently {discovered.address}",
                        required=False,
                    )
                )
    except AppleTVError as exc:
        checks.append(CheckResult("Device discovery", False, exc.message))

    factory = runtime_factory or (
        lambda: create_runtime(settings_repository=repository, storage=storage_adapter)
    )
    runtime = await factory()
    try:
        try:
            status = await runtime.controller.status()
            connected = status.connection.value == "connected"
            checks.append(
                CheckResult(
                    "Connection",
                    connected,
                    status.connection.value,
                )
            )
        except AppleTVError as exc:
            checks.append(CheckResult("Connection", False, exc.message))
            _write_checks(stdout, checks)
            return 1

        try:
            capabilities = await runtime.controller.capabilities()
            checks.extend(_capability_checks(capabilities))
        except AppleTVError as exc:
            checks.append(CheckResult("Capabilities", False, exc.message, required=False))
    finally:
        await runtime.aclose()

    _write_checks(stdout, checks)
    return 1 if any(not check.ok and check.required for check in checks) else 0


def _capability_checks(capabilities: AppleTVCapabilities) -> list[CheckResult]:
    groups: list[tuple[str, tuple[NormalizedOperation, ...]]] = [
        ("Power", (NormalizedOperation.POWER_ON, NormalizedOperation.POWER_OFF)),
        ("Apps", (NormalizedOperation.LIST_APPS, NormalizedOperation.LAUNCH_APP)),
        (
            "Navigation",
            (
                NormalizedOperation.NAVIGATE_UP,
                NormalizedOperation.NAVIGATE_SELECT,
                NormalizedOperation.NAVIGATE_BACK,
            ),
        ),
        ("Playback", (NormalizedOperation.PLAY, NormalizedOperation.PAUSE)),
        ("Keyboard", (NormalizedOperation.TEXT_SET, NormalizedOperation.KEYBOARD_FOCUS)),
        ("Volume", (NormalizedOperation.VOLUME_SET, NormalizedOperation.VOLUME_UP)),
    ]
    results: list[CheckResult] = []
    for name, operations in groups:
        states = [capabilities.for_operation(operation) for operation in operations]
        if FeatureAvailability.AVAILABLE in states or FeatureAvailability.UNKNOWN in states:
            detail = ", ".join(
                f"{op.value}={st.value}" for op, st in zip(operations, states, strict=True)
            )
            results.append(CheckResult(name, True, detail, required=False))
        elif FeatureAvailability.UNAVAILABLE in states:
            results.append(CheckResult(name, True, "currently unavailable", required=False))
        else:
            results.append(CheckResult(name, True, "unsupported", required=False))
    return results


def _write_checks(stdout: TextIO, checks: list[CheckResult]) -> None:
    for check in checks:
        stdout.write(check.line() + "\n")
