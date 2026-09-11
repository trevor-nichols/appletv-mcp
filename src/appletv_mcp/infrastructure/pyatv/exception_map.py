"""Map pyatv exceptions to domain errors without leaking credentials."""

from pyatv import exceptions as pyatv_exceptions

from appletv_mcp.domain.errors import (
    CommandFailedError,
    CommandTimeoutError,
    DeviceConnectionError,
    DeviceUnreachableError,
    FeatureUnavailableError,
    FeatureUnsupportedError,
    PairingRequiredError,
)

_PAIRING = (
    pyatv_exceptions.NoCredentialsError,
    pyatv_exceptions.InvalidCredentialsError,
    pyatv_exceptions.AuthenticationError,
    pyatv_exceptions.PairingError,
)

_UNSUPPORTED = (pyatv_exceptions.NotSupportedError,)
_UNAVAILABLE = (pyatv_exceptions.InvalidStateError,)
_UNREACHABLE = (
    pyatv_exceptions.ConnectionFailedError,
    pyatv_exceptions.NoServiceError,
    pyatv_exceptions.DeviceIdMissingError,
)
_DISCONNECTED = (
    pyatv_exceptions.ConnectionLostError,
    pyatv_exceptions.BlockedStateError,
)
_TIMEOUT = (pyatv_exceptions.OperationTimeoutError,)

# Property/call failures that mean "this optional field is not available"
# rather than "the connection or command transport failed".
_OPTIONAL_ABSENCE = (
    pyatv_exceptions.NotSupportedError,
    pyatv_exceptions.InvalidStateError,
)


def is_optional_absence(exc: BaseException) -> bool:
    """Return True when `exc` means an optional device field is unavailable."""

    return isinstance(exc, _OPTIONAL_ABSENCE)


def translate_exception(
    exc: Exception,
    *,
    operation: str,
    may_have_been_delivered: bool,
) -> Exception:
    """Return a domain error equivalent to `exc`, or `exc` if unexpected."""

    if isinstance(exc, TimeoutError):
        return CommandTimeoutError(
            f"The {operation} command timed out.",
            may_have_been_delivered=may_have_been_delivered,
        )
    if isinstance(exc, _TIMEOUT):
        return CommandTimeoutError(
            f"The {operation} command timed out.",
            may_have_been_delivered=may_have_been_delivered,
        )
    if isinstance(exc, _PAIRING):
        return PairingRequiredError(
            "Apple TV pairing credentials are missing or invalid. "
            "Run `atvremote wizard`, then `appletv-mcp configure`."
        )
    if isinstance(exc, _UNSUPPORTED):
        return FeatureUnsupportedError(f"{operation} is not supported by this device.")
    if isinstance(exc, _UNAVAILABLE):
        return FeatureUnavailableError(f"{operation} is unavailable in the current device state.")
    if isinstance(exc, _UNREACHABLE):
        return DeviceUnreachableError(
            f"Apple TV could not be reached while performing {operation}.",
            may_have_been_delivered=False,
        )
    if isinstance(exc, _DISCONNECTED):
        return DeviceConnectionError(
            f"The Apple TV connection failed while performing {operation}.",
            may_have_been_delivered=may_have_been_delivered,
        )
    if isinstance(exc, pyatv_exceptions.CommandError):
        return CommandFailedError(f"The Apple TV rejected the {operation} command.")
    if isinstance(exc, pyatv_exceptions.ProtocolError):
        return CommandFailedError(f"A protocol error occurred during {operation}.")
    return exc
