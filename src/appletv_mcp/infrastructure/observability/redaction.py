"""Central log redaction so secrets are not scattered as ad-hoc replacements."""

import logging
import re

_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)\b(credentials?|password|passwd|secret|token|pairing[_-]?blob)\b(\s*[=:]\s*)([^\s,;]+)"
)
_LONG_HEX = re.compile(r"\b[0-9a-fA-F]{32,}\b")
_REDACTED = "[redacted]"


class RedactionFilter(logging.Filter):
    """Strip credential-like values from log records."""

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
        return True


def redact(value: str) -> str:
    redacted = _SENSITIVE_ASSIGNMENT.sub(rf"\1\2{_REDACTED}", value)
    return _LONG_HEX.sub(_REDACTED, redacted)


def _redact_arg(value: object) -> object:
    if isinstance(value, str):
        return redact(value)
    return value
