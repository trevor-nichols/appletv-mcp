"""Helper configuration: which Apple TV to capture and how to reach it.

No pairing material lives here. RemotePairing records belong to pymobiledevice3
and Apple's `remotepairingd`; this file only names the device and transport.
"""

import json
import math
import os
import tempfile
from enum import StrEnum
from pathlib import Path

from platformdirs import user_config_dir
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from appletv_screenshot.errors import SidecarError
from appletv_screenshot.exit_codes import ExitCode

APP_NAME = "appletv-screenshot"
CONFIG_DIR_ENV = "APPLETV_SCREENSHOT_CONFIG_DIR"
CONFIG_FILENAME = "config.json"


class Transport(StrEnum):
    AUTO = "auto"
    NATIVE = "native"
    USERSPACE = "userspace"
    TUNNELD = "tunneld"


class SidecarConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    udid: str | None = Field(
        default=None,
        description="UDID of the Apple TV to capture. Required for capture.",
    )
    transport: Transport = Field(
        default=Transport.AUTO,
        description="auto tries native on macOS, then userspace, then tunneld.",
    )
    tunneld_host: str = Field(default="127.0.0.1", min_length=1)
    tunneld_port: int = Field(default=49151, ge=1, le=65535)
    discovery_timeout_seconds: float = Field(default=3.0, gt=0, le=30)
    timeout_seconds: float = Field(
        default=15.0,
        gt=0,
        le=55,
        description="Budget for tunnel, DVT session, and screenshot together.",
    )

    @field_validator("udid")
    @classmethod
    def blank_udid_becomes_none(cls, value: str | None) -> str | None:
        return value or None

    @field_validator("discovery_timeout_seconds", "timeout_seconds")
    @classmethod
    def timeouts_must_be_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("timeouts must be finite")
        return value

    @property
    def tunneld_address(self) -> tuple[str, int]:
        return (self.tunneld_host, self.tunneld_port)


def config_dir() -> Path:
    override = os.environ.get(CONFIG_DIR_ENV)
    if override:
        return Path(override).expanduser()
    return Path(user_config_dir(APP_NAME))


def config_path() -> Path:
    return config_dir() / CONFIG_FILENAME


def load_config(path: Path | None = None) -> SidecarConfig:
    target = path or config_path()
    if not target.is_file():
        return SidecarConfig()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SidecarError(ExitCode.CONFIG_INVALID, f"cannot read {target}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SidecarError(ExitCode.CONFIG_INVALID, f"{target} must contain a JSON object")
    try:
        return SidecarConfig.model_validate(payload)
    except ValidationError as exc:
        details = "; ".join(str(error["msg"]) for error in exc.errors())
        raise SidecarError(ExitCode.CONFIG_INVALID, f"{target} is invalid: {details}") from exc


def save_config(config: SidecarConfig, path: Path | None = None) -> Path:
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(config.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(target)
    except OSError:
        temp_path.unlink(missing_ok=True)
        raise
    return target
