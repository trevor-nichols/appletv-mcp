"""Device and application identity models."""

from pydantic import BaseModel, ConfigDict, Field


class DeviceInfo(BaseModel):
    """Stable identity and hardware metadata for the configured Apple TV."""

    model_config = ConfigDict(extra="forbid")

    identifier: str
    name: str | None = None
    address: str | None = None
    model: str | None = None
    operating_system: str | None = None
    version: str | None = None
    mac: str | None = None


class AppInfo(BaseModel):
    """A launchable application installed on the Apple TV."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    bundle_id: str = Field(min_length=1)
