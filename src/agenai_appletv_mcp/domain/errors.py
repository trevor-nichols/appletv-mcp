"""Domain errors for Apple TV control.

These are the only operational failures the interface layers should need to
understand. Raw `pyatv` exceptions stay behind the infrastructure boundary.
"""


class AppleTVError(Exception):
    """Base class for expected Apple TV operational failures."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class DeviceNotConfiguredError(AppleTVError):
    """No device profile has been saved yet."""


class DeviceNotFoundError(AppleTVError):
    """The configured device was not discovered on the network."""


class DeviceUnreachableError(AppleTVError):
    """Discovery succeeded or was skipped, but a connection could not be made."""

    def __init__(self, message: str, *, may_have_been_delivered: bool = False) -> None:
        super().__init__(message)
        self.may_have_been_delivered = may_have_been_delivered


class DeviceConnectionError(AppleTVError):
    """An established connection failed or was closed unexpectedly."""

    def __init__(self, message: str, *, may_have_been_delivered: bool = True) -> None:
        super().__init__(message)
        self.may_have_been_delivered = may_have_been_delivered


class PairingRequiredError(AppleTVError):
    """Stored pairing credentials are missing or rejected."""


class FeatureUnavailableError(AppleTVError):
    """The feature is supported by the device but not available right now."""


class FeatureUnsupportedError(AppleTVError):
    """The device does not support the requested feature."""


class AppNotFoundError(AppleTVError):
    """No installed application matched the requested identifier or name."""


class AmbiguousAppError(AppleTVError):
    """More than one installed application matched the requested name."""


class InvalidUrlError(AppleTVError):
    """A deep-link URL failed syntactic validation."""


class InvalidInputError(AppleTVError):
    """A caller-supplied argument failed domain validation."""


class KeyboardNotFocusedError(AppleTVError):
    """Text input was requested while no virtual keyboard is focused."""


class CommandTimeoutError(AppleTVError):
    """A device or network operation exceeded its allotted time."""

    def __init__(self, message: str, *, may_have_been_delivered: bool = False) -> None:
        super().__init__(message)
        self.may_have_been_delivered = may_have_been_delivered


class CommandFailedError(AppleTVError):
    """The device rejected or failed a command for a non-connection reason."""


class UncertainExecutionError(AppleTVError):
    """A non-idempotent command may have been delivered before the connection failed."""


class ConfigurationError(AppleTVError):
    """Application configuration is missing or invalid."""


class StorageError(AppleTVError):
    """pyatv persistent storage could not be loaded."""
