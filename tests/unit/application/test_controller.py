"""AppleTVController semantic operations, retry, and privacy tests."""

import logging

import pytest

from appletv_mcp.application.services.apple_tv_controller import (
    AppleTVController,
    validate_deep_link,
)
from appletv_mcp.domain.enums import (
    FeatureAvailability,
    KeyboardFocus,
    NormalizedOperation,
    PlaybackAction,
    PowerState,
    PowerTarget,
    PressAction,
    RemoteButton,
    SkipDirection,
    VolumeDirection,
)
from appletv_mcp.domain.errors import (
    AmbiguousAppError,
    AppNotFoundError,
    DeviceConnectionError,
    FeatureUnavailableError,
    FeatureUnsupportedError,
    InvalidUrlError,
    KeyboardNotFocusedError,
    PairingRequiredError,
    UncertainExecutionError,
)
from tests.helpers.factories import make_app, make_status
from tests.helpers.fakes import FakeGateway


def _controller(gateway: FakeGateway | None = None) -> tuple[AppleTVController, FakeGateway]:
    fake = gateway or FakeGateway()
    return AppleTVController(fake), fake


async def test_status_full_and_media_app_name() -> None:
    controller, _gateway = _controller()
    status = await controller.status()
    assert status.media_app is not None
    assert status.media_app.bundle_id == "com.apple.TV"
    dumped = status.model_dump()
    assert "active_app" not in dumped
    assert dumped["media_app"]["name"] == "TV"


async def test_status_unreachable_after_retry_exhaustion() -> None:
    gateway = FakeGateway()
    gateway.fail(DeviceConnectionError("offline", may_have_been_delivered=False), "status")
    controller, _ = _controller(gateway)
    status = await controller.status()
    assert status.connection.value == "unreachable"
    assert gateway.reconnect_calls == 1
    assert gateway.disconnect_calls == 1


async def test_read_retry_succeeds() -> None:
    gateway = FakeGateway()
    gateway.fail(DeviceConnectionError("drop", may_have_been_delivered=False), "capabilities")
    controller, _ = _controller(gateway)
    original_reconnect = gateway.reconnect

    async def reconnect() -> None:
        await original_reconnect()
        gateway.fail_with = None

    gateway.reconnect = reconnect  # type: ignore[method-assign]
    result = await controller.capabilities()
    assert result.play.value == "available"
    assert gateway.reconnect_calls == 1


async def test_capabilities_normalization() -> None:
    controller, gateway = _controller()
    gateway.features[NormalizedOperation.PAUSE] = FeatureAvailability.UNAVAILABLE
    gateway.capabilities_value = gateway.capabilities_value.model_copy(
        update={"pause": FeatureAvailability.UNAVAILABLE}
    )
    caps = await controller.capabilities()
    assert caps.pause is FeatureAvailability.UNAVAILABLE


async def test_list_apps_filter() -> None:
    controller, _ = _controller()
    apps = await controller.list_apps("tube")
    assert [app.name for app in apps] == ["YouTube"]


async def test_power_on_and_off() -> None:
    controller, gateway = _controller()
    on = await controller.power(PowerTarget.ON)
    off = await controller.power(PowerTarget.OFF)
    assert on.power_state.value == "on"
    assert off.power_state.value == "off"
    assert ("turn_on", None) in gateway.calls


async def test_power_reports_unknown_when_observed_state_does_not_match() -> None:
    controller, gateway = _controller()
    gateway.observed_power = PowerState.UNKNOWN
    result = await controller.power(PowerTarget.ON)
    assert result.requested_state is PowerTarget.ON
    assert result.power_state is PowerState.UNKNOWN
    assert gateway.reconnect_calls == 0


async def test_reconnect_propagates_pairing_required() -> None:
    gateway = FakeGateway()
    gateway.fail(DeviceConnectionError("drop", may_have_been_delivered=False), "capabilities")

    async def reconnect() -> None:
        gateway.reconnect_calls += 1
        raise PairingRequiredError("Apple TV pairing credentials are missing or invalid.")

    gateway.reconnect = reconnect  # type: ignore[method-assign]
    controller, _ = _controller(gateway)
    with pytest.raises(PairingRequiredError, match="pairing credentials"):
        await controller.capabilities()
    assert gateway.reconnect_calls == 1


async def test_open_app_bundle_id_and_name() -> None:
    controller, gateway = _controller()
    by_id = await controller.open_app("com.netflix.Netflix")
    by_name = await controller.open_app("youtube")
    assert by_id.launched is True
    assert gateway.launch_log == ["com.netflix.Netflix", "com.google.ios.youtube"]
    assert by_name.bundle_id == "com.google.ios.youtube"


