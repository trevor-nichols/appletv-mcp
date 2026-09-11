"""Process logging configuration. MCP stdio owns stdout; logs go to stderr."""

import logging
import sys

from appletv_mcp.infrastructure.observability.redaction import RedactingFormatter, RedactionFilter

_APP_LOGGER = "appletv_mcp"
_PYATV_LOGGER = "pyatv"


class _LoggingState:
    installed = False


def configure_logging(*, debug: bool = False) -> None:
    """Install stderr logging with secret redaction.

    Safe to call more than once; subsequent calls update levels.
    """

    root = logging.getLogger()
    if not _LoggingState.installed:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(RedactingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        handler.addFilter(RedactionFilter())
        root.handlers.clear()
        root.addHandler(handler)
        _LoggingState.installed = True

    root.setLevel(logging.DEBUG if debug else logging.INFO)
    logging.getLogger(_APP_LOGGER).setLevel(logging.DEBUG if debug else logging.INFO)
    # Never enable pyatv DEBUG. Companion logs full OPACK frames, including RTI
    # keyboard payloads and pairing credentials, which cannot be reliably redacted.
    logging.getLogger(_PYATV_LOGGER).setLevel(logging.WARNING)
