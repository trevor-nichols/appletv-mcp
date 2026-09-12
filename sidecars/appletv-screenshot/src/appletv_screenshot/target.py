"""Deterministic device selection. Never the first device found."""

from dataclasses import dataclass

from appletv_screenshot.errors import SidecarError
from appletv_screenshot.exit_codes import ExitCode


@dataclass(frozen=True, slots=True)
class Candidate:
    udid: str
    name: str | None = None

    def describe(self) -> str:
        return f"{self.udid} ({self.name})" if self.name else self.udid


def select_target(candidates: list[Candidate], configured_udid: str | None) -> str:
    """Return the UDID to capture from, or raise a `SidecarError`.

    With a configured UDID only an exact match is accepted. Without one, exactly
    one visible device is required; zero is not found and two or more is
    ambiguous, because capturing another household's Apple TV is worse than
    failing.
    """

    if configured_udid is not None:
        if any(candidate.udid == configured_udid for candidate in candidates):
            return configured_udid
        raise SidecarError(
            ExitCode.DEVICE_NOT_FOUND,
            f"configured device {configured_udid} is not reachable; "
            f"visible: {_describe_all(candidates)}",
        )
    if not candidates:
        raise SidecarError(ExitCode.DEVICE_NOT_FOUND, "no Apple TV is reachable")
    if len(candidates) > 1:
        raise SidecarError(
            ExitCode.AMBIGUOUS_DEVICE,
            "more than one device is reachable and no udid is configured; run "
            f"`appletv-screenshot configure --udid <udid>`; visible: {_describe_all(candidates)}",
        )
    return candidates[0].udid


def _describe_all(candidates: list[Candidate]) -> str:
    return ", ".join(candidate.describe() for candidate in candidates) or "none"
