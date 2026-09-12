"""CLI configure/doctor/serve wiring tests without hardware."""

from collections.abc import Sequence
from io import StringIO
from pathlib import Path

import pytest
from pyatv.interface import Storage

from appletv_mcp.application.ports.apple_tv import DiscoveredDevice
from appletv_mcp.application.services.apple_tv_controller import AppleTVController
from appletv_mcp.application.services.screen_capture import ScreenCaptureService
from appletv_mcp.composition import Runtime
from appletv_mcp.domain.errors import DeviceUnreachableError, StorageError
from appletv_mcp.domain.models.settings import ScreenCaptureSettings
from appletv_mcp.infrastructure.config.repository import FileSettingsRepository
from appletv_mcp.infrastructure.pyatv.connection_manager import ConnectionManager
from appletv_mcp.infrastructure.pyatv.storage import PyAtvStorageAdapter
from appletv_mcp.interfaces.cli.commands.configure import (
    ConfigureError,
    _apple_tv_candidates,
    run_configure,
)
from appletv_mcp.interfaces.cli.commands.doctor import run_doctor
from appletv_mcp.interfaces.cli.main import main
from tests.helpers.factories import make_settings
from tests.helpers.fakes import FakeGateway, discovered
from tests.helpers.screen_capture import FakeScreenCaptureBackend


