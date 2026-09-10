# AgenAI Apple TV MCP

**Status:** Approved v0.1 Specification  
**Project:** `agenai-appletv-mcp`  
**Primary purpose:** Expose reliable, semantic Apple TV control to AI agents through a local MCP server backed by `pyatv`.

---

## 1. Goal

Build a local MCP server that allows an AI agent to reliably control one paired Apple TV over the local network without interacting with the Apple TV Remote UI.

The server must expose high-level Apple TV actions including:

- Read device and playback status.
- Turn the Apple TV on or off.
- Launch installed applications.
- Open application URLs and deep links.
- Navigate the Apple TV interface.
- Control playback.
- Seek and skip.
- Enter text into a focused Apple TV text field.
- Read and control volume when supported.
- Inspect the capabilities currently available on the device.

The MCP contract must remain independent of Apple-specific protocols. `pyatv` is an implementation detail behind the controller layer.

---

## 2. Runtime Baseline

Use only stable releases.

```text
Python:           3.14.7
pyatv:            0.18.0
MCP Python SDK:   2.2.0
MCP protocol:     SDK-negotiated; current SDK targets 2026-07-28
Package manager:  uv
```

Pin direct production dependencies and commit `uv.lock`.

Recommended direct dependencies:

```toml
[project]
name = "agenai-appletv-mcp"
version = "0.1.0"
requires-python = ">=3.14,<3.15"

dependencies = [
    "mcp[cli]==2.2.0",
    "pyatv==0.18.0",
    "pydantic>=2.12,<3",
    "platformdirs",
]

[dependency-groups]
dev = [
    "pytest",
    "pytest-asyncio",
    "ruff",
    "pyright",
]
```

The repository should include:

```text
.python-version
```

with:

```text
3.14.7
```

---

## 3. Design Principles

### 3.1 Semantic MCP Interface

MCP tools represent user intentions, not `pyatv` implementation methods.

Preferred:

```text
apple_tv_status
apple_tv_open_app
apple_tv_power
apple_tv_set_volume
```

Avoid protocol-shaped tools such as:

```text
companion_launch_app
mrp_button_command
airplay_send_command
```

The model should never need to know which Apple protocol performs an operation.

### 3.2 `pyatv` Owns Protocol Selection

Connect all usable services discovered for the Apple TV and allow `pyatv` protocol relaying to select the best implementation.

Do not hard-code assumptions such as:

- Navigation always uses Companion.
- Metadata always uses MRP.
- Power always uses one protocol.
- App launching always uses one protocol.

### 3.3 Stable Device Identity

The configured Apple TV is identified primarily by a stable `pyatv` device identifier.

Do not use either of the following as identity:

- Display name.
- IP address.

Store the last-known host only as a connection optimization.

Resolution strategy:

```text
stable identifier
      │
      ├── preferred/last-known host available?
      │        │
      │        ├── yes → unicast scan at host
      │        │           │
      │        │           └── verify identifier
      │        │
      │        └── failure
      │
      └── multicast scan by stable identifier
```

### 3.4 Credentials Stay Out of MCP

Pairing credentials must never:

- Become MCP tool parameters.
- Be returned by MCP tools.
- Appear in normal logs.
- Be included in structured status responses.
- Be exposed to the model.

`pyatv` persistent storage owns credentials.

### 3.5 Feature-Gated Execution

Do not assume every Apple TV exposes every operation.

Before invoking feature-dependent behavior, consult the `pyatv` feature API.

Normalized behavior:

```text
Available     → execute
Unknown       → attempt execution
Unavailable   → ToolError explaining current-state limitation
Unsupported   → ToolError explaining device limitation
```

Feature checks belong in the controller layer rather than being duplicated inside MCP handlers.

### 3.6 Prefer Semantic Actions Over Blind Navigation

Use semantic operations whenever available.

Preferred:

```text
open_app("YouTube")
pause()
seek(120)
set_text("Severance")
set_volume(35)
```

Fallback only:

```text
right
right
down
select
```

Remote navigation is blind and non-idempotent.

---

## 4. High-Level Architecture

