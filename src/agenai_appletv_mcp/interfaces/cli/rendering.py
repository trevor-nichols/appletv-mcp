"""Screen-reader friendly diagnostic rendering."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    ok: bool
    detail: str
    required: bool = True

    def line(self) -> str:
        status = "OK" if self.ok else "FAIL"
        return f"{status} {self.name}: {self.detail}"


def render_device_row(index: int, name: str, identifier: str, address: str) -> str:
    return f"{index}. {name}  identifier={identifier}  host={address}"


def render_capability_summary(mapping: dict[str, str]) -> list[str]:
    return [f"{name}: {state}" for name, state in mapping.items()]
