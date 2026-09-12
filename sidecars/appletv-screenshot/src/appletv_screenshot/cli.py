"""Command line for the `appletv-screenshot` helper.

`capture --output PATH` is the machine-facing entry point that Apple TV MCP
spawns. Its stdout stays empty and every failure maps to one `ExitCode`.
`configure` and `--version` are for the operator.
"""

import argparse
import asyncio
import logging
import sys
from collections.abc import Callable, Sequence
from importlib import metadata
from pathlib import Path
from typing import TextIO

from pydantic import ValidationError

from appletv_screenshot import __version__
from appletv_screenshot.capture import capture_to_file
from appletv_screenshot.config import SidecarConfig, Transport, load_config, save_config
from appletv_screenshot.errors import SidecarError
from appletv_screenshot.exit_codes import CONTRACT_VERSION, ExitCode

PROG = "appletv-screenshot"
INTERRUPTED_EXIT_STATUS = 130

logger = logging.getLogger(__name__)

Handler = Callable[[argparse.Namespace], ExitCode]


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(verbose=args.verbose)
    handler: Handler = args.handler
    try:
        return int(handler(args))
    except SidecarError as exc:
        _emit(sys.stderr, f"{PROG}: {exc.detail}")
        return int(exc.exit_code)
    except KeyboardInterrupt:
        _emit(sys.stderr, f"{PROG}: interrupted")
        return INTERRUPTED_EXIT_STATUS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Capture one PNG screenshot of the configured Apple TV.",
    )
    parser.add_argument("--version", action="version", version=version_line())
    parser.add_argument(
        "--verbose", action="store_true", help="Log progress to stderr at INFO level."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture = subparsers.add_parser("capture", help="Write one screenshot to --output.")
    capture.add_argument(
        "--output", required=True, help="Destination PNG path. Written atomically."
    )
    capture.set_defaults(handler=run_capture)

    configure = subparsers.add_parser(
        "configure", help="Choose the target Apple TV and transport. Stores no pairing data."
    )
    target = configure.add_mutually_exclusive_group()
    target.add_argument("--udid", help="UDID of the Apple TV to capture.")
    target.add_argument("--clear-udid", action="store_true", help="Forget the configured UDID.")
    configure.add_argument(
        "--transport",
        choices=[transport.value for transport in Transport],
        help="auto tries native (macOS), then userspace, then a running tunneld.",
    )
    configure.add_argument("--tunneld-host", help="Host of a running tunneld.")
    configure.add_argument("--tunneld-port", type=int, help="Port of a running tunneld.")
    configure.add_argument("--timeout", type=float, help="Seconds allowed for one whole capture.")
    configure.add_argument("--discovery-timeout", type=float, help="Seconds to browse for devices.")
    configure.set_defaults(handler=run_configure)
    identify = subparsers.add_parser(
        "identify",
        help="Print the helper's configured target as JSON. Stores and pairs nothing.",
    )
    identify.set_defaults(handler=run_identify)
    return parser


def run_capture(args: argparse.Namespace) -> ExitCode:
    output = Path(args.output).expanduser().resolve()
    config = load_config()
    size = asyncio.run(capture_to_file(config, output))
    logger.info("wrote %d bytes to %s", size, output)
    return ExitCode.SUCCESS


def run_configure(args: argparse.Namespace) -> ExitCode:
    try:
        current = load_config()
    except SidecarError as exc:
        _emit(sys.stderr, f"{PROG}: replacing unreadable configuration ({exc.detail})")
        current = SidecarConfig()
    payload: dict[str, object] = current.model_dump(mode="json")
    if args.clear_udid:
        payload["udid"] = None
    updates = {
        "udid": args.udid,
        "transport": args.transport,
        "tunneld_host": args.tunneld_host,
        "tunneld_port": args.tunneld_port,
        "timeout_seconds": args.timeout,
        "discovery_timeout_seconds": args.discovery_timeout,
    }
    payload.update({key: value for key, value in updates.items() if value is not None})
    try:
        config = SidecarConfig.model_validate(payload)
    except ValidationError as exc:
        details = "; ".join(str(error["msg"]) for error in exc.errors())
        raise SidecarError(ExitCode.USAGE, f"invalid configuration: {details}") from exc
    path = save_config(config)
    _emit(sys.stdout, f"wrote {path}")
    _emit(sys.stdout, config.model_dump_json(indent=2))
    return ExitCode.SUCCESS


def run_identify(_args: argparse.Namespace) -> ExitCode:
    config = load_config()
    _emit(sys.stdout, config.model_dump_json())
    return ExitCode.SUCCESS


def version_line() -> str:
    try:
        dependency = metadata.version("pymobiledevice3")
    except metadata.PackageNotFoundError:
        dependency = "missing"
    return f"{PROG} {__version__} contract={CONTRACT_VERSION} pymobiledevice3={dependency}"


def configure_logging(*, verbose: bool) -> None:
    level = logging.INFO if verbose else logging.WARNING
    logging.basicConfig(
        level=level, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s"
    )
    # Pair records and tunnel frames show up in pymobiledevice3 below WARNING.
    logging.getLogger("pymobiledevice3").setLevel(logging.WARNING)


def _emit(stream: TextIO, line: str) -> None:
    stream.write(line + "\n")
    stream.flush()
