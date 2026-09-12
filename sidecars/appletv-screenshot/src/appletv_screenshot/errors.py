"""One failure type: an exit code plus an operator-facing detail line."""

from appletv_screenshot.exit_codes import ExitCode


class SidecarError(Exception):
    def __init__(self, exit_code: ExitCode, detail: str) -> None:
        super().__init__(detail)
        self.exit_code = exit_code
        self.detail = detail
