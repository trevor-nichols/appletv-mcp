"""Persisted application configuration. Credentials are never stored here."""

import math
from ipaddress import IPv4Address

from pydantic import BaseModel, ConfigDict, Field, field_validator

DEFAULT_SCREEN_CAPTURE_COMMAND = "appletv-screenshot"


class ScreenCaptureSettings(BaseModel):
    """How the optional external screen-capture helper is invoked.

    Only invocation parameters live here. RemoteXPC pairing material belongs to
    the helper's own storage and never enters this file.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    command: str = Field(
        default=DEFAULT_SCREEN_CAPTURE_COMMAND,
        min_length=1,
        description="Executable name on PATH or absolute path of the screenshot helper.",
    )
    timeout_seconds: float = Field(
        default=20.0,
        gt=0,
        le=60,
        description="Wall-clock budget for one capture, including helper startup.",
    )
    max_image_bytes: int = Field(
        default=33_554_432,
        gt=0,
        description="Largest PNG accepted from the helper, in bytes.",
    )

    @field_validator("command")
    @classmethod
    def command_must_not_be_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("screen_capture.command must not be empty")
        return value

    @field_validator("timeout_seconds")
    @classmethod
    def timeout_must_be_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("screen_capture.timeout_seconds must be finite")
        return value


class Settings(BaseModel):
    """Device profile used to find and reconnect to one Apple TV."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    device_identifier: str = Field(
        min_length=1,
        description="Stable pyatv identifier for the configured Apple TV.",
    )
    device_name: str | None = Field(
        default=None,
        description="Informational display name captured at configuration time.",
    )
    preferred_host: str | None = Field(
        default=None,
        description="Last-known IPv4 address used as a unicast discovery hint.",
    )
    scan_timeout_seconds: float = Field(
        default=5.0,
        gt=0,
        description="Discovery timeout in seconds.",
    )
    command_timeout_seconds: float = Field(
        default=10.0,
        gt=0,
        description="Per-command device timeout in seconds.",
    )
    screen_capture: ScreenCaptureSettings = Field(
        default_factory=ScreenCaptureSettings,
        description="Optional external screen-capture helper configuration.",
    )

    @field_validator("device_identifier")
    @classmethod
    def identifier_must_not_be_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("device_identifier must not be empty")
        return value

    @field_validator("device_name", "preferred_host")
    @classmethod
    def blank_optional_becomes_none(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        return value

    @field_validator("preferred_host")
    @classmethod
    def preferred_host_must_be_ipv4(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return str(IPv4Address(value))
        except ValueError as exc:
            raise ValueError("preferred_host must be an IPv4 address") from exc

    @field_validator("scan_timeout_seconds", "command_timeout_seconds")
    @classmethod
    def timeouts_must_be_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("timeouts must be finite and greater than zero")
        return value
