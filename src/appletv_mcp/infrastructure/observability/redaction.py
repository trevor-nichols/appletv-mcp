"""Central log redaction so secrets are not scattered as ad-hoc replacements."""

import logging
import re
import traceback

_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)\b(credentials?|password|passwd|secret|token|pairing[_-]?blob)\b(\s*[=:]\s*)([^\s,;]+)"
)
_LONG_HEX = re.compile(r"\b[0-9a-fA-F]{32,}\b")
_REDACTED = "[redacted]"


class RedactionFilter(logging.Filter):
    """Strip credential-like values from log records, including exception text."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.args:
            if isinstance(record.args, dict):
                record.args = {key: _redact_arg(value) for key, value in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(_redact_arg(arg) for arg in record.args)
        try:
            formatted = record.getMessage()
        except Exception:
            formatted = str(record.msg)
        record.msg = redact(formatted)
        record.args = ()
        _redact_exception(record)
        if isinstance(record.stack_info, str):
            record.stack_info = redact(record.stack_info)
        return True


class RedactingFormatter(logging.Formatter):
    """Formatter that redacts the fully rendered line, including traceback text."""

    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


def redact(value: str) -> str:
    redacted = _SENSITIVE_ASSIGNMENT.sub(rf"\1\2{_REDACTED}", value)
    return _LONG_HEX.sub(_REDACTED, redacted)


def _redact_arg(value: object) -> object:
    if isinstance(value, str):
        return redact(value)
    return value


def _redact_exception(record: logging.LogRecord) -> None:
    if record.exc_text:
        record.exc_text = redact(record.exc_text)
        return
    if not record.exc_info:
        return
    try:
        formatted = "".join(traceback.format_exception(*record.exc_info))
    except Exception:
        formatted = str(record.exc_info[1] or "")
    record.exc_text = redact(formatted)
