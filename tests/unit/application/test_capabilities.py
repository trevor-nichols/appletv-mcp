"""Capability policy tests."""

import pytest
from pyatv.const import FeatureName

from appletv_mcp.application.policies.capabilities import ensure_executable
from appletv_mcp.domain.enums import FeatureAvailability, NormalizedOperation
from appletv_mcp.domain.errors import FeatureUnavailableError, FeatureUnsupportedError
from appletv_mcp.infrastructure.pyatv.feature_map import FEATURE_MAP


def test_every_normalized_operation_has_feature_mapping() -> None:
    assert set(FEATURE_MAP) == set(NormalizedOperation)
    assert FEATURE_MAP[NormalizedOperation.NAVIGATE_BACK] is FeatureName.Menu
    assert FEATURE_MAP[NormalizedOperation.SEEK] is FeatureName.SetPosition
    assert FEATURE_MAP[NormalizedOperation.TEXT_SET] is FeatureName.TextSet
    assert FEATURE_MAP[NormalizedOperation.TOGGLE] is FeatureName.PlayPause


@pytest.mark.parametrize("state", [FeatureAvailability.AVAILABLE, FeatureAvailability.UNKNOWN])
def test_available_and_unknown_permit_execution(state: FeatureAvailability) -> None:
    ensure_executable(NormalizedOperation.PLAY, state)


def test_unavailable_raises_current_state_error() -> None:
    with pytest.raises(FeatureUnavailableError, match="currently playing"):
        ensure_executable(NormalizedOperation.PAUSE, FeatureAvailability.UNAVAILABLE)


def test_unsupported_raises_device_capability_error() -> None:
    with pytest.raises(FeatureUnsupportedError, match="not supported"):
        ensure_executable(NormalizedOperation.VOLUME_SET, FeatureAvailability.UNSUPPORTED)