```text
                    AI Agent
                       │
                       │ MCP
                       ▼
             ┌─────────────────────┐
             │      MCPServer      │
             │                     │
             │ semantic tools      │
             │ typed schemas       │
             │ structured results  │
             └─────────┬───────────┘
                       │
                       ▼
             ┌─────────────────────┐
             │ AppleTVController   │
             │                     │
             │ app resolution      │
             │ feature gating      │
             │ command semantics   │
             │ error translation   │
             └─────────┬───────────┘
                       │
                       ▼
             ┌─────────────────────┐
             │ ConnectionManager   │
             │                     │
             │ scan                │
             │ connect             │
             │ reconnect           │
             │ persistent storage  │
             └─────────┬───────────┘
                       │
                       ▼
                   pyatv 0.18
                       │
          ┌────────────┼────────────┐
          │            │            │
      Companion       MRP        AirPlay/RAOP
          │            │            │
          └────────────┴────────────┘
                       │
                       ▼
                   Apple TV
```

---

## 5. Repository Structure

```text
agenai-appletv-mcp/
├── pyproject.toml
├── uv.lock
├── .python-version
├── README.md
├── SPEC.md
├── IMPLEMENTATION_CHECKLIST.md
│
├── references/
│   └── ...
│
├── src/
│   └── agenai_appletv_mcp/
│       ├── __init__.py
│       ├── server.py
│       ├── lifespan.py
│       ├── controller.py
│       ├── connection.py
│       ├── config.py
│       ├── models.py
│       ├── errors.py
│       └── cli.py
│
└── tests/
    ├── conftest.py
    ├── test_server.py
    ├── test_controller.py
    ├── test_connection.py
    ├── test_models.py
    └── test_tools.py
```

---

## 6. Configuration

The application maintains a small device profile separate from `pyatv` credentials.

Example:

```json
{
  "device_identifier": "00:11:22:33:44:55",
  "device_name": "Living Room",
  "preferred_host": "192.168.1.50",
  "scan_timeout_seconds": 5,
  "command_timeout_seconds": 10
}
```

Use `platformdirs` to determine the application configuration directory.

Configuration semantics:

- `device_identifier` is authoritative.
- `device_name` is informational.
- `preferred_host` is an optimization.
- `preferred_host` may be replaced whenever the configured device is rediscovered at another address.
- Timeouts must have sane positive defaults and validation.

Recommended data model:

```python
class Settings(BaseModel):
    device_identifier: str
    device_name: str | None = None
    preferred_host: str | None = None
    scan_timeout_seconds: float = Field(default=5.0, gt=0)
    command_timeout_seconds: float = Field(default=10.0, gt=0)
```

---

## 7. Credential Storage and Pairing

Use the `pyatv` file storage mechanism so the application can reuse persistent pairing credentials, including credentials created by `atvremote`.

For v0.1, pairing remains outside the model-facing MCP interface.

Recommended first-run workflow:

```bash
atvremote wizard
```

Then:

```bash
agenai-appletv configure
```

`configure` must:

1. Load `pyatv` persistent storage.
2. Scan Apple TVs.
3. Show discovered devices that can be used with stored credentials.
4. Allow the user to select the target Apple TV.
5. Save its stable identifier.
6. Save its display name for diagnostics.
7. Save its current host as `preferred_host`.
8. Connect once to verify the stored credentials.
9. Display a concise capability summary.
10. Close the connection cleanly.

A later version may replace the `atvremote wizard` step with a custom pairing flow.

Pairing must not be exposed as an ordinary agent tool.

---

## 8. MCP Lifecycle

Use an MCP lifespan object for process-lifetime state.

Conceptual structure:

```python
@dataclass
class AppContext:
    controller: AppleTVController
```

Lifespan startup must:

1. Load application configuration.
2. Initialize `pyatv` persistent storage.
3. Create `ConnectionManager`.
4. Create `AppleTVController`.
5. Yield `AppContext`.

Lifespan shutdown must:

1. Close any active Apple TV connection.
2. Await connection cleanup where required.
3. Release process-owned resources.

### Lazy Connection Requirement

Do not require an Apple TV connection for MCP server startup.

```text
Apple TV offline
      ≠
MCP server unavailable
```

The first tool that requires the Apple TV asks the connection manager for a live connection.

This requirement prevents:

- MCP startup failures when the Apple TV is sleeping.
- MCP host failures after a network interruption.
- Tight coupling between process lifecycle and device availability.

---

## 9. Connection Manager

`ConnectionManager` owns all direct connection lifecycle use of:

```text
pyatv.scan
pyatv.connect
pyatv storage
```

Public interface:

