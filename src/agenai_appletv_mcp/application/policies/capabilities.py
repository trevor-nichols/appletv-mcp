"""Central capability policy for normalized operations."""

from agenai_appletv_mcp.domain.enums import FeatureAvailability, NormalizedOperation
from agenai_appletv_mcp.domain.errors import FeatureUnavailableError, FeatureUnsupportedError

_UNAVAILABLE_MESSAGES: dict[NormalizedOperation, str] = {
    NormalizedOperation.PAUSE: "Pause is unavailable because nothing is currently playing.",
    NormalizedOperation.PLAY: "Play is unavailable in the current device state.",
    NormalizedOperation.TEXT_SET: ("Text input is unavailable because no text field is focused."),
    NormalizedOperation.SEEK: "Seek is unavailable because nothing is currently playing.",
    NormalizedOperation.SKIP_FORWARD: (
        "Skip forward is unavailable because nothing is currently playing."
    ),
    NormalizedOperation.SKIP_BACKWARD: (
        "Skip backward is unavailable because nothing is currently playing."
    ),
}


def ensure_executable(operation: NormalizedOperation, state: FeatureAvailability) -> None:
    """Apply the project capability rules.

    available  → execute
    unknown    → attempt execution
    unavailable → current-state failure
    unsupported → device-capability failure
    """

    if state is FeatureAvailability.AVAILABLE or state is FeatureAvailability.UNKNOWN:
        return
    if state is FeatureAvailability.UNAVAILABLE:
        raise FeatureUnavailableError(
            _UNAVAILABLE_MESSAGES.get(
                operation,
                f"{_display_name(operation)} is unavailable in the current device state.",
            )
        )
    if state is FeatureAvailability.UNSUPPORTED:
        raise FeatureUnsupportedError(
            f"{_display_name(operation)} is not supported by this device."
        )
    raise FeatureUnsupportedError(f"{_display_name(operation)} cannot be used (state: {state}).")


def _display_name(operation: NormalizedOperation) -> str:
    return operation.value.replace("_", " ").capitalize()
