"""CLI configure/doctor/serve wiring tests without hardware."""

import io
from collections.abc import Sequence
from pathlib import Path

import pytest

from agenai_appletv_mcp.application.ports.apple_tv import DiscoveredDevice
from agenai_appletv_mcp.application.services.apple_tv_controller import AppleTVController
from agenai_appletv_mcp.infrastructure.config.repository import FileSettingsRepository
from agenai_appletv_mcp.interfaces.cli.commands.configure import run_configure
from agenai_appletv_mcp.interfaces.cli.commands.doctor import run_doctor
from agenai_appletv_mcp.interfaces.cli.main import main
from tests.helpers.fakes import FakeGateway, discovered


async def test_configure_saves_selected_device(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = FileSettingsRepository(tmp_path / "config.json")
    stdout = io.StringIO()
    stdin = io.StringIO("1\n")
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
        "agenai_appletv_mcp.interfaces.cli.commands.configure.PyAtvScanner.scan",
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
        "agenai_appletv_mcp.interfaces.cli.commands.configure.PyAtvStorageAdapter",
        fake_storage,
    )

    gateway = FakeGateway()
    controller = AppleTVController(gateway)

    class DummyRuntime:
        def __init__(self) -> None:
            self.controller = controller

        async def aclose(self) -> None:
            return None

    async def fake_create_runtime(**_kwargs: object) -> DummyRuntime:
        return DummyRuntime()

    monkeypatch.setattr(
        "agenai_appletv_mcp.interfaces.cli.commands.configure.create_runtime",
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


async def test_doctor_fails_without_config(tmp_path: Path) -> None:
    stdout = io.StringIO()
    code = await run_doctor(
        stdout=stdout,
        settings_repository=FileSettingsRepository(tmp_path / "missing.json"),
    )
    assert code == 1
    assert "FAIL Configuration" in stdout.getvalue()


def test_cli_help_and_unknown() -> None:
    try:
        main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
    try:
        main(["nope"])
    except SystemExit as exc:
        assert exc.code == 2