```python
class ConnectionManager:
    async def get(self) -> AppleTV: ...
    async def reconnect(self) -> AppleTV: ...
    async def close(self) -> None: ...
    def invalidate(self) -> None: ...
```

Implementation may add private helpers such as:

```python
async def _discover_configured_device(...)
async def _connect(...)
async def _scan_preferred_host(...)
async def _scan_by_identifier(...)
```

### 9.1 Connection Algorithm

```text
get()
 │
 ├── healthy cached connection?
 │      └── return
 │
 ├── preferred_host available?
 │      ├── unicast scan
 │      └── identifier matches?
 │             └── connect
 │
 ├── multicast scan using stable identifier
 │      └── connect
 │
 ├── update preferred_host
 │
 └── cache connection
```

### 9.2 Concurrency

Only one connection establishment attempt may run at a time.

Use an async lock around:

- Discovery.
- Initial connection.
- Reconnection.

Commands that could interfere with one another must also be serialized through a controller command lock.

This is especially important for:

- Navigation.
- Repeated button presses.
- Volume steps.
- App launch followed immediately by navigation.

### 9.3 Connection Invalidation

A connection must be invalidated when:

- `pyatv` reports connection loss.
- A command fails because the connection is no longer usable.
- A reconnection is explicitly requested.
- Shutdown begins.

Invalidation must not delete persistent pairing credentials.

---

## 10. Reconnection and Retry Policy

Read operations may:

1. Detect a broken cached connection.
2. Reconnect.
3. Retry once.

Do not automatically replay a non-idempotent operation after an uncertain transport failure.

Example:

```text
right button sent
connection drops
```

The server may not know whether the Apple TV processed the button press.

It must not blindly send another `right`.

### Suggested Classification

Safe for one automatic retry after reconnect:

- Status.
- Capability inspection.
- App listing.
- Explicit absolute volume set.
- Explicit absolute seek.
- Power request when state can be verified.

Do not replay automatically:

- Navigation presses.
- Double taps.
- Holds.
- Relative volume steps.
- Previous/next.
- Play/pause toggle.
- Relative skips when execution is uncertain.

When a non-idempotent command fails after dispatch uncertainty, return a `ToolError` explaining that execution state is uncertain.

---

## 11. Controller Layer

`AppleTVController` is the only layer MCP handlers call.

Public conceptual interface:

```python
class AppleTVController:
    async def status(self) -> AppleTVStatus: ...
    async def capabilities(self) -> AppleTVCapabilities: ...
    async def list_apps(self, query: str | None = None) -> list[AppInfo]: ...
    async def power(self, state: PowerTarget) -> PowerResult: ...
    async def open_app(self, app: str) -> OpenAppResult: ...
    async def open_url(self, url: str) -> OpenUrlResult: ...
    async def press(self, button: RemoteButton, action: PressAction, count: int) -> PressResult: ...
    async def playback(self, action: PlaybackAction) -> PlaybackResult: ...
    async def seek(self, position_seconds: int) -> SeekResult: ...
    async def skip(self, direction: SkipDirection, seconds: float) -> SkipResult: ...
    async def set_text(self, text: str) -> TextResult: ...
    async def set_volume(self, percent: float) -> VolumeResult: ...
    async def adjust_volume(self, direction: VolumeDirection, steps: int) -> VolumeAdjustResult: ...
```

The controller owns:

- Feature gating.
- App resolution.
- `pyatv` method mapping.
- Operation serialization.
- Reconnect policy.
- Error translation.
- Status normalization.
- Capability normalization.

MCP handlers should be thin wrappers over controller methods.

---

## 12. MCP Server

Use:

```python
from mcp.server import MCPServer
```

Create an explicitly named and versioned server:

```python
mcp = MCPServer(
    "agenai-appletv",
    version="0.1.0",
    instructions=SERVER_INSTRUCTIONS,
    lifespan=app_lifespan,
)
```

Default transport:

```text
stdio
```

No ordinary application logging may be written to stdout while using stdio.

---

## 13. Server Instructions

The server should advertise instructions with these semantics:

> Control the configured Apple TV using semantic tools whenever possible.
>
> Prefer app launching, power, playback, seek, text, and volume tools over remote navigation.
>
> Remote button presses are blind and non-idempotent. The server cannot see the Apple TV screen or determine which UI element currently has focus.
>
> The app returned by status is the app associated with currently playing media. Do not interpret it as a guaranteed currently visible or foreground app.
>
> Use text entry only when an Apple TV text field is focused.
>
> Do not automatically repeat remote presses after an uncertain failure.

