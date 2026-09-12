# appletv-screenshot

One-shot screen-capture helper for [Apple TV MCP](../../README.md). The MCP server
spawns it as a separate process, waits for one PNG, and maps its exit code to a
tool error. Nothing from `pymobiledevice3` is imported by the MCP package.

## Why a separate process

- `pymobiledevice3` is licensed GPL-3.0-or-later (see the pinned corpus at
  `docs/references/pymobiledevice3/index.md`). The MCP package is MIT. The process
  boundary keeps the two apart.
- RemoteXPC tunnels, developer pairing, and DVT sessions have their own failure
  modes. Isolating them means a screenshot failure can never take down Apple TV
  control, which runs over `pyatv` in the MCP process.

## Requirements

- Python 3.14.
- An Apple TV with tvOS 17 or later that has Developer Mode enabled and the
  developer disk image mounted. Without those the device refuses the DVT screenshot
  service and the helper exits with code 14. The pinned pymobiledevice3 troubleshooting
  guide covers the two steps (`amfi enable-developer-mode`, `mounter auto-mount`).
- `pymobiledevice3==11.12.4`. This pin was chosen from the latest stable release at the
  time of writing. It has not been exercised against Apple TV hardware in this
  repository; see Verification status below.

## Install

From the repository root:

```bash
uv tool install ./sidecars/appletv-screenshot
```

`pipx install ./sidecars/appletv-screenshot` also works. The MCP server resolves the
`appletv-screenshot` executable from its own `PATH`. If the MCP host launches the server
with a minimal environment, set `screen_capture.command` in the MCP configuration to the
absolute path printed by `uv tool dir --bin` or `which appletv-screenshot`.

## Pairing

Screenshots need a RemoteXPC developer pairing. This pairing is separate from the
`pyatv` (Companion) pairing that Apple TV MCP uses for control. Two transports exist.

### tunneld (macOS, Linux, Windows)

```bash
pymobiledevice3 remote pair
sudo pymobiledevice3 remote tunneld
```

Leave the daemon running. It listens on `127.0.0.1:49151` by default; pass
`--tunneld-host` and `--tunneld-port` to `configure` if you moved it. The helper reuses
the daemon's tunnel and never needs root itself.

### native (macOS only)

The helper rides Apple's own `remoted` tunnel through `remotepairingd`, so no daemon and
no root are needed. It relies on the Apple developer pairing already held by
`remotepairingd` for the current user. `pymobiledevice3 remote browse` lists the devices
that pairing knows. How to establish that pairing for an Apple TV is not covered by the
pinned pymobiledevice3 corpus in this repository; when the helper exits with code 12 on
this transport, the Apple TV is not paired with this Mac and the tunneld transport is the
documented alternative.

With `--transport auto` (the default) the helper tries native on macOS first, then tunneld.
On other systems only tunneld is tried.

## Configure

```bash
appletv-screenshot configure --udid 00008110-000A1B2C3D4E5F60
appletv-screenshot configure --transport tunneld --tunneld-port 49151
appletv-screenshot configure --timeout 15 --discovery-timeout 3
appletv-screenshot configure --clear-udid
```

Configuration lives in the `appletv-screenshot` platform config directory
(`platformdirs`). `APPLETV_SCREENSHOT_CONFIG_DIR` overrides it. The file holds only the
target UDID, transport, tunneld address, and timeouts. Pairing records stay where
`pymobiledevice3` or `remotepairingd` keep them.

Device selection is deterministic. With a configured UDID only that device is accepted.
Without one, exactly one reachable Apple TV is required; two or more exit with code 11
and the message lists the visible UDIDs so you can pick one.

## Capture

```bash
appletv-screenshot capture --output /absolute/path/screen.png
```

This is the only invocation Apple TV MCP makes. The helper:

1. Loads its configuration.
2. Opens the device over the first transport that succeeds.
3. Takes one screenshot over DVT.
4. Writes the PNG atomically to `--output` (sibling temp file, then rename).
5. Exits with `0`. Stdout stays empty. Progress goes to stderr only with `--verbose`.

The whole capture runs under one deadline (`timeout_seconds`, default 15 s). The MCP
server's own default deadline is 20 s, so a slow device produces exit code 16 from the
helper rather than a kill from the parent.

## Exit codes

Exit codes are the contract between the helper and the MCP server. The MCP repository
compares this table with its own copy in a test.

| Code | Name                  | Meaning                                                     |
| ---: | --------------------- | ----------------------------------------------------------- |
|    0 | `SUCCESS`             | PNG written to `--output`.                                  |
|    2 | `USAGE`               | Bad arguments (argparse) or invalid `configure` values.      |
|   10 | `DEVICE_NOT_FOUND`    | Configured device not reachable, or none visible.           |
|   11 | `AMBIGUOUS_DEVICE`    | Several devices visible and no UDID configured.             |
|   12 | `PAIRING_REQUIRED`    | The device rejected the pairing or is not paired.           |
|   13 | `TUNNEL_UNAVAILABLE`  | No usable transport (no tunneld, native unavailable).       |
|   14 | `CAPTURE_FAILED`      | Device reached, but no PNG came back from DVT.              |
|   15 | `OUTPUT_WRITE_FAILED` | PNG captured but `--output` could not be written.           |
|   16 | `CAPTURE_TIMEOUT`     | The capture exceeded `timeout_seconds`.                     |
|   17 | `CONFIG_INVALID`      | The helper's own config file is unreadable or invalid.      |

## Verification status

Every module has unit tests that run without hardware, using fake transports and fake
DVT sessions. The transport and capture code was written against the installed
pymobiledevice3 11.12.4 sources and its type hints. No Apple TV was captured in this
repository yet, so treat the pin and the transport behaviour as implemented and
fake-tested, not live-verified.

## Development

```bash
cd sidecars/appletv-screenshot
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

This project is intentionally not a member of the root `uv` workspace, so
`uv sync` at the repository root never installs `pymobiledevice3`.
