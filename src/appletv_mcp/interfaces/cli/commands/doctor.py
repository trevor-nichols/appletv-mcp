"""Non-destructive setup diagnostics."""

from collections.abc import Awaitable, Callable
from typing import TextIO

from appletv_mcp.application.ports.apple_tv import DiscoveredDevice
from appletv_mcp.composition import Runtime, create_runtime
from appletv_mcp.domain.enums import FeatureAvailability, NormalizedOperation
from appletv_mcp.domain.errors import AppleTVError
from appletv_mcp.domain.models.capabilities import AppleTVCapabilities
from appletv_mcp.domain.models.settings import ScreenCaptureSettings, Settings
from appletv_mcp.infrastructure.config.repository import FileSettingsRepository
from appletv_mcp.infrastructure.pyatv.storage import PyAtvStorageAdapter
from appletv_mcp.infrastructure.screen_capture import (
    inspect_png,
    resolve_screen_capture_executable,
)
from appletv_mcp.interfaces.cli.rendering import CheckResult, CheckStatus, exit_code_for

RuntimeFactory = Callable[[], Awaitable[Runtime]]

OK = CheckStatus.OK
FAIL = CheckStatus.FAIL
SKIP = CheckStatus.SKIP


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

    try:
        settings = repository.load()
        checks.append(CheckResult("Configuration", OK, f"loaded from {repository.path}"))
    except AppleTVError as exc:
        checks.append(CheckResult("Configuration", FAIL, exc.message))
        _write_checks(stdout, checks)
        return exit_code_for(checks)

    try:
        await storage_adapter.load()
        checks.append(CheckResult("pyatv storage", OK, "loaded"))
    except AppleTVError as exc:
        checks.append(CheckResult("pyatv storage", FAIL, exc.message))
        _write_checks(stdout, checks)
        return exit_code_for(checks)

    factory = runtime_factory or (
        lambda: create_runtime(settings_repository=repository, storage=storage_adapter)
    )
    runtime: Runtime | None = None
    try:
        runtime = await factory()
        checks.extend(await _control_checks(runtime, settings))
        checks.extend(await _screen_capture_checks(runtime, settings.screen_capture))
    finally:
        if runtime is not None:
            await runtime.aclose()
        else:
            await storage_adapter.close()

    _write_checks(stdout, checks)
    return exit_code_for(checks)


async def _control_checks(runtime: Runtime, settings: Settings) -> list[CheckResult]:
    checks: list[CheckResult] = []
    try:
        device = await runtime.connection_manager.resolve_device()
        checks.extend(
            _discovery_checks(device, settings.device_identifier, settings.preferred_host)
        )
    except AppleTVError as exc:
        checks.append(CheckResult("Device discovery", FAIL, exc.message))

    try:
        status = await runtime.controller.status()
        connected = status.connection.value == "connected"
        checks.append(CheckResult("Connection", OK if connected else FAIL, status.connection.value))
    except AppleTVError as exc:
        checks.append(CheckResult("Connection", FAIL, exc.message))
        return checks

    try:
        capabilities = await runtime.controller.capabilities()
        checks.extend(_capability_checks(capabilities))
    except AppleTVError as exc:
        checks.append(CheckResult("Capabilities", FAIL, exc.message, required=False))
    return checks


async def _screen_capture_checks(
    runtime: Runtime, settings: ScreenCaptureSettings
) -> list[CheckResult]:
    executable = resolve_screen_capture_executable(settings)
    if executable is None:
        return [
            CheckResult(
                "Screen capture helper",
                SKIP,
                f"optional backend not available ({settings.command} not found)",
                required=False,
            )
        ]
    checks = [CheckResult("Screen capture helper", OK, str(executable), required=False)]
    try:
        screen = await runtime.screen_capture.capture()
    except AppleTVError as exc:
        checks.append(CheckResult("Screen capture", FAIL, exc.message, required=False))
        return checks
    info = inspect_png(screen.data)
    size = f"{info.width}x{info.height} " if info is not None else ""
    checks.append(
        CheckResult("Screen capture", OK, f"{size}PNG, {len(screen.data)} bytes", required=False)
    )
    return checks


def _discovery_checks(
    device: DiscoveredDevice,
    identifier: str,
    preferred_host: str | None,
) -> list[CheckResult]:
    matched = device.matches(identifier)
    checks = [
        CheckResult("Device discovery", OK, f"{device.name} at {device.address}"),
        CheckResult(
            "Stable identifier", OK if matched else FAIL, "matched" if matched else "mismatch"
        ),
    ]
    if preferred_host is None:
        checks.append(
            CheckResult(
                "Preferred host",
                OK,
                f"unset; discovered {device.address}",
                required=False,
            )
        )
    elif device.address == preferred_host:
        checks.append(CheckResult("Preferred host", OK, preferred_host))
    else:
        checks.append(
            CheckResult(
                "Preferred host",
                OK,
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
            results.append(CheckResult(name, OK, detail, required=False))
        elif FeatureAvailability.UNAVAILABLE in states:
            results.append(CheckResult(name, OK, "currently unavailable", required=False))
        else:
            results.append(CheckResult(name, OK, "unsupported", required=False))
    return results


def _write_checks(stdout: TextIO, checks: list[CheckResult]) -> None:
    for check in checks:
        stdout.write(check.line() + "\n")
