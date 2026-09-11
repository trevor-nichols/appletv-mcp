"""Normalized capability snapshot for operations this server exposes."""

from pydantic import BaseModel, ConfigDict

from agenai_appletv_mcp.domain.enums import FeatureAvailability, NormalizedOperation


class AppleTVCapabilities(BaseModel):
    """Availability of each semantic operation on the current device."""

    model_config = ConfigDict(extra="forbid")

    power_on: FeatureAvailability
    power_off: FeatureAvailability
    list_apps: FeatureAvailability
    launch_app: FeatureAvailability
    navigate_up: FeatureAvailability
    navigate_down: FeatureAvailability
    navigate_left: FeatureAvailability
    navigate_right: FeatureAvailability
    navigate_select: FeatureAvailability
    navigate_back: FeatureAvailability
    navigate_home: FeatureAvailability
    play: FeatureAvailability
    pause: FeatureAvailability
    toggle: FeatureAvailability
    stop: FeatureAvailability
    next: FeatureAvailability
    previous: FeatureAvailability
    seek: FeatureAvailability
    skip_forward: FeatureAvailability
    skip_backward: FeatureAvailability
    text_set: FeatureAvailability
    volume_get: FeatureAvailability
    volume_set: FeatureAvailability
    volume_up: FeatureAvailability
    volume_down: FeatureAvailability
    keyboard_focus: FeatureAvailability

    def for_operation(self, operation: NormalizedOperation) -> FeatureAvailability:
        return getattr(self, operation.value)

    def as_mapping(self) -> dict[str, FeatureAvailability]:
        return {operation.value: self.for_operation(operation) for operation in NormalizedOperation}
