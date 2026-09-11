"""Filesystem locations for application configuration."""

import os
from pathlib import Path

from platformdirs import user_config_dir

APP_NAME = "agenai-appletv"
APP_AUTHOR = "agenai"
CONFIG_FILENAME = "config.json"
CONFIG_DIR_ENV = "AGENAI_APPLETV_CONFIG_DIR"


def config_dir() -> Path:
    override = os.environ.get(CONFIG_DIR_ENV)
    if override:
        return Path(override).expanduser()
    return Path(user_config_dir(APP_NAME, APP_AUTHOR))


def config_path(directory: Path | None = None) -> Path:
    return (directory or config_dir()) / CONFIG_FILENAME
