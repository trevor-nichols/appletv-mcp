import pytest

from appletv_screenshot.errors import SidecarError
from appletv_screenshot.exit_codes import ExitCode
from appletv_screenshot.target import (
    Candidate,
    is_apple_tv_product,
    require_apple_tv_product,
    require_configured_udid,
    select_target,
)

LIVING_ROOM = Candidate(udid="00008110-AAAA", product_type="AppleTV14,1")
BEDROOM = Candidate(udid="00008110-BBBB", product_type="AppleTV11,1")
PHONE = Candidate(udid="00008101-CCCC", product_type="iPhone14,2", name="Kitchen")


def test_configured_udid_wins_when_visible() -> None:
    assert select_target([BEDROOM, LIVING_ROOM], "00008110-AAAA") == "00008110-AAAA"


def test_configured_udid_missing_lists_visible_devices() -> None:
    with pytest.raises(SidecarError) as excinfo:
        select_target([LIVING_ROOM], "00008110-CCCC")
    assert excinfo.value.exit_code is ExitCode.DEVICE_NOT_FOUND
    assert "00008110-CCCC is not reachable" in excinfo.value.detail
    assert "00008110-AAAA (AppleTV14,1)" in excinfo.value.detail


def test_single_apple_tv_is_used_without_configuration() -> None:
    assert select_target([LIVING_ROOM], None) == "00008110-AAAA"


def test_iphone_only_is_rejected_without_configuration() -> None:
    with pytest.raises(SidecarError) as excinfo:
        select_target([PHONE], None)
    assert excinfo.value.exit_code is ExitCode.DEVICE_NOT_FOUND
    assert "no Apple TV is reachable" in excinfo.value.detail
    assert "00008101-CCCC (iPhone14,2)" in excinfo.value.detail


def test_iphone_plus_apple_tv_selects_the_apple_tv() -> None:
    assert select_target([PHONE, LIVING_ROOM], None) == "00008110-AAAA"


def test_configured_udid_that_is_an_iphone_is_rejected() -> None:
    with pytest.raises(SidecarError) as excinfo:
        select_target([PHONE, LIVING_ROOM], "00008101-CCCC")
    assert excinfo.value.exit_code is ExitCode.DEVICE_NOT_FOUND
    assert "not an Apple TV" in excinfo.value.detail
    assert "iPhone14,2" in excinfo.value.detail


def test_no_device_is_not_found() -> None:
    with pytest.raises(SidecarError) as excinfo:
        select_target([], None)
    assert excinfo.value.exit_code is ExitCode.DEVICE_NOT_FOUND
    assert excinfo.value.detail == "no Apple TV is reachable"


def test_two_apple_tvs_without_configuration_refuse_to_guess() -> None:
    with pytest.raises(SidecarError) as excinfo:
        select_target([LIVING_ROOM, BEDROOM], None)
    assert excinfo.value.exit_code is ExitCode.AMBIGUOUS_DEVICE
    assert "configure --udid <udid>" in excinfo.value.detail
    assert "00008110-AAAA (AppleTV14,1), 00008110-BBBB (AppleTV11,1)" in excinfo.value.detail


def test_configured_udid_with_nothing_visible_reports_none() -> None:
    with pytest.raises(SidecarError) as excinfo:
        select_target([], "00008110-AAAA")
    assert excinfo.value.detail.endswith("visible: none")


def test_capture_requires_a_configured_udid() -> None:
    with pytest.raises(SidecarError) as excinfo:
        require_configured_udid(None)
    assert excinfo.value.exit_code is ExitCode.AMBIGUOUS_DEVICE
    assert "configure --udid" in excinfo.value.detail
    assert require_configured_udid("00008110-AAAA") == "00008110-AAAA"


def test_product_type_helpers_accept_apple_tv_names() -> None:
    assert is_apple_tv_product("AppleTV14,1")
    assert is_apple_tv_product("Apple TV 4K")
    assert not is_apple_tv_product("iPhone14,2")
    assert not is_apple_tv_product(None)
    require_apple_tv_product("00008110-AAAA", "AppleTV14,1")
    with pytest.raises(SidecarError, match="unknown type"):
        require_apple_tv_product("00008110-AAAA", None)