async def test_configure_saves_selected_device(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = FileSettingsRepository(tmp_path / "config.json")
    stdout = StringIO()
    stdin = StringIO("1\n")
    device = discovered()

    async def fake_scan(
        self: object,
        *,
        timeout: float,
        identifier: str | None = None,
        hosts: Sequence[str] | None = None,
    ) -> list[DiscoveredDevice]:
        return [device]

    monkeypatch.setattr(
        "appletv_mcp.interfaces.cli.commands.configure.PyAtvScanner.scan",
        fake_scan,
    )

    class DummyStorage:
        async def load(self) -> object:
            return object()

        async def close(self) -> None:
            return None

    def fake_storage(path: Path | None = None) -> DummyStorage:
        return DummyStorage()

    monkeypatch.setattr(
        "appletv_mcp.interfaces.cli.commands.configure.PyAtvStorageAdapter",
        fake_storage,
    )

    controller = AppleTVController(FakeGateway())

    class DummyRuntime:
        def __init__(self) -> None:
            self.controller = controller

        async def aclose(self) -> None:
            return None

    async def fake_create_runtime(**_kwargs: object) -> DummyRuntime:
        return DummyRuntime()

    monkeypatch.setattr(
        "appletv_mcp.interfaces.cli.commands.configure.create_runtime",
        fake_create_runtime,
    )

    code = await run_configure(
        stdin=stdin,
        stdout=stdout,
        settings_repository=repo,
        selector=lambda devices: devices[0],
    )
    assert code == 0
    saved = repo.load()
    assert saved.device_identifier == device.identifier
    assert saved.preferred_host == device.address
    assert "Capability summary" in stdout.getvalue()


async def test_configure_preserves_screen_capture_and_command_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = FileSettingsRepository(tmp_path / "config.json")
    repo.save(
        make_settings(
            command_timeout_seconds=22.5,
            screen_capture=ScreenCaptureSettings(
                command="/opt/appletv-screenshot",
                timeout_seconds=41.0,
                max_image_bytes=1024,
            ),
        )
    )
    device = discovered(name="Bedroom", identifier="DE:AD:BE:EF:00:01", address="10.0.0.8")
    stdout = StringIO()

    async def fake_scan(
        self: object,
        *,
        timeout: float,
        identifier: str | None = None,
        hosts: Sequence[str] | None = None,
    ) -> list[DiscoveredDevice]:
        return [device]

    monkeypatch.setattr(
        "appletv_mcp.interfaces.cli.commands.configure.PyAtvScanner.scan",
        fake_scan,
    )

    class DummyStorage:
        async def load(self) -> object:
            return object()

        async def close(self) -> None:
            return None

    def fake_storage(path: Path | None = None) -> DummyStorage:
        return DummyStorage()

    monkeypatch.setattr(
        "appletv_mcp.interfaces.cli.commands.configure.PyAtvStorageAdapter",
        fake_storage,
    )

    class DummyRuntime:
        def __init__(self) -> None:
            self.controller = AppleTVController(FakeGateway())

        async def aclose(self) -> None:
            return None

    async def fake_create_runtime(**_kwargs: object) -> DummyRuntime:
        return DummyRuntime()

    monkeypatch.setattr(
        "appletv_mcp.interfaces.cli.commands.configure.create_runtime",
        fake_create_runtime,
    )

    code = await run_configure(
        stdin=StringIO(),
        stdout=stdout,
        settings_repository=repo,
        selector=lambda devices: devices[0],
    )
    assert code == 0
    saved = repo.load()
    assert saved.device_identifier == device.identifier
    assert saved.device_name == "Bedroom"
    assert saved.preferred_host == "10.0.0.8"
    assert saved.command_timeout_seconds == 22.5
    assert saved.screen_capture.command == "/opt/appletv-screenshot"
    assert saved.screen_capture.timeout_seconds == 41.0
    assert saved.screen_capture.max_image_bytes == 1024


def test_configure_candidates_ignore_known_non_tv_devices() -> None:
    stdout = StringIO()
    tv = discovered(name="Living Room", device_model="Gen4K")
    pod = discovered(name="Kitchen", identifier="11:22:33:44:55:66", device_model="HomePod")
    music = discovered(name="Mac", identifier="aa:bb:cc:dd:ee:01", device_model="Music")
    candidates = _apple_tv_candidates([pod, music, tv], stdout)
    assert [device.identifier for device in candidates] == [tv.identifier]
    output = stdout.getvalue()
    assert "Ignored non-Apple-TV device(s)" in output
    assert "Kitchen" in output
    assert "Mac" in output


def test_configure_candidates_allow_unknown_model_with_warning() -> None:
    stdout = StringIO()
    unknown = discovered(name="Mystery", device_model="Unknown")
    candidates = _apple_tv_candidates([unknown], stdout)
    assert candidates == [unknown]
    assert "unknown model" in stdout.getvalue()


def test_configure_candidates_reject_when_only_non_tv_devices() -> None:
    stdout = StringIO()
    pod = discovered(name="Kitchen", device_model="HomePod")
    with pytest.raises(ConfigureError, match="non-TV"):
        _apple_tv_candidates([pod], stdout)


async def test_configure_does_not_save_homepod(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = FileSettingsRepository(tmp_path / "config.json")
    stdout = StringIO()
    tv = discovered(name="Living Room", device_model="Gen4K")
    pod = discovered(name="Kitchen", identifier="11:22:33:44:55:66", device_model="HomePod")

    async def fake_scan(
        self: object,
        *,
        timeout: float,
        identifier: str | None = None,
        hosts: Sequence[str] | None = None,
    ) -> list[DiscoveredDevice]:
        return [pod, tv]

    monkeypatch.setattr(
        "appletv_mcp.interfaces.cli.commands.configure.PyAtvScanner.scan",
        fake_scan,
    )

    class DummyStorage:
        async def load(self) -> object:
            return object()

        async def close(self) -> None:
            return None

    def fake_storage(path: Path | None = None) -> DummyStorage:
        return DummyStorage()

    monkeypatch.setattr(
        "appletv_mcp.interfaces.cli.commands.configure.PyAtvStorageAdapter",
        fake_storage,
    )

    controller = AppleTVController(FakeGateway())

    class DummyRuntime:
        def __init__(self) -> None:
            self.controller = controller

        async def aclose(self) -> None:
            return None

    async def fake_create_runtime(**_kwargs: object) -> DummyRuntime:
        return DummyRuntime()

    monkeypatch.setattr(
        "appletv_mcp.interfaces.cli.commands.configure.create_runtime",
        fake_create_runtime,
    )

    code = await run_configure(
        stdin=StringIO(),
        stdout=stdout,
        settings_repository=repo,
        selector=lambda devices: devices[0],
    )
    assert code == 0
    saved = repo.load()
    assert saved.device_identifier == tv.identifier
    assert saved.device_identifier != pod.identifier
    assert "Kitchen" in stdout.getvalue()


async def test_run_configure_translates_storage_error_and_closes_adapter(
    tmp_path: Path,
) -> None:
    class FailingStorage(PyAtvStorageAdapter):
        def __init__(self) -> None:
            super().__init__(path=None)
            self.close_calls = 0

        async def load(self) -> Storage:
            raise StorageError("Unable to load pyatv pairing storage.")

        async def close(self) -> None:
            self.close_calls += 1
            await super().close()

    adapter = FailingStorage()
    with pytest.raises(ConfigureError, match="Unable to load pyatv pairing storage"):
        await run_configure(
            stdin=StringIO(),
            stdout=StringIO(),
            settings_repository=FileSettingsRepository(tmp_path / "config.json"),
            storage=adapter,
        )
    assert adapter.close_calls == 1


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf"])
def test_main_configure_rejects_invalid_scan_timeout(value: str) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["configure", "--scan-timeout", value])
    assert exc_info.value.code == 2


async def test_doctor_fails_without_config(tmp_path: Path) -> None:
    stdout = StringIO()
    code = await run_doctor(
        stdout=stdout,
        settings_repository=FileSettingsRepository(tmp_path / "missing.json"),
    )
    assert code == 1
    assert "FAIL Configuration" in stdout.getvalue()


async def test_run_doctor_uses_preferred_host_when_multicast_fails(tmp_path: Path) -> None:
    repo = FileSettingsRepository(tmp_path / "config.json")
    repo.save(make_settings())
    device = discovered()
    calls: list[dict[str, object]] = []

    class HostThenBrokenMulticast:
        async def scan(
            self,
            *,
            timeout: float,
            identifier: str | None = None,
            hosts: Sequence[str] | None = None,
        ) -> list[DiscoveredDevice]:
            calls.append({"identifier": identifier, "hosts": list(hosts or [])})
            if hosts is None:
                raise DeviceUnreachableError("multicast unavailable")
            return [device]

    scanner = HostThenBrokenMulticast()
    manager = ConnectionManager(
        settings_repository=repo,
        storage=None,
        scan=scanner.scan,
    )
    storage = PyAtvStorageAdapter(tmp_path / "pyatv.conf")
    runtime = Runtime(
        settings_repository=repo,
        storage=storage,
        connection_manager=manager,
        controller=AppleTVController(FakeGateway()),
        screen_capture=ScreenCaptureService(FakeScreenCaptureBackend()),
    )

    async def factory() -> Runtime:
        return runtime

    stdout = StringIO()
    code = await run_doctor(
        stdout=stdout,
        settings_repository=repo,
        storage=storage,
        runtime_factory=factory,
    )
    output = stdout.getvalue()
    assert code == 0
    assert "OK Device discovery" in output
    assert "OK Connection" in output
    assert {"identifier": None, "hosts": ["192.168.1.50"]} in calls
    assert all(call["hosts"] for call in calls)


def test_cli_help_and_unknown(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "appletv-mcp" in help_text
    assert "Apple TV MCP" in help_text
    assert "configure" in help_text
    assert "doctor" in help_text
    assert "serve" in help_text

    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
    assert capsys.readouterr().out.strip() == "appletv-mcp 0.2.0"

    with pytest.raises(SystemExit) as exc_info:
        main(["nope"])
    assert exc_info.value.code == 2


@pytest.mark.parametrize("command", ["configure", "doctor", "serve"])
def test_cli_subcommand_help(command: str, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main([command, "--help"])
    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert command in output
    assert "appletv-mcp" in output