The implementation may adjust wording, but these behavioral constraints must remain.

---

## 14. MCP Tool Surface

All tools should use typed inputs and structured outputs.

### 14.1 `apple_tv_status`

Purpose: read current device and playback state.

Input:

```text
none
```

Output:

```python
class AppleTVStatus(BaseModel):
    connection: Literal["connected", "unreachable"]
    device: DeviceInfo
    power_state: Literal["on", "off", "unknown"] | None
    playback: PlaybackInfo | None
    media_app: AppInfo | None
    volume_percent: float | None
    keyboard_focus: Literal["focused", "unfocused", "unknown"] | None
```

`PlaybackInfo` should include when available:

```text
state
media_type
title
artist
album
genre
series_name
season_number
episode_number
position_seconds
duration_seconds
repeat
shuffle
content_identifier
itunes_store_identifier
```

Use the field name:

```text
media_app
```

Do not use:

```text
active_app
```

The metadata app represents the application associated with currently playing media and must not be treated as a guaranteed foreground-application signal.

Tool annotations:

```text
read_only_hint = true
open_world_hint = false
```

---

### 14.2 `apple_tv_capabilities`

Purpose: return the current availability of operations exposed by this MCP server.

Example:

```json
{
  "power_on": "available",
  "power_off": "available",
  "navigate_up": "available",
  "navigate_down": "available",
  "launch_app": "available",
  "play": "available",
  "pause": "unavailable",
  "seek": "available",
  "text_set": "unavailable",
  "volume_set": "available"
}
```

Return normalized MCP operation names, not raw `pyatv` feature enum names.

Tool annotations:

```text
read_only_hint = true
open_world_hint = false
```

---

### 14.3 `apple_tv_list_apps`

Purpose: return launchable applications.

Optional input:

```python
query: str | None = None
```

Filtering:

- Case-insensitive application-name matching.
- Case-insensitive bundle-ID matching.
- No fuzzy selection behavior.

Output:

```python
class AppInfo(BaseModel):
    name: str | None
    bundle_id: str
```

Tool annotations:

```text
read_only_hint = true
open_world_hint = false
```

---

### 14.4 `apple_tv_power`

Input:

```python
state: Literal["on", "off"]
```

Mapping:

```text
on  → atv.power.turn_on(...)
off → atv.power.turn_off(...)
```

Prefer waiting for an observed state transition when supported, bounded by the command timeout.

Output:

```python
class PowerResult(BaseModel):
    requested_state: Literal["on", "off"]
    power_state: Literal["on", "off", "unknown"]
```

Tool annotations:

```text
read_only_hint = false
destructive_hint = false
idempotent_hint = true
open_world_hint = false
```

---

### 14.5 `apple_tv_open_app`

Input:

```python
app: str
```

The input may be:

- Exact bundle identifier.
- Installed application name.

Resolution order:

1. Exact bundle identifier.
2. Case-insensitive exact application name.
3. If no exact match exists, fail.
4. Return close candidates in the error where useful.
5. If multiple exact normalized names remain, fail as ambiguous.
6. Never automatically execute a fuzzy match.

Execution:

```python
await atv.apps.launch_app(bundle_id)
```

Output:

```python
class OpenAppResult(BaseModel):
    name: str | None
    bundle_id: str
    launched: bool
```

---

### 14.6 `apple_tv_open_url`

Input:

```python
url: str
```

Execution:

```python
await atv.apps.launch_app(url)
```

Do not claim that arbitrary applications support arbitrary deep links.

A successful result means the launch request was accepted. It does not prove that a specific item is visible on screen.

Output:

```python
class OpenUrlResult(BaseModel):
    url: str
    accepted: bool
```

---

### 14.7 `apple_tv_press`

Input:

```python
button: Literal[
    "up",
    "down",
    "left",
    "right",
    "select",
    "back",
    "home",
]

action: Literal[
    "tap",
    "double_tap",
    "hold",
] = "tap"

count: int = Field(default=1, ge=1, le=10)
```

Mapping:

```text
back → pyatv remote_control.menu
```

Repeated presses execute sequentially under the controller command lock.

Do not automatically retry after an uncertain execution failure.

Output:

```python
class PressResult(BaseModel):
    button: RemoteButton
    action: PressAction
    count: int
    completed: int
```

