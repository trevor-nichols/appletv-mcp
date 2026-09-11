"""Persisted application configuration. Credentials are never stored here."""

import math
from ipaddress import IPv4Address

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
