"""Logging redaction and exception translation tests."""

import logging

import pytest
from pyatv import exceptions as pyatv_exceptions

from agenai_appletv_mcp.domain.errors import (
    DeviceConnectionError,
    FeatureUnsupportedError,
    PairingRequiredError,
)
from agenai_appletv_mcp.infrastructure.observability.redaction import RedactionFilter, redact
from agenai_appletv_mcp.infrastructure.pyatv.exception_map import (
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
    logger = logging.getLogger("agenai_appletv_mcp.tests.redaction")
    logger.addFilter(RedactionFilter())
    secret = "a" * 40
    with caplog.at_level(logging.INFO, logger="agenai_appletv_mcp.tests.redaction"):
        logger.info("token=%s", secret)
    assert secret not in caplog.text
    assert "[redacted]" in caplog.text


def test_translate_pairing_and_unsupported() -> None:
    pairing = translate_exception(
        pyatv_exceptions.NoCredentialsError("missing"),
        operation="connect",
        may_have_been_delivered=False,
    )
    assert isinstance(pairing, PairingRequiredError)
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


def test_optional_absence_excludes_transport_errors() -> None:
    assert is_optional_absence(pyatv_exceptions.NotSupportedError("no")) is True
    assert is_optional_absence(pyatv_exceptions.InvalidStateError("busy")) is True
    assert is_optional_absence(pyatv_exceptions.ConnectionLostError("gone")) is False
    assert is_optional_absence(pyatv_exceptions.OperationTimeoutError("slow")) is False
    assert is_optional_absence(pyatv_exceptions.AuthenticationError("auth")) is False
