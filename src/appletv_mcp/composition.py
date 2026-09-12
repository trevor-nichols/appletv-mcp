"""Constructor-injected process runtime. No service locator."""

from dataclasses import dataclass

from appletv_mcp.application.services.apple_tv_controller import AppleTVController
from appletv_mcp.application.services.screen_capture import ScreenCaptureService
from appletv_mcp.domain.models.settings import ScreenCaptureSettings
from appletv_mcp.infrastructure.config.repository import FileSettingsRepository
from appletv_mcp.infrastructure.pyatv.connection_manager import ConnectionManager
from appletv_mcp.infrastructure.pyatv.discovery import PyAtvScanner
from appletv_mcp.infrastructure.pyatv.gateway import PyAtvGateway
from appletv_mcp.infrastructure.pyatv.storage import PyAtvStorageAdapter
from appletv_mcp.infrastructure.screen_capture import ExternalScreenCaptureBackend


@dataclass
class Runtime:
    settings_repository: FileSettingsRepository
    storage: PyAtvStorageAdapter
    connection_manager: ConnectionManager
    controller: AppleTVController
    screen_capture: ScreenCaptureService

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
    screen_settings = ScreenCaptureSettings()
    if repository.exists():
        settings = repository.load()
        timeout = settings.command_timeout_seconds
        screen_settings = settings.screen_capture
    gateway = PyAtvGateway(connections, repository, timeout)
    controller = AppleTVController(gateway)
    screen_capture = ScreenCaptureService(ExternalScreenCaptureBackend(screen_settings))
    return Runtime(
        settings_repository=repository,
        storage=storage_adapter,
        connection_manager=connections,
        controller=controller,
        screen_capture=screen_capture,
    )
