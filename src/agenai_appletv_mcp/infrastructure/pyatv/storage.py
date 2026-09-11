"""Load pyatv file storage compatible with `atvremote` pairing."""

import asyncio
import logging
from pathlib import Path

from pyatv.interface import Storage
from pyatv.storage.file_storage import FileStorage

from agenai_appletv_mcp.domain.errors import StorageError

logger = logging.getLogger(__name__)


class PyAtvStorageAdapter:
    """Owns the process-lifetime pyatv storage instance."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path
        self._storage: Storage | None = None

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def loaded(self) -> bool:
        return self._storage is not None

    def get(self) -> Storage:
        if self._storage is None:
            raise StorageError("pyatv storage has not been loaded.")
        return self._storage

    async def load(self) -> Storage:
        if self._storage is not None:
            return self._storage
        loop = asyncio.get_running_loop()
        try:
            storage = (
                FileStorage(str(self._path), loop)
                if self._path is not None
                else FileStorage.default_storage(loop)
            )
            await storage.load()
        except Exception as exc:
            raise StorageError("Unable to load pyatv pairing storage.") from exc
        self._storage = storage
        logger.info("Loaded pyatv pairing storage")
        return storage

    async def close(self) -> None:
        storage = self._storage
        self._storage = None
        if storage is None:
            return
        try:
            await storage.save()
        except Exception:
            logger.exception("Failed to save pyatv storage during shutdown")