Tool annotations:

```text
read_only_hint = false
destructive_hint = false
idempotent_hint = false
open_world_hint = false
```

---

### 14.8 `apple_tv_playback`

Input:

```python
action: Literal[
    "play",
    "pause",
    "toggle",
    "stop",
    "next",
    "previous",
]
```

Map directly to semantic playback operations.

Do not implement these actions through fake UI navigation.

Output:

```python
class PlaybackResult(BaseModel):
    action: PlaybackAction
    accepted: bool
```

`toggle` is non-idempotent and must not be automatically replayed after uncertain execution.

---

### 14.9 `apple_tv_seek`

Input:

```python
position_seconds: int = Field(ge=0)
```

Execution:

```python
await atv.remote_control.set_position(position_seconds)
```

Output:

```python
class SeekResult(BaseModel):
    requested_position_seconds: int
    accepted: bool
```

Tool annotations:

```text
idempotent_hint = true
```

---

### 14.10 `apple_tv_skip`

Input:

```python
direction: Literal["forward", "backward"]
seconds: float = Field(default=0, ge=0)
```

`seconds=0` means allow the device/application to choose its standard skip interval.

Output:

```python
class SkipResult(BaseModel):
    direction: SkipDirection
    requested_seconds: float
    accepted: bool
```

Relative skipping is not automatically retried after uncertain execution.

---

### 14.11 `apple_tv_set_text`

Input:

```python
text: str
```

Require the virtual keyboard feature.

Preferred implementation:

```python
await atv.keyboard.text_set(text)
```

An empty string is the standard operation for clearing the field.

Never log the submitted text at INFO level or above.

Output:

```python
class TextResult(BaseModel):
    characters: int
    accepted: bool
```

Tool annotations:

```text
idempotent_hint = true
```

---

### 14.12 `apple_tv_set_volume`

Input:

```python
percent: float = Field(ge=0, le=100)
```

Execution:

```python
await atv.audio.set_volume(percent)
```

Output:

```python
class VolumeResult(BaseModel):
    requested_percent: float
    volume_percent: float | None
```

Tool annotations:

```text
idempotent_hint = true
```

---

### 14.13 `apple_tv_adjust_volume`

Input:

```python
direction: Literal["up", "down"]
steps: int = Field(default=1, ge=1, le=10)
```

Execute `volume_up` or `volume_down` once per step.

Output:

```python
class VolumeAdjustResult(BaseModel):
    direction: VolumeDirection
    requested_steps: int
    completed_steps: int
    volume_percent: float | None
```

This tool is intentionally separate from `apple_tv_set_volume` because relative adjustment is non-idempotent.

---

## 15. Structured Result Models

Every MCP tool must return a typed Pydantic model unless the operation naturally returns a list of typed models.

Do not return freeform status strings when a stable structured shape can express the result.

Core model set should include:

```text
Settings
DeviceInfo
AppInfo
PlaybackInfo
AppleTVStatus
AppleTVCapabilities
PowerResult
OpenAppResult
OpenUrlResult
PressResult
PlaybackResult
SeekResult
SkipResult
TextResult
VolumeResult
VolumeAdjustResult
```

Use `Literal`, enums, `Field`, and optional fields deliberately so the generated MCP schemas constrain agent behavior.

---

## 16. Capability Mapping

Create one centralized mapping between MCP operations and `pyatv` feature flags.

Conceptually:

```python
FEATURE_MAP = {
    "power_on": FeatureName.TurnOn,
    "power_off": FeatureName.TurnOff,
    "launch_app": FeatureName.LaunchApp,
    "list_apps": FeatureName.AppList,
    "seek": FeatureName.SetPosition,
    "text_set": FeatureName.TextSet,
    "volume_set": FeatureName.SetVolume,
}
```

The exact enum names must be taken from `pyatv 0.18.0`.

Do not scatter raw `FeatureName` checks through MCP handlers.

The controller must expose normalized helper methods such as:

```python
async def require_feature(...)
async def feature_state(...)
async def normalized_capabilities(...)
```

---

## 17. Error Model

### 17.1 `ToolError`

Use `ToolError` when the model should understand and potentially recover from the problem.

Examples:

```text
Apple TV could not be reached.
Application "Netflox" was not found.
Pause is unavailable because nothing is currently playing.
Text input is unavailable because no text field is focused.
Volume control is not supported by this device.
The command timed out.
The connection failed after the button may have been delivered; the command was not retried.
```

