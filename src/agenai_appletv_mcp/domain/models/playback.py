"""Playback metadata associated with currently playing media."""

from pydantic import BaseModel, ConfigDict, Field

from agenai_appletv_mcp.domain.enums import (
    MediaType,
    PlaybackState,
    RepeatMode,
    ShuffleMode,
)


class PlaybackInfo(BaseModel):
    """Observable playback and media metadata.

    Missing upstream values are `None`. This object does not describe the
    currently highlighted UI control or a guaranteed foreground application.
    """

    model_config = ConfigDict(extra="forbid")

    state: PlaybackState
    media_type: MediaType | None = None
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    genre: str | None = None
    series_name: str | None = None
    season_number: int | None = None
    episode_number: int | None = None
    position_seconds: int | None = Field(default=None, ge=0)
    duration_seconds: int | None = Field(default=None, ge=0)
    repeat: RepeatMode | None = None
    shuffle: ShuffleMode | None = None
    content_identifier: str | None = None
    itunes_store_identifier: int | None = None
