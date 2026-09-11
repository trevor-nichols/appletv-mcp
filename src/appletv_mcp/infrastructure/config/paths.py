"""Filesystem locations for application configuration."""

import os
from pathlib import Path

from platformdirs import user_config_dir

APP_NAME = "appletv-mcp"
APP_AUTHOR = "appletv-mcp"
CONFIG_FILENAME = "config.json"
CONFIG_DIR_ENV = "APPLETV_MCP_CONFIG_DIR"


def config_dir() -> Path:
    override = os.environ.get(CONFIG_DIR_ENV)
    if override:
        return Path(override).expanduser()
    return Path(user_config_dir(APP_NAME, APP_AUTHOR))


def config_path(directory: Path | None = None) -> Path:
    return (directory or config_dir()) / CONFIG_FILENAME
