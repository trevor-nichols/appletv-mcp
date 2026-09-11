"""pyatv storage adapter tests using a temp file."""

from pathlib import Path

from agenai_appletv_mcp.infrastructure.pyatv.storage import PyAtvStorageAdapter


async def test_storage_load_and_close(tmp_path: Path) -> None:
    adapter = PyAtvStorageAdapter(tmp_path / "pyatv.conf")
    storage = await adapter.load()
    assert adapter.loaded is True
    assert adapter.get() is storage
    await adapter.close()
    assert adapter.loaded is False


async def test_storage_load_is_idempotent(tmp_path: Path) -> None:
    adapter = PyAtvStorageAdapter(tmp_path / "pyatv.conf")
    first = await adapter.load()
    second = await adapter.load()
    assert first is second
    await adapter.close()
