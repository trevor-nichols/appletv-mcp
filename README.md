# Apple TV MCP

Local MCP server that exposes **semantic Apple TV control** to AI agents. It is backed by [`pyatv`](https://pyatv.dev/) 0.18.0 and speaks MCP over stdio. The model should think in terms of power, apps, playback, text, and volume — not Companion, MRP, or AirPlay.

This is a local, single-device, stdio-only server. It cannot see the Apple TV screen.

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

## Supported behavior (v0.1)

Exactly thirteen MCP tools, one configured Apple TV, persistent pairing via `pyatv` storage, lazy connection, and reconnection after disconnect. Pairing, unpairing, credentials, screen capture, and multiple TVs are out of scope.

## Architecture at a glance

```text
interfaces/mcp + interfaces/cli
        │
        ▼
application/AppleTVController
  (app resolution, capability policy, retry/idempotency)
        │
        ▼
infrastructure/pyatv
  gateway → connection manager → discovery / FileStorage
        │
        ▼
pyatv 0.18.0
```

Domain types never import `pyatv` or MCP. MCP tools never call `pyatv` directly.

## Requirements

- Python 3.14.7
- [uv](https://docs.astral.sh/uv/)
- An Apple TV on the local network
- Pairing credentials created with `atvremote` (shipped with pyatv)

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

Non-destructive checks, one per line, screen-reader friendly. Exits non-zero when a required prerequisite fails (configuration, storage, discovery, identity, or connection).

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

v0.1 does not serve HTTP and does not use OAuth.

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

## Perception limitations

The agent **cannot see the screen**. Status `media_app` is the app associated with currently playing media, not a guaranteed foreground app. Do not claim that a menu item is highlighted, that Netflix is visibly open, or that a movie started on-screen unless observable `pyatv` state actually says so.

Remote navigation is a last resort. Prefer `apple_tv_open_app`, playback, seek, text, and volume.

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

## Development

```bash
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

## Tests

Ordinary `uv run pytest` uses fakes only. It does **not** require Apple hardware.

Live device tests are opt-in:

```bash
APPLE_TV_INTEGRATION_TESTS=1 uv run pytest -m live
```

Do not run the live suite unless a paired Apple TV is available. Read-only live tests use `APPLE_TV_INTEGRATION_TESTS=1`. Disruptive write tests also require `APPLE_TV_LIVE_WRITES=1`.

## Security and privacy

- Pairing credentials remain in local pyatv storage
- Credentials are not MCP parameters or results
- Keyboard text is not logged (`--debug` does not enable raw pyatv protocol dumps)
- v0.1 is local stdio only

## License

MIT