async def test_open_app_missing_does_not_launch_candidate() -> None:
    controller, gateway = _controller()
    with pytest.raises(AppNotFoundError, match="Did you mean: Netflix"):
        await controller.open_app("Netflox")
    assert gateway.launch_log == []


async def test_open_app_ambiguous() -> None:
    controller, gateway = _controller()
    gateway.apps.append(make_app("Netflix", "com.netflix.duplicate"))
    with pytest.raises(AmbiguousAppError):
        await controller.open_app("Netflix")
    assert gateway.launch_log == []


async def test_open_url_accepts_custom_scheme() -> None:
    controller, gateway = _controller()
    result = await controller.open_url("youtube://watch?v=1")
    assert result.accepted is True
    assert gateway.launch_log == ["youtube://watch?v=1"]


async def test_open_url_not_replayed_after_uncertain_failure() -> None:
    controller, gateway = _controller()
    gateway.fail(DeviceConnectionError("lost", may_have_been_delivered=True), "launch_app")
    with pytest.raises(UncertainExecutionError, match="not retried"):
        await controller.open_url("youtube://watch?v=1")
    assert gateway.launch_log == []
    assert gateway.reconnect_calls == 0
    assert gateway.invalidate_calls == 1
    assert gateway.disconnect_calls == 1


async def test_open_app_is_retried_after_uncertain_failure() -> None:
    controller, gateway = _controller()
    gateway.fail(DeviceConnectionError("lost", may_have_been_delivered=True), "launch_app")
    original = gateway.reconnect

    async def reconnect() -> None:
        await original()
        gateway.fail_with = None

    gateway.reconnect = reconnect  # type: ignore[method-assign]
    result = await controller.open_app("com.netflix.Netflix")
    assert result.launched is True
    assert gateway.launch_log == ["com.netflix.Netflix"]
    assert gateway.reconnect_calls == 1
    assert gateway.disconnect_calls == 0


@pytest.mark.parametrize(
    "url",
    ["", "no-scheme", "https://example.com/\x00video", "1abc://x"],
)
def test_url_validation_rejects_malformed(url: str) -> None:
    with pytest.raises(InvalidUrlError):
        validate_deep_link(url)


async def test_seek_and_volume_and_text() -> None:
    controller, gateway = _controller()
    gateway.status_value = make_status(keyboard_focus=KeyboardFocus.FOCUSED)
    seek = await controller.seek(120)
    volume = await controller.set_volume(35)
    text = await controller.set_text("hello")
    empty = await controller.set_text("")
    assert seek.accepted is True
    assert volume.volume_percent == 35
    assert text.characters == 5
    assert empty.characters == 0
    assert gateway.text_log == ["hello", ""]


async def test_text_requires_focus() -> None:
    controller, gateway = _controller()
    gateway.status_value = make_status(keyboard_focus=KeyboardFocus.UNFOCUSED)
    with pytest.raises(KeyboardNotFocusedError):
        await controller.set_text("secret-value")
    assert gateway.text_log == []


async def test_every_remote_button_and_style() -> None:
    controller, gateway = _controller()
    for button in RemoteButton:
        for action in PressAction:
            gateway.press_log.clear()
            result = await controller.press(button, action, 1)
            assert result.completed == 1
            assert gateway.press_log == [(button, action)]


async def test_press_count_and_partial_completion() -> None:
    controller, gateway = _controller()
    result = await controller.press(RemoteButton.RIGHT, PressAction.TAP, 4)
    assert result.completed == 4
    assert len(gateway.press_log) == 4

    gateway.press_log.clear()
    calls = {"n": 0}

    async def press(button: RemoteButton, action: PressAction) -> None:
        calls["n"] += 1
        if calls["n"] == 3:
            raise DeviceConnectionError("lost", may_have_been_delivered=True)
        gateway.press_log.append((button, action))

    gateway.press = press  # type: ignore[method-assign]
    with pytest.raises(UncertainExecutionError, match="right button"):
        await controller.press(RemoteButton.RIGHT, PressAction.TAP, 5)
    assert len(gateway.press_log) == 2


async def test_playback_actions() -> None:
    controller, gateway = _controller()
    for action in PlaybackAction:
        await controller.playback(action)
    assert gateway.playback_log == list(PlaybackAction)


async def test_skip_and_relative_volume() -> None:
    controller, gateway = _controller()
    skip = await controller.skip(SkipDirection.FORWARD, 0)
    adjust = await controller.adjust_volume(VolumeDirection.DOWN, 3)
    assert skip.accepted is True
    assert adjust.completed_steps == 3
    assert gateway.skip_log == [(SkipDirection.FORWARD, 0)]
    assert len([item for item in gateway.volume_log if item[0] == "step"]) == 3


