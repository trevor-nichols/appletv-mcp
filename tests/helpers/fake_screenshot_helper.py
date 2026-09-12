"""Stand-in for the `appletv-screenshot` executable, driven by `--mode`.

Runs as a separate OS process under the test interpreter. It records the
arguments and working directory it received so tests can assert the adapter's
fixed argument shape, and it writes noise to stdout/stderr so tests can prove
that noise never reaches server logs or model-visible errors.
"""

import argparse
import os
import signal
import sys
from pathlib import Path

STDOUT_NOISE = "stdout noise: pairing token 0xDEADBEEF"
STDERR_NOISE = "Traceback (most recent call last): secret-pair-record"


def _hang_forever() -> None:
    while True:
        signal.pause()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("helper_args", nargs=argparse.REMAINDER)
    namespace = parser.parse_args()
    mode: str = namespace.mode
    state: Path = namespace.state
    args: list[str] = list(namespace.helper_args)
    if args and args[0] == "--":
        args = args[1:]

    (state / "argv").write_text("\n".join(args), encoding="utf-8")
    (state / "cwd").write_text(str(Path.cwd()), encoding="utf-8")
    (state / "pid").write_text(str(os.getpid()), encoding="utf-8")

    if args == ["--version"]:
        contract = "2" if mode == "contract-mismatch" else "1"
        print(
            f"appletv-screenshot 0.2.0 contract={contract} pymobiledevice3=fake",
            flush=True,
        )
        return 0
    if args == ["identify"]:
        if mode == "no-udid":
            print('{"udid":null,"transport":"auto"}', flush=True)
        else:
            print('{"udid":"00008110-AAAA","transport":"auto"}', flush=True)
        return 0

    print(STDOUT_NOISE, flush=True)
    print(STDERR_NOISE, file=sys.stderr, flush=True)

    if len(args) != 3 or args[0] != "capture" or args[1] != "--output":
        return 2
    output = Path(args[2])
    image = (state / "image.png").read_bytes()

    if mode == "success":
        output.write_bytes(image)
        return 0
    if mode.startswith("exit:"):
        return int(mode.removeprefix("exit:"))
    if mode.startswith("write-then-exit:"):
        output.write_bytes(image)
        return int(mode.removeprefix("write-then-exit:"))
    if mode == "hang":
        _hang_forever()
    if mode == "hang-ignore-term":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        _hang_forever()
    if mode == "no-output":
        return 0
    if mode == "empty":
        output.write_bytes(b"")
        return 0
    if mode == "garbage":
        output.write_bytes(b"definitely not a png " * 8)
        return 0
    raise SystemExit(f"fake helper: unknown mode {mode!r}")


if __name__ == "__main__":
    sys.exit(main())
