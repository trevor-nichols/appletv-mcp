"""Screen observation through an external helper process.

Nothing in this package imports pymobiledevice3. The helper owns RemoteXPC,
pairing records, and DVT; this package owns process execution and validation.
"""

from appletv_mcp.infrastructure.screen_capture.contract import (
    HELPER_CONTRACT_VERSION,
    HelperExitCode,
    error_for_exit_status,
)
from appletv_mcp.infrastructure.screen_capture.external import (
    ExternalScreenCaptureBackend,
    resolve_screen_capture_executable,
)
from appletv_mcp.infrastructure.screen_capture.png import PngInfo, inspect_png

__all__ = [
    "HELPER_CONTRACT_VERSION",
    "ExternalScreenCaptureBackend",
    "HelperExitCode",
    "PngInfo",
    "error_for_exit_status",
    "inspect_png",
    "resolve_screen_capture_executable",
]
