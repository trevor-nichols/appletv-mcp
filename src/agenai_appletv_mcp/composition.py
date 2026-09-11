"""Constructor-injected process runtime. No service locator."""

from dataclasses import dataclass

from agenai_appletv_mcp.application.services.apple_tv_controller import AppleTVController
from agenai_appletv_mcp.infrastructure.config.repository import FileSettingsRepository
from agenai_appletv_mcp.infrastructure.pyatv.connection_manager import ConnectionManager
from agenai_appletv_mcp.infrastructure.pyatv.discovery import PyAtvScanner
from agenai_appletv_mcp.infrastructure.pyatv.gateway import PyAtvGateway
from agenai_appletv_mcp.infrastructure.pyatv.storage import PyAtvStorageAdapter


@dataclass
class Runtime:
    settings_repository: FileSettingsRepository
    storage: PyAtvStorageAdapter
    connection_manager: ConnectionManager
    controller: AppleTVController

    async def aclose(self) -> None:
        await self.controller.close()
        await self.connection_manager.close()
        await self.storage.close()


async def create_runtime(
    *,
    settings_repository: FileSettingsRepository | None = None,
    storage: PyAtvStorageAdapter | None = None,
) -> Runtime:
    repository = settings_repository or FileSettingsRepository()
    storage_adapter = storage or PyAtvStorageAdapter()
    pyatv_storage = await storage_adapter.load()
    scanner = PyAtvScanner(pyatv_storage)
    connections = ConnectionManager(
        settings_repository=repository,
        storage=pyatv_storage,
        scan=scanner.scan,
    )
    timeout = 10.0
    if repository.exists():
        timeout = repository.load().command_timeout_seconds
    gateway = PyAtvGateway(connections, repository, timeout)
    controller = AppleTVController(gateway)
    return Runtime(
        settings_repository=repository,
        storage=storage_adapter,
        connection_manager=connections,
        controller=controller,
    )
