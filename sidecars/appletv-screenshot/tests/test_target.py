import pytest

from appletv_screenshot.errors import SidecarError
from appletv_screenshot.exit_codes import ExitCode
from appletv_screenshot.target import Candidate, select_target

LIVING_ROOM = Candidate(udid="00008110-AAAA", name="AppleTV14,1")
BEDROOM = Candidate(udid="00008110-BBBB")


def test_configured_udid_wins_when_visible() -> None:
    assert select_target([BEDROOM, LIVING_ROOM], "00008110-AAAA") == "00008110-AAAA"


def test_configured_udid_missing_lists_visible_devices() -> None:
    with pytest.raises(SidecarError) as excinfo:
        select_target([LIVING_ROOM], "00008110-CCCC")
    assert excinfo.value.exit_code is ExitCode.DEVICE_NOT_FOUND
    assert "00008110-CCCC is not reachable" in excinfo.value.detail
    assert "00008110-AAAA (AppleTV14,1)" in excinfo.value.detail


def test_single_visible_device_is_used_without_configuration() -> None:
    assert select_target([BEDROOM], None) == "00008110-BBBB"


def test_no_device_is_not_found() -> None:
    with pytest.raises(SidecarError) as excinfo:
        select_target([], None)
    assert excinfo.value.exit_code is ExitCode.DEVICE_NOT_FOUND
    assert excinfo.value.detail == "no Apple TV is reachable"


def test_two_devices_without_configuration_refuse_to_guess() -> None:
    with pytest.raises(SidecarError) as excinfo:
        select_target([LIVING_ROOM, BEDROOM], None)
    assert excinfo.value.exit_code is ExitCode.AMBIGUOUS_DEVICE
    assert "configure --udid <udid>" in excinfo.value.detail
    assert "00008110-AAAA (AppleTV14,1), 00008110-BBBB" in excinfo.value.detail


def test_configured_udid_with_nothing_visible_reports_none() -> None:
    with pytest.raises(SidecarError) as excinfo:
        select_target([], "00008110-AAAA")
    assert excinfo.value.detail.endswith("visible: none")
