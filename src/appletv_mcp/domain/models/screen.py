"""Captured Apple TV screen image."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CapturedScreen(BaseModel):
    """One PNG frame captured from the configured Apple TV.

    The producing infrastructure adapter validates the PNG signature and size
    before constructing this model, so consumers may trust `data` as-is.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    data: bytes = Field(min_length=1, description="PNG-encoded image bytes.")
    mime_type: Literal["image/png"] = "image/png"