### 17.2 `MCPError`

Use `MCPError` only when the request itself should be rejected at the protocol level.

Ordinary device failures are not protocol failures.

### 17.3 Unexpected Exceptions

Unexpected exceptions must:

1. Be logged with traceback.
2. Not leak credentials.
3. Not leak stored pairing data.
4. Reach the caller only through normal SDK sanitization.

### 17.4 Translation Boundary

Raw `pyatv` exceptions should generally not cross into MCP handlers.

The controller or connection manager should translate them into:

- Domain-specific internal exceptions, then `ToolError`; or
- `ToolError` directly where appropriate.

---

## 18. Logging

Use module loggers:

```python
logger = logging.getLogger(__name__)
```

Never use `print()` while serving MCP over stdio.

Recommended defaults:

```text
agenai_appletv_mcp    INFO
pyatv                 WARNING
```

Debug mode may enable additional `pyatv` diagnostics.

Normal logs must never contain:

- Pairing credentials.
- Passwords.
- Stored credential blobs.
- Full text entered through `apple_tv_set_text`.
- Raw persistent storage contents.

For text entry, log only metadata if necessary:

```text
Entered 17 characters into Apple TV keyboard field
```

not the text itself.

---

## 19. CLI

Initial commands:

```text
agenai-appletv configure
agenai-appletv doctor
agenai-appletv serve
```

### 19.1 `configure`

Responsibilities:

- Load `pyatv` storage.
- Discover devices.
- Select the target.
- Save stable identity.
- Save preferred host.
- Verify connection.
- Show concise capabilities.

### 19.2 `doctor`

Perform a non-destructive diagnostic.

Example:

```text
✓ Configuration loaded
✓ pyatv storage loaded
✓ Device discovered
✓ Stable identifier matched
✓ Connected
✓ Power state available
✓ App launching available
✓ Remote navigation available
✓ Playback control available
✓ Keyboard currently unavailable
✓ Volume control available
```

The command must exit non-zero when a required prerequisite fails.

### 19.3 `serve`

Starts the MCP server.

Default:

```text
stdio
```

The implementation may support an explicit transport option later, but v0.1 only needs stdio.

---

## 20. Testing Strategy

### 20.1 Model Tests

Test:

- Enum serialization.
- Output schemas.
- Input bounds.
- Optional fields.
- Configuration validation.

### 20.2 Connection Manager Unit Tests

Mock `pyatv` and test:

- Cached connection reuse.
- Preferred-host scan.
- Identifier verification.
- Fallback multicast discovery.
- Host update after rediscovery.
- Connection invalidation.
- Reconnection.
- Concurrent connection calls collapsing into one attempt.
- Clean shutdown.

### 20.3 Controller Unit Tests

Mock `pyatv` interfaces and test:

- Feature gating.
- App matching.
- Ambiguous app matching.
- No fuzzy auto-launch.
- Button mapping.
- Action mapping.
- Repeated presses.
- Command serialization.
- Status normalization.
- `media_app` semantics.
- Timeout handling.
- Safe retry classification.
- No retry for non-idempotent uncertain commands.
- Error translation.

### 20.4 MCP Contract Tests

Use the MCP SDK in-memory client.

Conceptually:

```python
async with Client(mcp, raise_exceptions=True) as client:
    ...
```

Test:

- Exact tool names.
- Tool descriptions.
- Input schemas.
- Input constraints.
- Output schemas.
- Tool annotations.
- Structured results.
- `ToolError` behavior.
- Invalid-input validation.
- No device connection required to start the server.

### 20.5 Live Device Integration Tests

Optional and disabled by default.

Enable explicitly:

```text
APPLE_TV_INTEGRATION_TESTS=1
```

Live-device tests must never be required for normal CI.

Potential live tests:

- Connect.
- Read status.
- Read capabilities.
- List apps.
- Verify power state.
- Perform one safe idempotent operation.
- Optionally exercise non-idempotent controls only in a manually invoked suite.

---

## 21. Code Quality Gates

Before a change is accepted:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

The repository should use strict-enough Pyright configuration to catch:

- Incorrect `pyatv` API usage.
- Missing `None` handling.
- Incorrect Pydantic return types.
- Async/sync mistakes.

CI should run all four gates.

Live Apple TV integration tests remain opt-in.

