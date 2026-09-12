"""Non-destructive setup diagnostics."""

import json
from collections.abc import Awaitable, Callable
from pathlib import Path
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
    HELPER_CONTRACT_VERSION,
    inspect_png,
    parse_helper_contract_version,
    resolve_screen_capture_executable,
    run_helper_command,
)
from appletv_mcp.infrastructure.screen_capture.contract import (
    HELPER_IDENTIFY_SUBCOMMAND,
    HELPER_VERSION_FLAG,
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
    contract_ok, contract_checks = await _helper_contract_checks(executable)
    checks.extend(contract_checks)
    if not contract_ok:
        return checks
    target_checks = await _helper_target_checks(executable)
    checks.extend(target_checks)
    if any(check.status is FAIL for check in target_checks):
        return checks
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


async def _helper_contract_checks(executable: Path) -> tuple[bool, list[CheckResult]]:
    try:
        status, output = await run_helper_command(executable, [HELPER_VERSION_FLAG])
    except TimeoutError:
        return False, [
            CheckResult(
                "Screen capture helper contract",
                SKIP,
                "helper --version timed out",
                required=False,
            )
        ]
    except OSError as exc:
        return False, [
            CheckResult(
                "Screen capture helper contract",
                SKIP,
                f"helper --version could not run ({exc.strerror or 'unknown error'})",
                required=False,
            )
        ]
    if status != 0:
        return False, [
            CheckResult(
                "Screen capture helper contract",
                SKIP,
                f"helper --version exited {status}",
                required=False,
            )
        ]
    reported = parse_helper_contract_version(output)
    if reported is None:
        return False, [
            CheckResult(
                "Screen capture helper contract",
                SKIP,
                f"helper --version did not report contract=N ({output or 'empty'})",
                required=False,
            )
        ]
    if reported != HELPER_CONTRACT_VERSION:
        return False, [
            CheckResult(
                "Screen capture helper contract",
                FAIL,
                f"helper reports contract={reported}, server expects {HELPER_CONTRACT_VERSION}",
                required=False,
            )
        ]
    return True, [
        CheckResult(
            "Screen capture helper contract",
            OK,
            f"contract={reported}",
            required=False,
        )
    ]


async def _helper_target_checks(executable: Path) -> list[CheckResult]:
    try:
        status, output = await run_helper_command(executable, [HELPER_IDENTIFY_SUBCOMMAND])
    except TimeoutError, OSError:
        return [
            CheckResult(
                "Screen capture target",
                SKIP,
                "helper identify did not run",
                required=False,
            )
        ]
    if status != 0:
        return [
            CheckResult(
                "Screen capture target",
                SKIP,
                "helper identify is unavailable",
                required=False,
            )
        ]
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return [
            CheckResult(
                "Screen capture target",
                SKIP,
                "helper identify did not return JSON",
                required=False,
            )
        ]
    if not isinstance(payload, dict):
        return [
            CheckResult(
                "Screen capture target",
                SKIP,
                "helper identify did not return a JSON object",
                required=False,
            )
        ]
    udid = payload.get("udid")
    transport = payload.get("transport", "auto")
    if not isinstance(udid, str) or not udid:
        return [
            CheckResult(
                "Screen capture target",
                FAIL,
                "no UDID configured; run `appletv-screenshot configure --udid <udid>`",
                required=False,
            )
        ]
    return [
        CheckResult(
            "Screen capture target",
            OK,
            f"udid={udid} transport={transport}",
            required=False,
        )
    ]


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
