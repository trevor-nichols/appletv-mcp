"""Port for persisting the application device profile."""

from typing import Protocol

from agenai_appletv_mcp.domain.models.settings import Settings


class SettingsRepository(Protocol):
    def load(self) -> Settings:
        """Load the saved device profile."""
        ...

    def save(self, settings: Settings) -> None:
        """Atomically persist a validated device profile."""
        ...

    def exists(self) -> bool:
        """Return whether a configuration file is present."""
        ...

    def update_preferred_host(self, host: str) -> Settings:
        """Persist a rediscovered IPv4 address without changing identity."""
        ...
