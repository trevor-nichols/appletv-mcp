"""Standard-library CLI for configure, doctor, and serve."""

import argparse
import asyncio
import math
import sys
from collections.abc import Awaitable, Sequence

from agenai_appletv_mcp._version import __version__
from agenai_appletv_mcp.domain.errors import AppleTVError
from agenai_appletv_mcp.infrastructure.observability.logging import configure_logging
from agenai_appletv_mcp.interfaces.cli.commands.configure import ConfigureError, run_configure
from agenai_appletv_mcp.interfaces.cli.commands.doctor import run_doctor
from agenai_appletv_mcp.interfaces.cli.commands.serve import run_serve


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    configure_logging(debug=getattr(args, "debug", False))
    if args.command == "configure":
        return _run_async(_configure(args))
    if args.command == "doctor":
        return _run_async(run_doctor(stdout=sys.stdout))
    if args.command == "serve":
        return run_serve(debug=args.debug)
    parser.error("unknown command")
    return 2


def _positive_timeout(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be a finite number greater than zero")
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agenai-appletv",
        description="Local MCP server and setup tools for Apple TV control.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    configure = sub.add_parser("configure", help="Discover and save the target Apple TV.")
    configure.add_argument(
        "--scan-timeout",
        type=_positive_timeout,
        default=5.0,
        help="Discovery timeout in seconds (default: 5).",
    )
    configure.add_argument("--debug", action="store_true", help="Enable debug logging.")

    doctor = sub.add_parser("doctor", help="Run non-destructive setup diagnostics.")
    doctor.add_argument("--debug", action="store_true", help="Enable debug logging.")

    serve = sub.add_parser("serve", help="Run the MCP server on stdio.")
    serve.add_argument("--debug", action="store_true", help="Enable debug logging on stderr.")
    return parser


async def _configure(args: argparse.Namespace) -> int:
    try:
        return await run_configure(
            stdin=sys.stdin,
            stdout=sys.stdout,
            scan_timeout_seconds=args.scan_timeout,
        )
    except ConfigureError as exc:
        sys.stderr.write(f"{exc}\n")
        return exc.exit_code
    except AppleTVError as exc:
        sys.stderr.write(f"{exc.message}\n")
        return 1


def _run_async(coro: Awaitable[int]) -> int:
    return asyncio.run(coro)
