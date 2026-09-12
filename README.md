# Apple TV MCP

Local MCP server that exposes **semantic Apple TV control** to AI agents. It is backed by [`pyatv`](https://pyatv.dev/) 0.18.0 and speaks MCP over stdio. The model should think in terms of power, apps, playback, text, volume, and screenshots, not Companion, MRP, AirPlay, or RemoteXPC.

This is a local, single-device, stdio-only server. It does not watch the Apple TV screen; it can take one screenshot at a time when the optional screen-capture helper is installed.

## What it does

- Reads structured device and playback status
- Turns the Apple TV on or off
- Lists and launches installed applications
- Opens application URLs and deep links
- Presses remote buttons (blind navigation)
- Controls playback, seek, and skip
- Types into a focused virtual keyboard
- Reads and sets volume when the device supports it
- Reports current capability availability
- Captures one PNG screenshot of the screen (v0.2, optional helper)

## Supported behavior (v0.2)

Exactly fourteen MCP tools, one configured Apple TV, persistent pairing via `pyatv` storage, lazy connection, and reconnection after disconnect. Screen capture runs through a separate helper process and is optional; the server starts and controls the TV without it. Pairing, unpairing, credentials, and multiple TVs are out of scope.

## Architecture at a glance

```text
interfaces/mcp + interfaces/cli
        │                          │
        ▼                          ▼
application/AppleTVController   application/ScreenCaptureService
  (app resolution, capability      (one capture at a time)
   policy, retry/idempotency)          │
        │                              ▼
        ▼                       infrastructure/screen_capture
infrastructure/pyatv              spawn appletv-screenshot, read one PNG
  gateway → connection manager         │
        │                              ▼
        ▼                       sidecars/appletv-screenshot (pymobiledevice3)
pyatv 0.18.0                           │
        │                              ▼
        ▼                          Apple TV (RemoteXPC / DVT)
   Apple TV (Companion / MRP / AirPlay)
```

Domain types never import `pyatv` or MCP. MCP tools never call `pyatv` directly. `appletv_mcp` never imports `pymobiledevice3`; the helper is a separate project with its own lockfile under `sidecars/appletv-screenshot/`.

## Requirements

- Python 3.14.7
- [uv](https://docs.astral.sh/uv/)
- An Apple TV on the local network
- Pairing credentials created with `atvremote` (shipped with pyatv)
- For screenshots only: the `appletv-screenshot` helper and a RemoteXPC developer pairing (see Screen capture)

## Installation

```bash
git clone https://github.com/trevor-nichols/appletv-mcp.git
cd appletv-mcp
uv sync --locked
```

The console entrypoint is `appletv-mcp`.

## Pairing

Pairing is setup, not an agent tool. Credentials stay in pyatv file storage (`~/.pyatv.conf`) and are never exposed through MCP.

```bash
uv run atvremote wizard
```

Follow the PIN prompts until the device is set up. Repeat for every protocol the wizard offers.

## Configure

```bash
uv run appletv-mcp configure
```

This scans the network, lets you select one Apple TV, and writes a device profile (identifier, display name, last-known IPv4 host, timeouts) under the platform config directory. Credentials are not copied into that file.

## Doctor

```bash
uv run appletv-mcp doctor
```

Non-destructive checks, one per line, screen-reader friendly. Exits non-zero when a required prerequisite fails (configuration, storage, discovery, identity, or connection). Screen-capture lines never change the exit code. A missing helper is `SKIP`. A helper contract mismatch or missing capture UDID is optional `FAIL` and skips the capture. A successful capture is `OK` with PNG dimensions.

## Screen capture

Screenshots come from a separate helper, `appletv-screenshot`, which the server runs as a one-shot subprocess per request. The helper uses [`pymobiledevice3`](https://github.com/doronz88/pymobiledevice3) 11.12.4 to open a RemoteXPC tunnel and ask the Apple TV's developer services for one PNG. Its full setup, transports, and exit codes are in [`sidecars/appletv-screenshot/README.md`](sidecars/appletv-screenshot/README.md).

Short version:

```bash
# 1. Install the helper next to the server (any Python tool installer works)
uv tool install ./sidecars/appletv-screenshot

# 2. Pair the Apple TV for developer access (this is separate from atvremote)
pymobiledevice3 remote pair

# 3. Pin the helper to one Apple TV UDID. Capture refuses to guess.
appletv-screenshot configure --udid <UDID>

# 4. Confirm. doctor reports the helper contract, the configured UDID, and one capture.
uv run appletv-mcp doctor
```

The Apple TV needs tvOS 17 or later with Developer Mode enabled and the developer disk image mounted. This developer pairing is separate from the `atvremote` pairing used for control.

The helper's default `auto` transport tries the macOS native `remoted` tunnel, then an in-process userspace tunnel over Wi-Fi RemotePairing, then a running privileged `tunneld`. Userspace is the no-root path on Linux and Windows. `sudo pymobiledevice3 remote tunneld` is a last resort, not the normal setup. See the helper README.

Server-side settings live under `screen_capture` in the Apple TV MCP config file and all have defaults:

```json
"screen_capture": {
  "command": "appletv-screenshot",
  "timeout_seconds": 20.0,
  "max_image_bytes": 33554432
}
```

Set `command` to an absolute path when the MCP host launches the server with a minimal `PATH`. Configuration files written by v0.1 load unchanged.

Screenshots are ephemeral. The PNG is written to a private temporary directory, returned as MCP image content, and deleted. Nothing is cached, logged, or kept.

## Serve

```bash
uv run appletv-mcp serve
```

Starts the MCP server on **stdio**. Application logs go to stderr. Do not write anything else to stdout while serving.

Debug logging:

```bash
uv run appletv-mcp serve --debug
```

`--debug` raises `appletv_mcp` to DEBUG. The `pyatv` logger stays at WARNING so Companion OPACK dumps (which include keyboard text and credentials) never reach the log.

## MCP host configuration

Use an absolute project path. Example generic stdio config:

```json
{
  "mcpServers": {
    "appletv-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/appletv-mcp",
        "run",
        "appletv-mcp",
        "serve"
      ]
    }
  }
}
```

Installed executable form, if `appletv-mcp` is on `PATH`:

```json
{
  "mcpServers": {
    "appletv-mcp": {
      "command": "/absolute/path/to/appletv-mcp",
      "args": ["serve"]
    }
  }
}
```

The server does not serve HTTP and does not use OAuth.

## Tool inventory

| Tool | Purpose |
| --- | --- |
| `apple_tv_status` | Structured device/playback status |
| `apple_tv_capabilities` | Normalized operation availability |
| `apple_tv_list_apps` | Launchable applications |
| `apple_tv_power` | Power on/off |
| `apple_tv_open_app` | Launch by exact bundle ID or exact name |
| `apple_tv_open_url` | Open a URL / deep link |
| `apple_tv_press` | Blind remote button |
| `apple_tv_playback` | Play/pause/toggle/stop/next/previous |
| `apple_tv_seek` | Absolute seek |
| `apple_tv_skip` | Relative skip |
| `apple_tv_set_text` | Focused keyboard text |
| `apple_tv_set_volume` | Absolute volume |
| `apple_tv_adjust_volume` | Relative volume steps |
| `apple_tv_screenshot` | One point-in-time PNG of the screen as MCP image content (optional helper) |

`apple_tv_screenshot` is the only tool that returns image content instead of a structured result, so it is also the only tool without an output schema.

## Perception limitations

The agent **does not watch the screen**. It can request one screenshot at a time with `apple_tv_screenshot`, and that image is stale the moment it arrives. Between screenshots nothing reports what is rendered or which control has focus.

Status `media_app` is the app associated with currently playing media, not a guaranteed foreground app. Do not claim that a menu item is highlighted, that Netflix is visibly open, or that a movie started on-screen unless observable `pyatv` state or a screenshot taken after the action actually shows it.

Protected video (most streaming apps during playback) may render as a black frame in a screenshot. Black is not evidence that playback stopped, and the server does not try to detect or work around it.

Remote navigation is a last resort. Prefer `apple_tv_open_app`, playback, seek, text, and volume; when navigation is unavoidable, take a screenshot afterwards instead of assuming where focus landed.

## Troubleshooting

| Symptom | What to try |
| --- | --- |
| MCP starts but tools fail | `appletv-mcp doctor` |
| Device not found | Confirm same LAN, wake the TV, re-run `configure` |
| Pairing / authentication errors | `atvremote wizard` again, then `configure` |
| IP changed | Normal. Identifier discovery should update `preferred_host` |
| `preferred_host` rejected | It must be an IPv4 address; pyatv 0.18.0 unicast scan does not accept hostnames |
| Keyboard tool fails | A text field must be focused on the TV |
| Feature unsupported | The TV/app does not implement that operation |
| Uncertain execution error | A non-idempotent command may have been delivered; it was not retried |
| Screenshot: helper could not be found | Install `appletv-screenshot` or set `screen_capture.command` to its absolute path; `doctor` shows what the server resolves |
| Screenshot: pairing required | Run `pymobiledevice3 remote pair` for the Apple TV (separate from `atvremote`). Userspace does not need a privileged tunneld |
| Screenshot: helper does not have an unambiguous Apple TV target | `appletv-screenshot configure --udid <UDID>` |
| Screenshot: timed out | Wake the TV, check the tunnel daemon, raise `screen_capture.timeout_seconds` (max 60) |
| Screenshot is black | Protected content; the frame is real, the picture is withheld by the device |

## Development

```bash
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

The helper is its own project. Run the same five commands inside `sidecars/appletv-screenshot/` to gate it; CI runs both. `uv sync` at the root never installs `pymobiledevice3`, and the published `appletv-mcp` wheel contains neither the helper nor a dependency on it.

## Tests

Ordinary `uv run pytest` uses fakes only. It does **not** require Apple hardware. Screen-capture tests run a fake `appletv-screenshot` script that exits with each contract code, hangs, ignores SIGTERM, or writes garbage, so the subprocess handling is exercised for real without a device.

Live device tests are opt-in:

```bash
APPLE_TV_INTEGRATION_TESTS=1 uv run pytest -m live
```

Do not run the live suite unless a paired Apple TV is available. Read-only live tests use `APPLE_TV_INTEGRATION_TESTS=1`; the screenshot live test is read-only and skips when the helper is not installed. Disruptive write tests also require `APPLE_TV_LIVE_WRITES=1`.

## Security and privacy

- Pairing credentials remain in local pyatv storage
- Credentials are not MCP parameters or results
- Keyboard text is not logged (`--debug` does not enable raw pyatv protocol dumps)
- Screenshot bytes are never logged; logs carry only byte counts and dimensions
- The screenshot helper runs with no shell, fixed arguments, detached standard streams, and a private temporary output directory that is removed after every call
- RemoteXPC pairing records stay with `pymobiledevice3`; the server never reads them
- No DRM circumvention: protected frames come back as the device renders them
- The server is local stdio only

## License

MIT for `appletv-mcp`. The optional helper under `sidecars/appletv-screenshot/` depends on `pymobiledevice3`, which is licensed GPL-3.0-or-later; the process boundary keeps that dependency out of the MCP package.
