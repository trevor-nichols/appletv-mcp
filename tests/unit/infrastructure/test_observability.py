"""Logging redaction and exception translation tests."""

import io
import logging

import pytest
from pyatv import exceptions as pyatv_exceptions

from appletv_mcp.domain.errors import (
    CommandFailedError,
    CommandTimeoutError,
    DeviceConnectionError,
    FeatureUnsupportedError,
    PairingRequiredError,
)
from appletv_mcp.infrastructure.observability.redaction import RedactionFilter, redact
from appletv_mcp.infrastructure.pyatv.exception_map import (
    is_optional_absence,
    translate_exception,
)


def test_redact_credentials_and_hex() -> None:
    text = "credentials=abcd1234abcd1234abcd1234abcd1234 password=supersecret"
    redacted = redact(text)
    assert "supersecret" not in redacted
    assert "abcd1234abcd1234abcd1234abcd1234" not in redacted
    assert "[redacted]" in redacted


def test_redaction_filter_on_logger(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("appletv_mcp.tests.redaction")
    logger.addFilter(RedactionFilter())
    secret = "a" * 40
    with caplog.at_level(logging.INFO, logger="appletv_mcp.tests.redaction"):
        logger.info("token=%s", secret)
    assert secret not in caplog.text
    assert "[redacted]" in caplog.text


def test_redaction_filter_on_exception_message(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("appletv_mcp.tests.redaction_exc")
    logger.addFilter(RedactionFilter())
    secret = "b" * 40
    with caplog.at_level(logging.ERROR, logger="appletv_mcp.tests.redaction_exc"):
        try:
            raise RuntimeError(f"credentials={secret}")
        except RuntimeError:
            logger.exception("command failed")
    assert secret not in caplog.text
    assert "[redacted]" in caplog.text


def test_translate_pairing_and_unsupported() -> None:
    pairing = translate_exception(
        pyatv_exceptions.NoCredentialsError("missing"),
        operation="connect",
        may_have_been_delivered=False,
    )
    assert isinstance(pairing, PairingRequiredError)
    assert "appletv-mcp configure" in str(pairing)
    unsupported = translate_exception(
        pyatv_exceptions.NotSupportedError("no"),
        operation="volume",
        may_have_been_delivered=False,
    )
    assert isinstance(unsupported, FeatureUnsupportedError)
    lost = translate_exception(
        pyatv_exceptions.ConnectionLostError("bye"),
        operation="right button",
        may_have_been_delivered=True,
    )
    assert isinstance(lost, DeviceConnectionError)
    assert lost.may_have_been_delivered is True
    assert "credentials" not in str(pairing).lower() or "pairing" in str(pairing).lower()


def test_translate_backoff_and_blocked_state() -> None:
    backoff = translate_exception(
        pyatv_exceptions.BackOffError("wait"),
        operation="connect",
        may_have_been_delivered=True,
    )
    assert isinstance(backoff, CommandFailedError)
    assert "backoff" in str(backoff).lower()
    blocked = translate_exception(
        pyatv_exceptions.BlockedStateError("closed"),
        operation="right button",
        may_have_been_delivered=True,
    )
    assert isinstance(blocked, DeviceConnectionError)
    assert blocked.may_have_been_delivered is False
    invalid = translate_exception(
        pyatv_exceptions.InvalidResponseError("junk"),
        operation="status",
        may_have_been_delivered=False,
    )
    assert isinstance(invalid, CommandFailedError)


def test_optional_absence_excludes_transport_errors() -> None:
    assert is_optional_absence(pyatv_exceptions.NotSupportedError("no")) is True
    assert is_optional_absence(pyatv_exceptions.InvalidStateError("busy")) is True
    assert is_optional_absence(pyatv_exceptions.ConnectionLostError("gone")) is False
    assert is_optional_absence(pyatv_exceptions.OperationTimeoutError("slow")) is False
    assert is_optional_absence(pyatv_exceptions.AuthenticationError("auth")) is False


def _protocol_error_from(
    cause: BaseException, message: str = "Command _hidC failed"
) -> pyatv_exceptions.ProtocolError:
    error = pyatv_exceptions.ProtocolError(message)
    error.__cause__ = cause
    return error


def test_protocol_error_with_timeout_cause_is_timeout() -> None:
    mapped = translate_exception(
        _protocol_error_from(TimeoutError("response wait")),
        operation="right button",
        may_have_been_delivered=True,
    )
    assert isinstance(mapped, CommandTimeoutError)
    assert mapped.may_have_been_delivered is True


def test_protocol_error_with_connection_cause_is_connection_error() -> None:
    mapped = translate_exception(
        _protocol_error_from(pyatv_exceptions.ConnectionLostError("drop")),
        operation="open url",
        may_have_been_delivered=True,
    )
    assert isinstance(mapped, DeviceConnectionError)
    assert mapped.may_have_been_delivered is True


def test_protocol_error_stale_connection_is_connection_error() -> None:
    mapped = translate_exception(
        pyatv_exceptions.ProtocolError("Command failed: missing field"),
        operation="right button",
        may_have_been_delivered=True,
        connection_stale=True,
    )
    assert isinstance(mapped, DeviceConnectionError)
    assert mapped.may_have_been_delivered is True


def test_genuine_protocol_error_on_healthy_connection_is_command_failed() -> None:
    mapped = translate_exception(
        pyatv_exceptions.ProtocolError("Command failed: missing field"),
        operation="right button",
        may_have_been_delivered=True,
        connection_stale=False,
    )
    assert isinstance(mapped, CommandFailedError)
    assert "protocol error" in str(mapped).lower()


def test_debug_logging_does_not_emit_companion_rti_text() -> None:
    from pyatv.protocols.companion.plist_payloads import get_rti_input_text_payload

    from appletv_mcp.infrastructure.observability.logging import configure_logging

    stream = io.StringIO()
    configure_logging(debug=True)
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.DEBUG)
    root = logging.getLogger()
    root.addHandler(handler)
    secret = "Trevor123!"
    try:
        payload = get_rti_input_text_payload(b"\x11" * 16, secret)
        companion = logging.getLogger("pyatv.protocols.companion.protocol")
        companion.debug("Exchange OPACK: %s", {"_i": "_tiC", "_c": {"_tiD": payload}})
        companion.debug("Send OPACK: %s", {"_i": "_tiC", "_c": {"_tiD": payload}})
        logging.getLogger("appletv_mcp.tests.debug").debug("app-debug-marker")
        output = stream.getvalue()
        assert secret not in output
        assert "app-debug-marker" in output
        assert logging.getLogger("pyatv").getEffectiveLevel() == logging.WARNING
    finally:
        root.removeHandler(handler)
        configure_logging(debug=False)