---

## 22. Explicit v0.1 Non-Goals

Do not implement in v0.1:

- Screen capture.
- Screen OCR.
- Detection of currently highlighted UI controls.
- General visual UI automation.
- Siri or voice-command emulation.
- Touchpad coordinate gestures.
- User-account switching.
- AirPlay output-device routing.
- Local-file streaming.
- Agent-managed pairing credentials.
- Multiple Apple TVs.
- Remote Internet exposure.
- OAuth.
- Streamable HTTP.
- Arbitrary command macros.
- Background automation rules.

These may be added later without changing the core semantic controller contract.

---

## 23. Known Perception Limitation

The agent does not see the Apple TV screen.

`pyatv` exposes useful device, media, application, keyboard, audio, and playback state, but it does not provide a general representation of:

```text
current screen
highlighted menu item
button labels
UI hierarchy
foreground application in every state
```

Therefore the agent must prefer semantic actions where available.

Do not make claims such as:

```text
"The Netflix button is highlighted."
"The Settings app is definitely foregrounded."
"The movie successfully started playing."
```

unless observable `pyatv` state actually supports the claim.

---

## 24. Future Extensions

### v0.2 — Shared Local Daemon

Add optional localhost Streamable HTTP:

```text
agenai-appletv serve --transport http
```

Purpose:

- Multiple local agents share one long-running connection.
- MCP client process restarts do not require rebuilding the device connection.

Default may remain stdio.

### v0.3 — Multiple Apple TVs

Introduce named profiles:

```text
living-room
bedroom
office
```

Only then should tools gain a target-device argument.

Do not burden v0.1 schemas with unused device parameters.

### v0.4 — Higher-Level Agent Actions

Potential composed tools:

```text
apple_tv_watch
apple_tv_search
apple_tv_sequence
```

These should compose the primitive controller methods rather than bypass them.

### Future — MCPB Distribution

If distributing beyond a personal development environment becomes useful, package the local MCP server and runtime as an MCP Bundle.

---

## 25. Acceptance Criteria

v0.1 is complete when all of the following are true:

1. The user pairs the Apple TV once and credentials persist across restarts.
2. The application identifies the configured device by stable identifier.
3. A changed IP address does not require re-pairing or manual reconfiguration.
4. The MCP server starts even while the Apple TV is unavailable.
5. The server can reconnect after Apple TV disconnect or restart.
6. `apple_tv_status` returns typed device and playback state.
7. `apple_tv_capabilities` returns normalized feature availability.
8. The agent can power the Apple TV on and off.
9. The agent can list installed/launchable applications.
10. The agent can launch an application by exact bundle ID or exact normalized name.
11. The agent can invoke deep links through `apple_tv_open_url`.
12. The agent can navigate using remote buttons.
13. The agent can control playback.
14. The agent can seek to an absolute playback position.
15. The agent can perform relative skip operations.
16. The agent can enter text when an Apple TV text field is available.
17. The agent can set absolute volume when supported.
18. The agent can adjust relative volume when supported.
19. Unsupported and temporarily unavailable features return useful `ToolError`s.
20. No credentials appear in MCP results or normal logs.
21. Entered keyboard text is not logged.
22. stdio remains clean of application stdout.
23. All MCP tools have typed inputs.
24. All MCP tools have structured outputs.
25. MCP contract tests run without physical Apple TV hardware.
26. Connection and controller tests run without physical Apple TV hardware.
27. Live integration tests are opt-in.
28. `doctor` validates a configured real Apple TV end-to-end.
29. Ruff passes.
30. Pyright passes.
31. Pytest passes.
32. `uv.lock` is committed and reproduces the intended stable dependency set.

---

## 26. Source-of-Truth Rules

Implementation decisions must follow this priority:

1. This `SPEC.md` for product and architectural intent.
2. The pinned `pyatv 0.18.0` reference corpus for `pyatv` behavior and exact APIs.
3. The pinned MCP Python SDK 2.2.0 reference corpus for MCP behavior and exact APIs.
4. The MCP 2026-07-28 specification where protocol behavior matters.
5. Tests in this repository.

If implementation reality conflicts with this specification because an upstream pinned API behaves differently, update the spec deliberately rather than silently working around it.

Do not copy examples from newer `pyatv` master, MCP v1, deprecated `FastMCP` tutorials, or unpinned web snippets without verifying them against the pinned references.
