"""Deterministic Apple TV selection. Never the first device found."""

from dataclasses import dataclass

from appletv_screenshot.errors import SidecarError
from appletv_screenshot.exit_codes import ExitCode

APPLE_TV_PRODUCT_PREFIX = "AppleTV"


@dataclass(frozen=True, slots=True)
class Candidate:
    udid: str
    product_type: str | None = None
    name: str | None = None

    def describe(self) -> str:
        label = self.product_type or self.name
        return f"{self.udid} ({label})" if label else self.udid


def is_apple_tv_product(product_type: str | None) -> bool:
    """True when `product_type` is an Apple TV model identifier or display name."""

    if not product_type:
        return False
    return product_type.startswith((APPLE_TV_PRODUCT_PREFIX, "Apple TV"))


def require_configured_udid(udid: str | None) -> str:
    if udid:
        return udid
    raise SidecarError(
        ExitCode.AMBIGUOUS_DEVICE,
        "capture requires a configured UDID; run `appletv-screenshot configure --udid <udid>`",
    )


def require_apple_tv_product(udid: str, product_type: str | None) -> None:
    if is_apple_tv_product(product_type):
        return
    label = product_type or "unknown type"
    raise SidecarError(
        ExitCode.DEVICE_NOT_FOUND,
        f"configured device {udid} is {label}, not an Apple TV",
    )


def select_target(candidates: list[Candidate], configured_udid: str | None) -> str:
    """Return the UDID to capture from, or raise a `SidecarError`.

    Known non-Apple-TV product types are never captured. A configured UDID must
    match a visible device and must not be a phone, pad, or other product.
    Without a UDID, exactly one visible Apple TV is required.
    """

    if configured_udid is not None:
        match = next((item for item in candidates if item.udid == configured_udid), None)
        if match is None:
            raise SidecarError(
                ExitCode.DEVICE_NOT_FOUND,
                f"configured device {configured_udid} is not reachable; "
                f"visible: {_describe_all(candidates)}",
            )
        if match.product_type is not None:
            require_apple_tv_product(configured_udid, match.product_type)
        return configured_udid

    apple_tvs = [item for item in candidates if is_apple_tv_product(item.product_type)]
    others = [
        item
        for item in candidates
        if item.product_type is not None and not is_apple_tv_product(item.product_type)
    ]
    if not apple_tvs:
        extra = ""
        if others:
            extra = f"; ignored non-Apple-TV device(s): {_describe_all(others)}"
        raise SidecarError(ExitCode.DEVICE_NOT_FOUND, f"no Apple TV is reachable{extra}")
    if len(apple_tvs) > 1:
        raise SidecarError(
            ExitCode.AMBIGUOUS_DEVICE,
            "more than one Apple TV is reachable and no udid is configured; run "
            f"`appletv-screenshot configure --udid <udid>`; visible: {_describe_all(apple_tvs)}",
        )
    return apple_tvs[0].udid


def _describe_all(candidates: list[Candidate]) -> str:
    return ", ".join(candidate.describe() for candidate in candidates) or "none"
