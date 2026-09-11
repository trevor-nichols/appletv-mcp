"""Connection manager identity, cache, concurrency, and shutdown tests."""

import asyncio
from collections.abc import Sequence

import pytest

from agenai_appletv_mcp.application.ports.apple_tv import DiscoveredDevice
from agenai_appletv_mcp.domain.errors import DeviceNotFoundError
from agenai_appletv_mcp.infrastructure.pyatv.connection_manager import ConnectionManager
from tests.helpers.factories import make_settings
from tests.helpers.fakes import FakeAppleTV, FakeScanner, MemorySettingsRepository, discovered


def _manager(
    scanner: FakeScanner,
    repo: MemorySettingsRepository | None = None,
    connected: list[FakeAppleTV] | None = None,
) -> ConnectionManager:
    created = connected if connected is not None else []

    async def connect(_config: object) -> FakeAppleTV:
        atv = FakeAppleTV()
        created.append(atv)
        return atv

    settings = repo or MemorySettingsRepository(make_settings())
    return ConnectionManager(
        settings_repository=settings,
        storage=None,
        scan=scanner.scan,
        connect=connect,
    )


async def test_cached_connection_is_reused() -> None:
    scanner = FakeScanner([discovered()])
    created: list[FakeAppleTV] = []
    manager = _manager(scanner, connected=created)
    first = await manager.get()
    second = await manager.get()
    assert first is second
    assert len(created) == 1
    assert len(scanner.calls) == 1
    await manager.close()


async def test_preferred_host_success_uses_unicast() -> None:
    scanner = FakeScanner([discovered()])
    manager = _manager(scanner)
    await manager.get()
    assert scanner.calls[0]["hosts"] == ["192.168.1.50"]
    await manager.close()


async def test_preferred_host_wrong_device_falls_back() -> None:
    wrong = discovered(identifier="11:22:33:44:55:66", address="192.168.1.50")
    correct = discovered(address="10.0.0.8")
    scanner = FakeScanner([wrong, correct])
    repo = MemorySettingsRepository(make_settings())
    manager = _manager(scanner, repo)
    await manager.get()
    assert repo.load().preferred_host == "10.0.0.8"
    await manager.close()


async def test_preferred_host_failure_then_identifier_scan() -> None:
    device = discovered(address="10.0.0.4")

    class HostThenIdentifier(FakeScanner):
        async def scan(
            self,
            *,
            timeout: float,
            identifier: str | None = None,
            hosts: Sequence[str] | None = None,
        ) -> list[DiscoveredDevice]:
            self.calls.append(
                {"timeout": timeout, "identifier": identifier, "hosts": list(hosts or [])}
            )
            if hosts:
                raise RuntimeError("unicast failed")
            return [device]

    scanner = HostThenIdentifier()
    repo = MemorySettingsRepository(make_settings(preferred_host="192.168.1.50"))
    manager = _manager(scanner, repo)
    await manager.get()
    assert repo.load().preferred_host == "10.0.0.4"
    await manager.close()


async def test_configured_identifier_absent() -> None:
    scanner = FakeScanner([])
    manager = _manager(scanner)
    with pytest.raises(DeviceNotFoundError):
        await manager.get()
    await manager.close()


async def test_concurrent_get_collapses_to_one_connect() -> None:
    scanner = FakeScanner([discovered()])
    scanner.delay = 0.05
    created: list[FakeAppleTV] = []
    manager = _manager(scanner, connected=created)
    first, second, third = await asyncio.gather(manager.get(), manager.get(), manager.get())
    assert first is second is third
    assert len(created) == 1
    await manager.close()


async def test_invalidate_and_reconnect() -> None:
    scanner = FakeScanner([discovered()])
    created: list[FakeAppleTV] = []
    manager = _manager(scanner, connected=created)
    first = await manager.get()
    manager.invalidate()
    second = await manager.reconnect()
    assert first is not second
    assert len(created) == 2
    await manager.close()


async def test_close_is_idempotent() -> None:
    scanner = FakeScanner([discovered()])
    created: list[FakeAppleTV] = []
    manager = _manager(scanner, connected=created)
    await manager.get()
    await manager.close()
    await manager.close()
    assert created[0].close_calls == 1


async def test_listener_invalidates_on_loss() -> None:
    scanner = FakeScanner([discovered()])
    created: list[FakeAppleTV] = []
    manager = _manager(scanner, connected=created)
    atv = await manager.get()
    assert atv.listener is manager
    manager.connection_lost(RuntimeError("dropped"))
    assert manager.cached is False
    await manager.close()
