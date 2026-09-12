"""Exit codes that form the machine-readable contract with Apple TV MCP.

Keep this module free of third-party imports. The MCP repository loads it by
path in a test and compares it with `HelperExitCode`; both tables must match.
"""

from enum import IntEnum

CONTRACT_VERSION = 1


class ExitCode(IntEnum):
    SUCCESS = 0
    USAGE = 2
    DEVICE_NOT_FOUND = 10
    AMBIGUOUS_DEVICE = 11
    PAIRING_REQUIRED = 12
    TUNNEL_UNAVAILABLE = 13
    CAPTURE_FAILED = 14
    OUTPUT_WRITE_FAILED = 15
    CAPTURE_TIMEOUT = 16
    CONFIG_INVALID = 17
