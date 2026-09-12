from collections.abc import AsyncIterator

import pytest

from appletv_mcp.composition import Runtime, create_runtime
from appletv_mcp.domain.errors import DeviceNotConfiguredError
from appletv_mcp.infrastructure.config.repository import FileSettingsRepository


@pytest.fixture
async def runtime() -> AsyncIterator[Runtime]:
    try:
        FileSettingsRepository().load()
    except DeviceNotConfiguredError as exc:
        pytest.skip(str(exc))
    created = await create_runtime()
    try:
        yield created
    finally:
        await created.aclose()
