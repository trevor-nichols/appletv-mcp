"""Non-destructive setup diagnostics."""

from collections.abc import Awaitable, Callable
from typing import TextIO

from appletv_mcp.application.ports.apple_tv import DiscoveredDevice
from appletv_mcp.composition import Runtime, create_runtime
from appletv_mcp.domain.enums import FeatureAvailability, NormalizedOperation
from appletv_mcp.domain.errors import AppleTVError
from appletv_mcp.domain.models.capabilities import AppleTVCapabilities
from appletv_mcp.infrastructure.config.repository import FileSettingsRepository
from appletv_mcp.infrastructure.pyatv.storage import PyAtvStorageAdapter
from appletv_mcp.interfaces.cli.rendering import CheckResult

RuntimeFactory = Callable[[], Awaitable[Runtime]]


async def run_doctor(
    *,
    stdout: TextIO,
    settings_repository: FileSettingsRepository | None = None,
    storage: PyAtvStorageAdapter | None = None,
    runtime_factory: RuntimeFactory | None = None,
) -> int:
    checks: list[CheckResult] = []
    repository = settings_repository or FileSettingsRepository()
    storage_adapter = storage or PyAtvStorageAdapter()
    runtime: Runtime | None = None

    try:
        settings = repository.load()
        checks.append(CheckResult("Configuration", True, f"loaded from {repository.path}"))
    except AppleTVError as exc:
        checks.append(CheckResult("Configuration", False, exc.message))
        _write_checks(stdout, checks)
        return 1

    try:
        await storage_adapter.load()
        checks.append(CheckResult("pyatv storage", True, "loaded"))
    except AppleTVError as exc:
        checks.append(CheckResult("pyatv storage", False, exc.message))
        _write_checks(stdout, checks)
        return 1

    factory = runtime_factory or (
        lambda: create_runtime(settings_repository=repository, storage=storage_adapter)
    )
    try:
        runtime = await factory()
        try:
            device = await runtime.connection_manager.resolve_device()
            checks.extend(
                _discovery_checks(device, settings.device_identifier, settings.preferred_host)
            )
        except AppleTVError as exc:
            checks.append(CheckResult("Device discovery", False, exc.message))

        try:
            status = await runtime.controller.status()
            connected = status.connection.value == "connected"
            checks.append(CheckResult("Connection", connected, status.connection.value))
        except AppleTVError as exc:
            checks.append(CheckResult("Connection", False, exc.message))
            _write_checks(stdout, checks)
            return 1 if any(not check.ok and check.required for check in checks) else 0

        try:
            capabilities = await runtime.controller.capabilities()
            checks.extend(_capability_checks(capabilities))
        except AppleTVError as exc:
            checks.append(CheckResult("Capabilities", False, exc.message, required=False))
    finally:
        if runtime is not None:
            await runtime.aclose()
        else:
            await storage_adapter.close()

    _write_checks(stdout, checks)
    return 1 if any(not check.ok and check.required for check in checks) else 0


def _discovery_checks(
    device: DiscoveredDevice,
    identifier: str,
    preferred_host: str | None,
) -> list[CheckResult]:
    checks = [
        CheckResult("Device discovery", True, f"{device.name} at {device.address}"),
        CheckResult(
            "Stable identifier",
            device.matches(identifier),
            "matched" if device.matches(identifier) else "mismatch",
        ),
    ]
    if preferred_host is None:
        checks.append(
            CheckResult(
                "Preferred host",
                True,
                f"unset; discovered {device.address}",
                required=False,
            )
        )
    elif device.address == preferred_host:
        checks.append(CheckResult("Preferred host", True, preferred_host))
    else:
        checks.append(
            CheckResult(
                "Preferred host",
                True,
                f"configured {preferred_host}, currently {device.address}",
                required=False,
            )
        )
    return checks


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