async def test_toggle_not_replayed_after_uncertain_failure() -> None:
    controller, gateway = _controller()
    gateway.fail(
        DeviceConnectionError("lost", may_have_been_delivered=True),
        "playback",
    )
    with pytest.raises(UncertainExecutionError, match="not retried"):
        await controller.playback(PlaybackAction.TOGGLE)
    assert gateway.reconnect_calls == 0
    assert gateway.invalidate_calls == 1
    assert gateway.disconnect_calls == 1


async def test_preflight_retry_then_dispatch_uncertain_is_uncertain() -> None:
    controller, gateway = _controller()
    gateway.fail(
        DeviceConnectionError("preflight", may_have_been_delivered=False),
        "feature_state",
    )
    original = gateway.reconnect

    async def reconnect() -> None:
        await original()
        gateway.fail(
            DeviceConnectionError("lost after right", may_have_been_delivered=True),
            "press",
        )

    gateway.reconnect = reconnect  # type: ignore[method-assign]
    with pytest.raises(UncertainExecutionError, match="not retried"):
        await controller.press(RemoteButton.RIGHT, PressAction.TAP, 1)
    assert gateway.reconnect_calls == 1
    assert gateway.press_log == []
    assert gateway.disconnect_calls == 1


async def test_power_off_not_replayed_after_uncertain_failure() -> None:
    controller, gateway = _controller()
    gateway.fail(DeviceConnectionError("lost", may_have_been_delivered=True), "turn_off")
    with pytest.raises(UncertainExecutionError, match="not retried"):
        await controller.power(PowerTarget.OFF)
    assert gateway.reconnect_calls == 0
    assert gateway.disconnect_calls == 1


async def test_power_on_is_retried_after_uncertain_failure() -> None:
    controller, gateway = _controller()
    gateway.fail(DeviceConnectionError("lost", may_have_been_delivered=True), "turn_on")
    original = gateway.reconnect

    async def reconnect() -> None:
        await original()
        gateway.fail_with = None

    gateway.reconnect = reconnect  # type: ignore[method-assign]
    result = await controller.power(PowerTarget.ON)
    assert result.requested_state is PowerTarget.ON
    assert gateway.reconnect_calls == 1


async def test_relative_skip_not_replayed() -> None:
    controller, gateway = _controller()
    gateway.fail(DeviceConnectionError("lost", may_have_been_delivered=True), "skip")
    with pytest.raises(UncertainExecutionError):
        await controller.skip(SkipDirection.BACKWARD, 15)
    assert gateway.reconnect_calls == 0
    assert gateway.disconnect_calls == 1


async def test_relative_volume_not_replayed() -> None:
    controller, gateway = _controller()
    gateway.fail(DeviceConnectionError("lost", may_have_been_delivered=True), "volume_step")
    with pytest.raises(UncertainExecutionError):
        await controller.adjust_volume(VolumeDirection.UP, 1)
    assert gateway.reconnect_calls == 0
    assert gateway.disconnect_calls == 1


async def test_idempotent_seek_is_retried() -> None:
    controller, gateway = _controller()
    gateway.fail(DeviceConnectionError("lost", may_have_been_delivered=True), "seek")
    original = gateway.reconnect

    async def reconnect() -> None:
        await original()
        gateway.fail_with = None

    gateway.reconnect = reconnect  # type: ignore[method-assign]
    result = await controller.seek(10)
    assert result.accepted is True
    assert gateway.reconnect_calls == 1


async def test_unsupported_and_unavailable_features() -> None:
    controller, gateway = _controller()
    gateway.features[NormalizedOperation.VOLUME_SET] = FeatureAvailability.UNSUPPORTED
    with pytest.raises(FeatureUnsupportedError):
        await controller.set_volume(10)
    gateway.features[NormalizedOperation.PAUSE] = FeatureAvailability.UNAVAILABLE
    with pytest.raises(FeatureUnavailableError):
        await controller.playback(PlaybackAction.PAUSE)


async def test_set_text_is_absent_from_logs(caplog: pytest.LogCaptureFixture) -> None:
    controller, gateway = _controller()
    gateway.status_value = make_status(keyboard_focus=KeyboardFocus.FOCUSED)
    secret = "hunter2-keyboard-secret"
    with caplog.at_level(logging.DEBUG, logger="appletv_mcp"):
        await controller.set_text(secret)
    combined = " ".join(record.getMessage() for record in caplog.records)
    assert secret not in combined
    assert "characters" in combined
