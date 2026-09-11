"""Atomic JSON persistence for the application device profile."""

import json
import logging
import os
import tempfile
from pathlib import Path

from pydantic import ValidationError

from agenai_appletv_mcp.domain.errors import ConfigurationError, DeviceNotConfiguredError
from agenai_appletv_mcp.domain.models.settings import Settings
from agenai_appletv_mcp.infrastructure.config.paths import config_dir, config_path

logger = logging.getLogger(__name__)


class FileSettingsRepository:
    """Load and save `Settings` without touching pyatv credentials."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or config_path()

    @property
    def path(self) -> Path:
        return self._path

    def exists(self) -> bool:
        return self._path.is_file()

    def load(self) -> Settings:
        if not self.exists():
            raise DeviceNotConfiguredError(
                "No Apple TV is configured. Run `agenai-appletv configure` after pairing "
                "with `atvremote wizard`."
            )
        try:
            raw = self._path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigurationError(
                f"Unable to read configuration at {self._path}: {exc}"
            ) from exc
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ConfigurationError(
                f"Configuration at {self._path} is not valid JSON: {exc.msg}."
            ) from exc
        if not isinstance(payload, dict):
            raise ConfigurationError(f"Configuration at {self._path} must be a JSON object.")
        try:
            return Settings.model_validate(payload)
        except ValidationError as exc:
            raise ConfigurationError(_validation_message(exc, self._path)) from exc

    def save(self, settings: Settings) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = settings.model_dump(mode="json")
        serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        _atomic_write(self._path, serialized)
        logger.info(
            "Saved Apple TV profile identifier=%s host=%s",
            settings.device_identifier,
            settings.preferred_host,
        )

    def update_preferred_host(self, host: str) -> Settings:
        settings = self.load()
        updated = settings.model_copy(update={"preferred_host": host})
        self.save(updated)
        return updated


def default_repository() -> FileSettingsRepository:
    config_dir().mkdir(parents=True, exist_ok=True)
    return FileSettingsRepository()


def _atomic_write(destination: Path, contents: str) -> None:
    directory = destination.parent
    fd, temp_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=directory)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(destination)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def _validation_message(exc: ValidationError, path: Path) -> str:
    details = "; ".join(error["msg"] for error in exc.errors())
    return f"Configuration at {path} is invalid: {details}."
