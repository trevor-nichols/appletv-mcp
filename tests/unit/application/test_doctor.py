"""`appletv-mcp doctor` screen-capture diagnostics without hardware."""

from collections.abc import Sequence
from io import StringIO
from pathlib import Path

import pytest

from appletv_mcp.application.ports.apple_tv import DiscoveredDevice
from appletv_mcp.application.ports.screen_capture import ScreenCaptureBackend
from appletv_mcp.application.services.apple_tv_controller import AppleTVController
from appletv_mcp.application.services.screen_capture import ScreenCaptureService
from appletv_mcp.composition import Runtime
from appletv_mcp.domain.errors import DeviceUnreachableError
from appletv_mcp.domain.models.settings import ScreenCaptureSettings
from appletv_mcp.infrastructure.config.repository import FileSettingsRepository
from appletv_mcp.infrastructure.pyatv.connection_manager import ConnectionManager
from appletv_mcp.infrastructure.pyatv.storage import PyAtvStorageAdapter
from appletv_mcp.infrastructure.screen_capture import ExternalScreenCaptureBackend, HelperExitCode
from appletv_mcp.interfaces.cli.commands.doctor import run_doctor
from appletv_mcp.interfaces.cli.rendering import CheckResult, CheckStatus, exit_code_for
from tests.helpers.factories import make_settings
from tests.helpers.fake_helper import install_fake_helper
from tests.helpers.fakes import FakeGateway, discovered
from tests.helpers.png import FAKE_SCREEN_PNG
from tests.helpers.screen_capture import FakeScreenCaptureBackend


class _OneDeviceScanner:
    def __init__(self, device: DiscoveredDevice) -> None:
        self._device = device

    async def scan(
        self,
        *,
        timeout: float,
        identifier: str | None = None,
        hosts: Sequence[str] | None = None,
    ) -> list[DiscoveredDevice]:
        return [self._device]


class _Harness:
    def __init__(
        self,
        tmp_path: Path,
        *,
        screen_capture: ScreenCaptureSettings | None = None,
        gateway: FakeGateway | None = None,
        backend: ScreenCaptureBackend | None = None,
    ) -> None:
        self.repo = FileSettingsRepository(tmp_path / "config.json")
        settings = make_settings()
        if screen_capture is not None:
            settings = settings.model_copy(update={"screen_capture": screen_capture})
        self.repo.save(settings)
        self.storage = PyAtvStorageAdapter(tmp_path / "pyatv.conf")
        self.gateway = gateway or FakeGateway()
        self.backend: ScreenCaptureBackend = backend or FakeScreenCaptureBackend()
        manager = ConnectionManager(
            settings_repository=self.repo,
            storage=None,
            scan=_OneDeviceScanner(discovered()).scan,
        )
        self.runtime = Runtime(
            settings_repository=self.repo,
            storage=self.storage,
            connection_manager=manager,
            controller=AppleTVController(self.gateway),
            screen_capture=ScreenCaptureService(self.backend),
        )

    async def run(self) -> tuple[int, str]:
        stdout = StringIO()

        async def factory() -> Runtime:
            return self.runtime

        code = await run_doctor(
            stdout=stdout,
            settings_repository=self.repo,
            storage=self.storage,
            runtime_factory=factory,
        )
        return code, stdout.getvalue()


async def test_doctor_skips_screen_capture_when_helper_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    backend = FakeScreenCaptureBackend()
    harness = _Harness(tmp_path, backend=backend)
    code, output = await harness.run()
    assert code == 0
    assert "OK Connection: connected" in output
    assert (
        "SKIP Screen capture helper: optional backend not available (appletv-screenshot not found)"
    ) in output
    assert "Screen capture:" not in output
    assert backend.calls == 0


async def test_doctor_captures_through_real_helper_when_present(tmp_path: Path) -> None:
    helper = install_fake_helper(tmp_path, "success")
    settings = ScreenCaptureSettings(command=str(helper.executable))
    harness = _Harness(
        tmp_path,
        screen_capture=settings,
        backend=ExternalScreenCaptureBackend(settings, temp_root=tmp_path),
    )
    code, output = await harness.run()
    assert code == 0
    assert f"OK Screen capture helper: {helper.executable}" in output
    assert "OK Screen capture helper contract: contract=1" in output
    assert "OK Screen capture target: udid=00008110-AAAA transport=auto" in output
    assert f"OK Screen capture: 2x2 PNG, {len(FAKE_SCREEN_PNG)} bytes" in output


async def test_doctor_fails_helper_contract_mismatch_without_capturing(tmp_path: Path) -> None:
    helper = install_fake_helper(tmp_path, "contract-mismatch")
    settings = ScreenCaptureSettings(command=str(helper.executable))
    backend = FakeScreenCaptureBackend()
    harness = _Harness(tmp_path, screen_capture=settings, backend=backend)
    code, output = await harness.run()
    assert code == 0
    assert "FAIL Screen capture helper contract:" in output
    assert "contract=2" in output
    assert "server expects 1" in output
    assert "Screen capture target:" not in output
    assert "Screen capture:" not in output
    assert backend.calls == 0


async def test_doctor_fails_missing_helper_udid_without_capturing(tmp_path: Path) -> None:
    helper = install_fake_helper(tmp_path, "no-udid")
    settings = ScreenCaptureSettings(command=str(helper.executable))
    backend = FakeScreenCaptureBackend()
    harness = _Harness(tmp_path, screen_capture=settings, backend=backend)
    code, output = await harness.run()
    assert code == 0
    assert "OK Screen capture helper contract: contract=1" in output
    assert "FAIL Screen capture target: no UDID configured" in output
    assert "appletv-screenshot configure --udid" in output
    assert "Screen capture:" not in output
    assert backend.calls == 0


async def test_doctor_reports_broken_helper_without_failing_control(tmp_path: Path) -> None:
    helper = install_fake_helper(tmp_path, f"exit:{int(HelperExitCode.PAIRING_REQUIRED)}")
    settings = ScreenCaptureSettings(command=str(helper.executable))
    harness = _Harness(
        tmp_path,
        screen_capture=settings,
        backend=ExternalScreenCaptureBackend(settings, temp_root=tmp_path),
    )
    code, output = await harness.run()
    assert code == 0
    assert "OK Screen capture helper:" in output
    assert "FAIL Screen capture: Screen capture requires developer/RemoteXPC pairing" in output


async def test_doctor_runs_screen_checks_even_when_control_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    gateway = FakeGateway()
    gateway.fail_with = DeviceUnreachableError("Apple TV is asleep")
    gateway.fail_on = {"status"}
    harness = _Harness(tmp_path, gateway=gateway)
    code, output = await harness.run()
    assert code == 1
    assert "FAIL Connection: unreachable" in output
    assert "SKIP Screen capture helper" in output


def test_exit_code_ignores_optional_failures_and_skips() -> None:
    checks = [
        CheckResult("Configuration", CheckStatus.OK, "loaded"),
        CheckResult("Screen capture helper", CheckStatus.SKIP, "absent", required=False),
        CheckResult("Screen capture", CheckStatus.FAIL, "broken", required=False),
    ]
    assert exit_code_for(checks) == 0
    checks.append(CheckResult("Connection", CheckStatus.FAIL, "asleep"))
    assert exit_code_for(checks) == 1
    assert checks[1].line() == "SKIP Screen capture helper: absent"
