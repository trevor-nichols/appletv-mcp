"""Screen-reader friendly diagnostic rendering."""

from dataclasses import dataclass
from enum import StrEnum


class CheckStatus(StrEnum):
    OK = "OK"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    status: CheckStatus
    detail: str
    required: bool = True

    @property
    def failed(self) -> bool:
        return self.status is CheckStatus.FAIL

    def line(self) -> str:
        return f"{self.status.value} {self.name}: {self.detail}"


def exit_code_for(checks: list[CheckResult]) -> int:
    return 1 if any(check.failed and check.required for check in checks) else 0


def render_device_row(index: int, name: str, identifier: str, address: str) -> str:
    return f"{index}. {name}  identifier={identifier}  host={address}"


def render_capability_summary(mapping: dict[str, str]) -> list[str]:
    return [f"{name}: {state}" for name, state in mapping.items()]
