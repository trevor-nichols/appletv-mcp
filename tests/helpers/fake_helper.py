"""Install the fake `appletv-screenshot` executable into a test directory."""

import shlex
import sys
from dataclasses import dataclass
from pathlib import Path

from tests.helpers.png import FAKE_SCREEN_PNG

_SCRIPT = Path(__file__).with_name("fake_screenshot_helper.py")


@dataclass(frozen=True, slots=True)
class InstalledFakeHelper:
    executable: Path
    state: Path

    def argv(self) -> list[str]:
        return (self.state / "argv").read_text(encoding="utf-8").split("\n")

    def cwd(self) -> Path:
        return Path((self.state / "cwd").read_text(encoding="utf-8"))

    def pid(self) -> int | None:
        pid_file = self.state / "pid"
        if not pid_file.is_file():
            return None
        return int(pid_file.read_text(encoding="utf-8"))


def install_fake_helper(
    directory: Path,
    mode: str,
    *,
    png: bytes = FAKE_SCREEN_PNG,
    name: str = "appletv-screenshot",
) -> InstalledFakeHelper:
    """Write an executable wrapper that runs the fake helper under this interpreter."""

    state = directory / f"{name}-state"
    state.mkdir()
    (state / "image.png").write_bytes(png)
    wrapper = directory / name
    command = " ".join(
        shlex.quote(part)
        for part in (sys.executable, str(_SCRIPT), "--mode", mode, "--state", str(state))
    )
    wrapper.write_text(f'#!/bin/sh\nexec {command} -- "$@"\n', encoding="utf-8")
    wrapper.chmod(0o700)
    return InstalledFakeHelper(executable=wrapper, state=state)
