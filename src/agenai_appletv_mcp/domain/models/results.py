"""Structured results returned by semantic Apple TV operations."""

from pydantic import BaseModel, ConfigDict, Field

from agenai_appletv_mcp.domain.enums import (
    PlaybackAction,
    PowerState,
    PowerTarget,
    PressAction,
    RemoteButton,
    SkipDirection,
    VolumeDirection,
)


class PowerResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_state: PowerTarget
    power_state: PowerState


class OpenAppResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    bundle_id: str
    launched: bool


class OpenUrlResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    accepted: bool


class PressResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    button: RemoteButton
    action: PressAction
    count: int = Field(ge=1, le=10)
    completed: int = Field(ge=0, le=10)


class PlaybackResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: PlaybackAction
    accepted: bool


class SeekResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_position_seconds: int = Field(ge=0)
    accepted: bool


class SkipResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    direction: SkipDirection
    requested_seconds: float = Field(ge=0)
    accepted: bool


class TextResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    characters: int = Field(ge=0)
    accepted: bool


class VolumeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_percent: float = Field(ge=0, le=100)
    volume_percent: float | None = Field(default=None, ge=0, le=100)


class VolumeAdjustResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    direction: VolumeDirection
    requested_steps: int = Field(ge=1, le=10)
    completed_steps: int = Field(ge=0, le=10)
    volume_percent: float | None = Field(default=None, ge=0, le=100)
