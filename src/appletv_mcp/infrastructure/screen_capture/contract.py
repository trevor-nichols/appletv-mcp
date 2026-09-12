"""The executable contract shared with the `appletv-screenshot` helper.

Exit codes are the only machine-readable channel between the helper and this
package. The helper's own `exit_codes.py` must stay identical to
`HelperExitCode`; a test in this repository compares the two tables.
"""

from enum import IntEnum

from appletv_mcp.domain.errors import (
    ScreenCaptureError,
    ScreenCaptureFailedError,
    ScreenCapturePairingRequiredError,
    ScreenCaptureTimeoutError,
)

HELPER_CONTRACT_VERSION = 1
HELPER_CAPTURE_SUBCOMMAND = "capture"
HELPER_OUTPUT_FLAG = "--output"


class HelperExitCode(IntEnum):
    SUCCESS = 0
    USAGE = 2
    DEVICE_NOT_FOUND = 10
    AMBIGUOUS_DEVICE = 11
    PAIRING_REQUIRED = 12
    TUNNEL_UNAVAILABLE = 13
    CAPTURE_FAILED = 14
    OUTPUT_WRITE_FAILED = 15
    CAPTURE_TIMEOUT = 16


HELPER_MISSING_MESSAGE = (
    "Screen capture is unavailable because the configured screenshot helper could not be "
    "found. Run `appletv-mcp doctor` and configure the external screen-capture sidecar."
)
PAIRING_REQUIRED_MESSAGE = (
    "Screen capture requires developer/RemoteXPC pairing for the configured Apple TV. "
    "Re-run the screen-capture pairing flow outside MCP."
)
TIMEOUT_MESSAGE = "Apple TV screen capture timed out before a screenshot was returned."
INVALID_IMAGE_MESSAGE = "The screen-capture helper completed but did not return a valid PNG image."

_EXIT_ERRORS: dict[HelperExitCode, tuple[type[ScreenCaptureError], str]] = {
    HelperExitCode.USAGE: (
        ScreenCaptureFailedError,
        "The screen-capture helper rejected the capture request. The installed helper may "
        "not match this server's helper contract; reinstall matching versions.",
    ),
    HelperExitCode.DEVICE_NOT_FOUND: (
        ScreenCaptureFailedError,
        "The screen-capture helper could not find its configured Apple TV on the network. "
        "Check that the Apple TV is awake and that the helper targets the right device.",
    ),
    HelperExitCode.AMBIGUOUS_DEVICE: (
        ScreenCaptureFailedError,
        "The screen-capture helper found more than one Apple TV and refused to guess. "
        "Configure the helper with one device identifier.",
    ),
    HelperExitCode.PAIRING_REQUIRED: (ScreenCapturePairingRequiredError, PAIRING_REQUIRED_MESSAGE),
    HelperExitCode.TUNNEL_UNAVAILABLE: (
        ScreenCaptureFailedError,
        "The screen-capture helper could not open a RemoteXPC tunnel to the Apple TV. "
        "Check the helper's tunnel setup outside MCP.",
    ),
    HelperExitCode.CAPTURE_FAILED: (
        ScreenCaptureFailedError,
        "The screen-capture helper reached the Apple TV but the device did not return a "
        "screenshot.",
    ),
    HelperExitCode.OUTPUT_WRITE_FAILED: (
        ScreenCaptureFailedError,
        "The screen-capture helper captured a screenshot but could not write it to the "
        "private output file.",
    ),
    HelperExitCode.CAPTURE_TIMEOUT: (ScreenCaptureTimeoutError, TIMEOUT_MESSAGE),
}


def error_for_exit_status(returncode: int) -> ScreenCaptureError:
    """Translate a non-zero helper exit status into the matching domain error."""

    if returncode < 0:
        return ScreenCaptureFailedError(
            f"The screen-capture helper was terminated by signal {-returncode} before it "
            "returned a screenshot."
        )
    try:
        code = HelperExitCode(returncode)
    except ValueError:
        return ScreenCaptureFailedError(
            f"The screen-capture helper exited with status {returncode} without producing "
            "a screenshot."
        )
    if code is HelperExitCode.SUCCESS:
        raise ValueError("exit status 0 is not an error")
    error_type, message = _EXIT_ERRORS[code]
    return error_type(message)
