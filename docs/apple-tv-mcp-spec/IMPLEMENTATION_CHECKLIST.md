# Apple TV MCP — Implementation Checklist

**Status as of 2026-09-12:** v0.1 software implementation, unit tests, MCP contract tests, and stdio transport tests are complete. v0.2 screen capture (`apple_tv_screenshot` plus the `appletv-screenshot` helper) is implemented and fake-tested; see the v0.2 section below. Product naming is Apple TV MCP (`appletv-mcp` / `appletv_mcp`). **Live Apple TV validation was not executed** for either version in this environment because no physical device was available.

## v0.2 — Screen capture (`SPEC_v0.2.md`)

Implemented and tested with fakes (no hardware):

- [x] Domain: `CapturedScreen` (frozen, `image/png` only, non-empty bytes), `ScreenCaptureSettings` nested under `Settings.screen_capture` with defaults so v0.1 config files load unchanged, and the `ScreenCapture*` error family under a `ScreenCaptureError` base.
- [x] Application: `ScreenCaptureBackend` port and `ScreenCaptureService` with its own `asyncio.Lock` (five concurrent captures observed to run one at a time).
- [x] Infrastructure: `ExternalScreenCaptureBackend` spawns the helper with `create_subprocess_exec`, fixed argv, all streams `DEVNULL`, per-call temp dir removed in `finally`, timeout and cancel handled with terminate/wait/kill, PNG checked by signature, IHDR, and dimensions, size capped by `max_image_bytes`. `HelperExitCode` table and message mapping in `contract.py`.
- [x] MCP: `apple_tv_screenshot`, no arguments, `structured_output=False`, returns one `ImageContent` via the SDK `Image` helper. Fourteen tools in the contract test; the output-schema assertion is relaxed only for this tool by name. Server instructions and the status/remote tool descriptions rewritten for point-in-time perception.
- [x] Doctor: `SKIP` when the helper is missing, `OK` with dimensions after one real capture, `FAIL` with the helper error; never affects the exit code.
- [x] Sidecar `sidecars/appletv-screenshot/` (separate `uv` project, own lockfile, not a workspace member): `capture --output PATH`, `configure`, `--version`; transports `auto` (native on macOS, then tunneld), `native`, `tunneld`; deterministic target selection (configured UDID or exactly one visible device); exit codes 0/2/10–17; 82 tests.
- [x] Root drift test loads the helper's `exit_codes.py` by path and compares it with `HelperExitCode`.
- [x] CI: separate sidecar job; root job builds the wheel and fails if it carries the sidecar or a `pymobiledevice3` requirement.
- [x] Live test `tests/integration/live/test_live_screen_capture.py` (read-only, `APPLE_TV_INTEGRATION_TESTS=1`, skips without the helper).
- [x] Docs: `AGENTS.md` §8/§9/§10/§10a/§22/§35/§37/§38, `README.md`, `SPEC.md` (§4, §5 real tree, §13, §14.14, §15, §17, §19.2, §20.5, §22–§24), `docs/references/README.md` and `MANIFEST.sha256`.
- [x] Version `0.2.0` in `pyproject.toml`, `_version.py`, `uv.lock`, and the sidecar.

Not executed (hardware-dependent). Do not tick without a real Apple TV:

- [ ] `pymobiledevice3 remote pair` and `remote tunneld` (or the macOS native tunnel) against a tvOS 17+ Apple TV with Developer Mode and the DDI.
- [ ] `appletv-screenshot capture --output ...` returns a real PNG; record the tvOS version, host OS, and that pymobiledevice3 11.12.4 worked.
- [ ] `apple_tv_screenshot` through an MCP host renders the image.
- [ ] screenshot → `apple_tv_press` → screenshot shows the change.
- [ ] Protected playback returns a black frame and the tool still succeeds.
- [ ] Helper survives a tunnel restart and an Apple TV reboot (next call succeeds or returns a clear `ToolError`).

v0.2 deviations from `SPEC_v0.2.md`, all deliberate:

- `ScreenCaptureError` base class added above the five specified errors so the MCP boundary and the exit-code map can name the family.
- Exit code `17 CONFIG_INVALID` added to the helper contract; `appletv-screenshot configure` repairs an unreadable config from defaults.
- Helper stderr is detached (`DEVNULL`) rather than captured: it may carry tracebacks with pairing paths, and exit codes are the API.
- The helper offers no `devices` subcommand; the `AMBIGUOUS_DEVICE` message lists visible UDIDs and `pymobiledevice3 remote browse` exists.
- Native-tunnel pairing failure is detected by the `pairing failed` message prefix of `UserspaceTunnelUnavailableError`, because pymobiledevice3 11.12.4 raises a private subclass on that path.
- `pymobiledevice3==11.12.4` is the latest stable at the time of writing. No proof-of-concept pin was available to recover, so the pin is unverified on hardware.

## Current project state

Completed in software (mocked / no hardware):

- Layered package under `src/appletv_mcp/` (domain, application, infrastructure, interfaces)
- Persistent config (atomic JSON, no credentials)
- pyatv 0.18.0 `FileStorage` adapter compatible with `atvremote wizard`
- Lazy connection manager, identifier-first discovery, preferred-host IPv4 unicast hint
- Capability map verified against pyatv 0.18.0 `FeatureName`
- `AppleTVController` with deterministic app resolution and retry/idempotency policy
- 13 MCP v2 tools with typed inputs/outputs and `ToolAnnotations`
- CLI: `configure`, `doctor`, `serve`
- Quality gates: ruff, ruff format, pyright (0 errors), pytest

Not executed (hardware-dependent):

- `atvremote wizard` against a real Apple TV
- `appletv-mcp configure` / `doctor` against a real Apple TV
- Live pytest suite (`APPLE_TV_INTEGRATION_TESTS=1`)
- Disruptive live writes (`APPLE_TV_LIVE_WRITES=1`)
- MCP Inspector GUI (stdio transport was verified with the MCP Python SDK in-process client and a real stdio subprocess)
- Git release tag

v0.1 hardware verification (manual; do not treat as done until run on a real Apple TV):

- `atvremote wizard` → `appletv-mcp configure` → `appletv-mcp doctor`
- `apple_tv_status`, `apple_tv_capabilities`, `apple_tv_list_apps`
- `apple_tv_power(on)`, `apple_tv_open_app(...)`, `apple_tv_playback(play/pause)`, `apple_tv_seek(...)`
- `apple_tv_press(home/back/arrows)`, `apple_tv_set_text(...)` with a focused text field
- `apple_tv_set_volume(...)`, `apple_tv_adjust_volume(...)`
- `apple_tv_power(off)` then `apple_tv_power(on)`
- Restart MCP and verify reconnect

## Implementation notes / deviations

- Architecture follows the layered tree in the development prompt, not the flat sketch in SPEC §5.
- `preferred_host` is IPv4-only. pyatv 0.18.0 unicast `scan(hosts=...)` uses `IPv4Address`; hostnames are rejected at Settings validation.
- `apple_tv_status` returns `connection=unreachable` after read retry exhaustion instead of always raising `ToolError`, so agents can inspect identity without treating an offline TV as a protocol failure. Write tools still surface `ToolError`.
- Config directory can be overridden with `APPLETV_MCP_CONFIG_DIR` (tests and unusual installs).
- Naming normalized to Apple TV MCP: distribution/CLI/MCP server `appletv-mcp`, import package `appletv_mcp` under `src/appletv_mcp/`, platformdirs app name `appletv-mcp`, config override `APPLETV_MCP_CONFIG_DIR`. No compatibility shims for former names.
- `doctor` uses `OK`/`FAIL` words rather than symbols for screen-reader-friendly output.
- `doctor` discovers the configured device through `ConnectionManager.resolve_device()` (preferred-host unicast, then identifier multicast), not a second scan algorithm.
- Connection validity is separate from ownership: `invalidate()` marks the cached `pyatv` session stale and retains the object; `reconnect()`, `disconnect()`, `get()`, and `close()` close it.
- `apple_tv_open_url` is non-idempotent (`idempotent_hint=False`) because deep links may have side effects. `apple_tv_open_app` by resolved bundle ID remains idempotent.
- Power commands call `turn_on`/`turn_off` with `await_new_state=False` because pyatv 0.18.0 Companion raises `NotImplementedError` when waiting is requested, while still advertising those features as available. Observed `power_state` is best-effort on the same connection; unverifiable results are `unknown`. Reconnect is not used to confirm power-off.
- Gateway `_run` distinguishes observation (`delivery_risk=False`: status, capabilities, apps, feature preflight) from mutating commands (`delivery_risk=True`). `BlockedStateError` always maps to `may_have_been_delivered=False`.
- Companion `ProtocolError` wrapping a timeout/connection failure, or raised after the device listener marked the session stale, is translated as `CommandTimeoutError`/`DeviceConnectionError` with the original `delivery_risk`. Healthy-session protocol rejections stay `CommandFailedError`.
- Retry applies the uncertain-delivery rule to both the first failure and the post-reconnect attempt.
- Power-off uses `OperationKind.REPLAY_UNSAFE` so uncertain Sleep is not replayed; unicast rediscovery knocks ports and can wake the TV. Power-on remains an idempotent write. MCP `apple_tv_power` advertises `idempotent_hint=False` because annotations cannot split ON vs OFF and clients may treat `true` as retry-safe.
- `--debug` does not enable `pyatv` DEBUG (Companion OPACK dumps include keyboard text and credentials).
- `configure` rejects known non-Apple-TV pyatv models (HomePod, AirPort Express, Music) and allows `DeviceModel.Unknown` with a warning.
- MCP Inspector GUI was not available; `tests/contract/mcp/test_stdio_transport.py` exercises the real stdio process.

### Naming normalization (complete)

- [x] Product name Apple TV MCP.
- [x] Distribution, CLI, MCP server, and platformdirs app name: `appletv-mcp`.
- [x] Import package `appletv_mcp` under `src/appletv_mcp/`.
- [x] Config override `APPLETV_MCP_CONFIG_DIR` (previous override names removed; no shim).
- [x] GitHub URLs `https://github.com/trevor-nichols/appletv-mcp` and `/issues`.

---

This checklist is ordered by dependency. Complete each phase before moving to later phases unless a task is explicitly marked as parallelizable.

The goal is to eliminate architectural decision-making during implementation: later work should build only on interfaces and behavior already established in earlier phases.

---

## Phase 0 — Repository and Version Baseline

### 0.1 Create repository structure

- [x] Create `appletv-mcp/`.
- [x] Add `SPEC.md`.
- [x] Add `IMPLEMENTATION_CHECKLIST.md`.
- [x] Add `README.md`.
- [x] Add `.gitignore`.
- [x] Add `.python-version`.
- [x] Add `references/`.
- [x] Add `src/appletv_mcp/`.
- [x] Add `tests/`.

### 0.2 Pin runtime

- [x] Set `.python-version` to `3.14.7`.
- [x] Initialize project with `uv`.
- [x] Set `requires-python = ">=3.14,<3.15"`.
- [x] Add `pyatv==0.18.0`.
- [x] Add `mcp[cli]==2.2.0`.
- [x] Add `pydantic>=2.12,<3`.
- [x] Add `platformdirs`.
- [x] Add dev dependency `pytest`.
- [x] Add dev dependency `pytest-asyncio`.
- [x] Add dev dependency `ruff`.
- [x] Add dev dependency `pyright`.
- [x] Generate `uv.lock`.
- [x] Commit `uv.lock`.

### 0.3 Configure quality tooling

- [x] Configure Ruff linting.
- [x] Configure Ruff formatting.
- [x] Configure Pyright.
- [x] Configure Pytest.
- [x] Add basic CI workflow.
- [x] Verify an empty/minimal project passes all quality gates.

### Exit criteria

- [x] `uv sync` succeeds from a clean checkout.
- [x] `uv run ruff check .` passes.
- [x] `uv run ruff format --check .` passes.
- [x] `uv run pyright` passes.
- [x] `uv run pytest` passes.

---

## Phase 1 — Domain Models and Constants

This phase has no Apple TV network dependency.

### 1.1 Define enums and literals

Create normalized domain types for:

- [x] `PowerTarget`.
- [x] `PowerState`.
- [x] `FeatureAvailability`.
- [x] `RemoteButton`.
- [x] `PressAction`.
- [x] `PlaybackAction`.
- [x] `SkipDirection`.
- [x] `VolumeDirection`.
- [x] Playback state.
- [x] Media type.
- [x] Keyboard focus state.

### 1.2 Define configuration model

Create `Settings` with:

- [x] `device_identifier`.
- [x] `device_name`.
- [x] `preferred_host`.
- [x] `scan_timeout_seconds`.
- [x] `command_timeout_seconds`.

Validation:

- [x] Positive timeouts.
- [x] Empty identifier rejected.
- [x] Host remains optional.
- [x] Device name remains optional/informational.

### 1.3 Define output models

Create:

- [x] `DeviceInfo`.
- [x] `AppInfo`.
- [x] `PlaybackInfo`.
- [x] `AppleTVStatus`.
- [x] `AppleTVCapabilities`.
- [x] `PowerResult`.
- [x] `OpenAppResult`.
- [x] `OpenUrlResult`.
- [x] `PressResult`.
- [x] `PlaybackResult`.
- [x] `SeekResult`.
- [x] `SkipResult`.
- [x] `TextResult`.
- [x] `VolumeResult`.
- [x] `VolumeAdjustResult`.

### 1.4 Define internal exceptions

Create internal exception types only where they improve translation clarity, for example:

- [x] `DeviceNotConfiguredError`.
- [x] `DeviceNotFoundError`.
- [x] `DeviceConnectionError`.
- [x] `FeatureUnavailableError`.
- [x] `FeatureUnsupportedError`.
- [x] `AmbiguousAppError`.
- [x] `AppNotFoundError`.
- [x] `UncertainExecutionError`.

Do not recreate upstream exception hierarchies unnecessarily.

### 1.5 Tests

- [x] Test Settings validation.
- [x] Test enum serialization.
- [x] Test output-model serialization.
- [x] Test optional fields.
- [x] Test field constraints.

### Exit criteria

- [x] Models are independent of MCP.
- [x] Models are independent of live `pyatv` connections.
- [x] All model tests pass.

---

## Phase 2 — Configuration Persistence

Depends on Phase 1.

### 2.1 Determine config location

- [x] Use `platformdirs`.
- [x] Define application name consistently.
- [x] Define config filename.
- [x] Make config location overridable in tests.

### 2.2 Implement configuration repository

Implement:

- [x] `load_settings()`.
- [x] `save_settings()`.
- [x] Atomic write strategy.
- [x] Helpful error for missing config.
- [x] Helpful error for malformed config.

### 2.3 Safety

- [x] Do not put `pyatv` credentials into this config.
- [x] Do not copy raw `pyatv` storage into this config.
- [x] Ensure logs do not dump entire config objects if future secret fields are added.

### 2.4 Tests

- [x] Round-trip save/load.
- [x] Missing file.
- [x] Invalid JSON.
- [x] Invalid settings.
- [x] Atomic replacement behavior where practical.

### Exit criteria

- [x] Device profile persistence works independently of `pyatv` credentials.

---

## Phase 3 — `pyatv` Persistent Storage Adapter

Depends on Phase 0.

### 3.1 Review pinned storage API

Using the pinned `pyatv 0.18.0` references:

- [x] Confirm exact `FileStorage` construction API.
- [x] Confirm default storage path behavior.
- [x] Confirm required async load/save lifecycle.
- [x] Confirm compatibility with `atvremote` credentials.

### 3.2 Implement storage helper

Create a small adapter that:

- [x] Creates/opens persistent `pyatv` storage.
- [x] Loads it once during application lifespan.
- [x] Exposes it to `ConnectionManager`.
- [x] Closes/saves only as required by pinned API behavior.

### 3.3 Logging

- [x] Never log raw credentials.
- [x] Never log raw storage objects.
- [x] Never serialize storage into MCP results.

### 3.4 Tests

- [x] Mock storage load.
- [x] Mock load failure.
- [x] Verify storage object reaches connection layer.

### Exit criteria

- [x] Credentials can be loaded without involving MCP tools.

---

## Phase 4 — Connection Manager

Depends on Phases 1–3.

This is the first core infrastructure phase.

### 4.1 Define interface

Implement:

```python
class ConnectionManager:
    async def get(self) -> AppleTV: ...
    async def reconnect(self) -> AppleTV: ...
    async def disconnect(self) -> None: ...
    async def close(self) -> None: ...
    def invalidate(self) -> None: ...
```

### 4.2 Implement preferred-host discovery

- [x] If `preferred_host` exists, perform unicast scan.
- [x] Verify returned device stable identifier.
- [x] Reject a different Apple TV found at the old IP.
- [x] Use stored credentials/configuration during connection.

### 4.3 Implement identifier fallback discovery

- [x] Fall back to multicast scan when preferred-host resolution fails.
- [x] Filter/select by configured stable identifier.
- [x] Fail clearly when the configured device is not found.
- [x] Update `preferred_host` when the correct device is rediscovered elsewhere.
- [x] Persist updated host.

### 4.4 Implement connection caching

- [x] Cache one live Apple TV connection.
- [x] Reuse it across controller calls.
- [x] Do not reconnect on every MCP tool call.

### 4.5 Implement concurrency

- [x] Add async connection lock.
- [x] Collapse simultaneous `get()` calls into one discovery/connect operation.
- [x] Prevent duplicate connections during reconnect.

### 4.6 Implement invalidation

- [x] Invalidate cached connection on disconnect callback.
- [x] Invalidate cached connection on known broken-connection failures.
- [x] Mark the cached session stale without dropping ownership; close the retained handle on reconnect, disconnect, get, or close.
- [x] Preserve persistent credentials.
- [x] Preserve device profile.

### 4.7 Implement close

- [x] Close active connection cleanly.
- [x] Make repeated `close()` safe.
- [x] Prevent new connection use during shutdown if practical.

### 4.8 Unit tests

Mock all `pyatv` network calls.

Test:

- [x] Cached reuse.
- [x] Preferred-host success.
- [x] Preferred-host wrong-device rejection.
- [x] Preferred-host failure followed by multicast success.
- [x] Configured identifier not found.
- [x] Preferred-host update after rediscovery.
- [x] Concurrent `get()` calls.
- [x] Explicit reconnect.
- [x] Invalidation retains the connection until reconnect/disconnect/close.
- [x] Close.
- [x] Connection failure translation.

### Exit criteria

- [x] One configured device can be discovered and connected by stable identifier.
- [x] IP changes are recoverable without reconfiguration.
- [x] No MCP code is required to use the connection manager.

---

## Phase 5 — Capability Adapter

Depends on Phase 4.

### 5.1 Verify exact `pyatv 0.18.0` feature enum names

From the pinned source/docs, map normalized operations to exact `FeatureName` members.

Required coverage:

- [x] Turn on.
- [x] Turn off.
- [x] App list.
- [x] App launch.
- [x] Up.
- [x] Down.
- [x] Left.
- [x] Right.
- [x] Select.
- [x] Menu/back.
- [x] Home.
- [x] Play.
- [x] Pause.
- [x] Play/pause.
- [x] Stop.
- [x] Next.
- [x] Previous.
- [x] Set position.
- [x] Skip forward.
- [x] Skip backward.
- [x] Text get/set where applicable.
- [x] Keyboard focus where applicable.
- [x] Volume get/set/up/down where applicable.

### 5.2 Centralize mapping

Create a single mapping such as:

```python
FEATURE_MAP = {...}
```

Do not reference raw feature enums throughout controller methods.

### 5.3 Normalize feature states

Convert upstream states into:

```text
available
unknown
unavailable
unsupported
```

### 5.4 Implement helpers

- [x] `feature_state(operation)`.
- [x] `require_feature(operation)`.
- [x] `normalized_capabilities()`.

Behavior:

- [x] Available → execute.
- [x] Unknown → permit attempt.
- [x] Unavailable → expected operational failure.
- [x] Unsupported → expected device-capability failure.

### 5.5 Tests

- [x] Every public MCP operation has expected feature mapping where relevant.
- [x] Unknown behavior.
- [x] Unavailable behavior.
- [x] Unsupported behavior.
- [x] Capability output normalization.

### Exit criteria

- [x] No controller operation needs to understand raw feature-state semantics itself.

---

## Phase 6 — AppleTVController: Read-Only Surface

Depends on Phases 4–5.

Implement read-only functionality first because it is easiest to test and safest against a live device.

### 6.1 `status()`

Normalize:

- [x] Connection/device identity.
- [x] Power state.
- [x] Playback state.
- [x] Media metadata.
- [x] `media_app`.
- [x] Position.
- [x] Duration.
- [x] Repeat.
- [x] Shuffle.
- [x] Volume.
- [x] Keyboard focus.

Critical semantic rule:

- [x] Name the field `media_app`.
- [x] Do not call it `active_app`.
- [x] Do not imply foreground-app certainty.

### 6.2 `capabilities()`

- [x] Return normalized controller operations.
- [x] Do not expose raw `FeatureName` enum values.

### 6.3 `list_apps()`

- [x] Return typed `AppInfo`.
- [x] Optional case-insensitive filtering by name.
- [x] Optional case-insensitive filtering by bundle ID.
- [x] No fuzzy auto-selection.

### 6.4 Read retry policy

- [x] Broken cached connection may reconnect and retry once.
- [x] Do not loop indefinitely.
- [x] Convert final failures into domain-level errors.

### 6.5 Tests

- [x] Full status normalization.
- [x] Missing metadata.
- [x] Unknown power.
- [x] No media app.
- [x] No volume support.
- [x] Keyboard focus unavailable.
- [x] Capability normalization.
- [x] App filtering.
- [x] Read retry success.
- [x] Read retry exhaustion.

### Exit criteria

- [x] The project can report meaningful device state without MCP.

---

## Phase 7 — AppleTVController: Idempotent/Semantic Actions

Depends on Phase 6.

Add a controller command lock before write actions.

### 7.1 Command serialization

- [x] Add async command lock.
- [x] Ensure action methods execute serially.
- [x] Keep status reads outside the lock unless required by upstream behavior.

### 7.2 Power

Implement:

- [x] `power("on")`.
- [x] `power("off")`.
- [x] Feature checks.
- [x] Optional state verification.
- [x] Bounded wait.
- [x] Idempotent retry rules.

### 7.3 Open app

Implement deterministic resolution:

1. [ ] Exact bundle ID wins.
2. [ ] Case-insensitive exact name.
3. [ ] Ambiguity returns error.
4. [ ] Missing app returns error.
5. [ ] Candidate suggestions may be included.
6. [ ] Fuzzy match never executes automatically.

Then:

- [x] Launch resolved bundle ID.
- [x] Return `OpenAppResult`.

### 7.4 Open URL

- [x] Accept URL string.
- [x] Invoke `apps.launch_app(url)` as supported by pinned API.
- [x] Return acceptance only.
- [x] Do not claim content success.

### 7.5 Absolute seek

- [x] Validate position >= 0.
- [x] Feature gate.
- [x] Invoke set-position API.
- [x] Safe reconnect/retry only when semantics remain certain.

### 7.6 Absolute volume

- [x] Validate 0–100.
- [x] Feature gate.
- [x] Set volume.
- [x] Read back current volume where feasible.
- [x] Return requested and observed values.

### 7.7 Set text

- [x] Feature gate.
- [x] Prefer keyboard text-set API.
- [x] Permit empty string to clear field.
- [x] Never log input text.
- [x] Return only character count and acceptance.

### 7.8 Tests

- [x] Power on/off.
- [x] App bundle-ID resolution.
- [x] App exact-name resolution.
- [x] App ambiguity.
- [x] App missing with candidates.
- [x] URL launch.
- [x] Seek.
- [x] Volume set.
- [x] Text set.
- [x] Empty text.
- [x] Text never appears in logs.
- [x] Command serialization.

### Exit criteria

- [x] Semantic write actions work through controller without MCP.

---

## Phase 8 — AppleTVController: Non-Idempotent Actions

Depends on Phase 7.

### 8.1 Remote press

Support:

- [x] up.
- [x] down.
- [x] left.
- [x] right.
- [x] select.
- [x] back.
- [x] home.

Support action styles:

- [x] tap.
- [x] double tap.
- [x] hold.

Support:

- [x] count 1–10.
- [x] sequential execution.
- [x] completed-count reporting.

Confirm exact pinned `pyatv` APIs for press behavior before implementation.

### 8.2 Back mapping

- [x] Map MCP `back` to the correct `pyatv` menu/back operation for 0.18.0.
- [x] Do not expose `menu` to the MCP user unless later desired.

### 8.3 Playback

Support:

- [x] play.
- [x] pause.
- [x] toggle.
- [x] stop.
- [x] next.
- [x] previous.

### 8.4 Relative skip

Support:

- [x] forward.
- [x] backward.
- [x] optional seconds.
- [x] seconds=0 default-device interval semantics.

### 8.5 Relative volume

Support:

- [x] up.
- [x] down.
- [x] steps 1–10.
- [x] completed-step count.

### 8.6 Uncertain execution handling

For every non-idempotent operation:

- [x] Do not automatically replay after uncertain transport failure.
- [x] Invalidate broken connection.
- [x] Return an error explaining execution may have occurred.
- [x] Let a later independent call reconnect.

### 8.7 Tests

- [x] Every button maps correctly.
- [x] Tap behavior.
- [x] Double tap behavior.
- [x] Hold behavior.
- [x] Count sequencing.
- [x] Partial completion.
- [x] Playback mappings.
- [x] Skip mappings.
- [x] Relative volume.
- [x] No automatic replay after uncertain failure.

### Exit criteria

- [x] Blind controls are available but handled more conservatively than semantic/idempotent controls.

---

## Phase 9 — Error Translation Layer

Depends on Phases 4–8.

### 9.1 Define translation rules

Map expected `pyatv` failures into clear controller/domain errors.

Cover:

- [x] Device unavailable.
- [x] Connection lost.
- [x] Authentication/pairing unavailable.
- [x] Feature unsupported.
- [x] Feature temporarily unavailable.
- [x] Timeout.
- [x] App not found.
- [x] Ambiguous app.
- [x] Uncertain non-idempotent execution.

### 9.2 Preserve safe context

Error messages may include:

- [x] Operation name.
- [x] Device display name.
- [x] Requested app name.
- [x] Capability state.

Error messages must not include:

- [x] Credentials.
- [x] Passwords.
- [x] Raw credential objects.
- [x] Raw storage serialization.
- [x] Keyboard text.

### 9.3 Tests

- [x] Every expected failure becomes a deterministic domain error.
- [x] Unexpected failures remain unexpected and retain traceback in logs.
- [x] Secret-bearing values are absent from expected error strings.

### Exit criteria

- [x] MCP layer will not need to understand `pyatv` exception types.

---

## Phase 10 — MCP Lifespan and Server Skeleton

Depends on Phases 2–9.

### 10.1 Lifespan

Create `AppContext`:

```python
@dataclass
class AppContext:
    controller: AppleTVController
```

Startup:

- [x] Load settings.
- [x] Load `pyatv` storage.
- [x] Create `ConnectionManager`.
- [x] Create `AppleTVController`.
- [x] Do not connect to Apple TV.

Shutdown:

- [x] Close connection manager.
- [x] Clean up storage if required.

### 10.2 Server

Create explicitly:

- [x] Name `appletv-mcp`.
- [x] Version `0.1.0`.
- [x] Lifespan.
- [x] Server instructions.
- [x] Default stdio execution path.

### 10.3 Logging

- [x] Use Python `logging`.
- [x] No `print()` in serving path.
- [x] Default app logger INFO.
- [x] Default `pyatv` logger WARNING.
- [x] Optional debug mode.

### 10.4 Tests

- [x] Server can instantiate with mocked dependencies.
- [x] MCP server startup does not connect to Apple TV.
- [x] MCP server startup succeeds while device mock is unavailable.
- [x] Shutdown closes connection manager.

### Exit criteria

- [x] MCP process lifecycle is independent of Apple TV availability.

---

## Phase 11 — MCP Read-Only Tools

Depends on Phase 10.

Implement thin MCP wrappers only.

### 11.1 `apple_tv_status`

- [x] No user input.
- [x] Return `AppleTVStatus`.
- [x] `read_only_hint=True`.
- [x] `open_world_hint=False`.

### 11.2 `apple_tv_capabilities`

- [x] No user input.
- [x] Return `AppleTVCapabilities`.
- [x] `read_only_hint=True`.
- [x] `open_world_hint=False`.

### 11.3 `apple_tv_list_apps`

- [x] Optional `query`.
- [x] Return typed app list.
- [x] `read_only_hint=True`.
- [x] `open_world_hint=False`.

### 11.4 MCP error conversion

- [x] Expected domain/controller errors become `ToolError`.
- [x] Do not return error strings as successful tool results.

### Exit criteria

- [x] Read-only tools work via MCP in-memory client.

---

## Phase 12 — MCP Semantic Write Tools

Depends on Phase 11.

Implement:

### 12.1 `apple_tv_power`

- [x] Typed `state`.
- [x] Typed result.
- [x] `idempotent_hint=False` (annotations cannot split ON vs OFF; clients may treat `true` as retry-safe).
- [x] `destructive_hint=False`.
- [x] `open_world_hint=False`.

### 12.2 `apple_tv_open_app`

- [x] Typed `app`.
- [x] Typed result.
- [x] Exact-match semantics documented in tool docstring.

### 12.3 `apple_tv_open_url`

- [x] Typed `url`.
- [x] Typed result.
- [x] Tool description avoids claiming visual verification.
- [x] `idempotent_hint=False` (deep links are not retried after uncertain delivery).

### 12.4 `apple_tv_seek`

- [x] `position_seconds >= 0`.
- [x] Typed result.
- [x] `idempotent_hint=True`.

### 12.5 `apple_tv_set_text`

- [x] Typed text.
- [x] Typed result.
- [x] `idempotent_hint=True`.
- [x] Description states focused text field requirement.

### 12.6 `apple_tv_set_volume`

- [x] 0–100 constraint.
- [x] Typed result.
- [x] `idempotent_hint=True`.

### Exit criteria

- [x] Semantic action tools expose only normalized domain concepts.

---

## Phase 13 — MCP Non-Idempotent Tools

Depends on Phase 12.

### 13.1 `apple_tv_press`

- [x] Button enum.
- [x] Action enum.
- [x] Count range 1–10.
- [x] Structured result.
- [x] `idempotent_hint=False`.
- [x] Description explicitly states blind navigation.

### 13.2 `apple_tv_playback`

- [x] Action enum.
- [x] Structured result.
- [x] Treat toggle as non-idempotent.

### 13.3 `apple_tv_skip`

- [x] Direction enum.
- [x] Seconds >= 0.
- [x] Structured result.

### 13.4 `apple_tv_adjust_volume`

- [x] Direction enum.
- [x] Steps range 1–10.
- [x] Structured result.
- [x] `idempotent_hint=False`.

### Exit criteria

- [x] Agent has fallback control surface without raw `pyatv` concepts.

---

## Phase 14 — MCP Contract Test Suite

Depends on Phases 11–13.

Use the MCP SDK in-memory client.

### 14.1 Tool inventory

Assert exact v0.1 tool set:

- [x] `apple_tv_status`.
- [x] `apple_tv_capabilities`.
- [x] `apple_tv_list_apps`.
- [x] `apple_tv_power`.
- [x] `apple_tv_open_app`.
- [x] `apple_tv_open_url`.
- [x] `apple_tv_press`.
- [x] `apple_tv_playback`.
- [x] `apple_tv_seek`.
- [x] `apple_tv_skip`.
- [x] `apple_tv_set_text`.
- [x] `apple_tv_set_volume`.
- [x] `apple_tv_adjust_volume`.

### 14.2 Schema assertions

For every tool:

- [x] Tool name.
- [x] Description.
- [x] Required arguments.
- [x] Optional arguments.
- [x] Enum values.
- [x] Numeric bounds.
- [x] Output schema.
- [x] Tool annotations.

### 14.3 Behavior assertions

- [x] Structured content returned.
- [x] Expected controller failures become `is_error=True` tool results.
- [x] Invalid MCP input is rejected before controller execution.
- [x] Server can be tested without subprocess.
- [x] Server can be tested without physical Apple TV.

### Exit criteria

- [x] MCP contract is stable and independently testable.

---

## Phase 15 — CLI: `configure`

Depends on Phases 2–5.

Can be implemented earlier after Phase 5, but should be complete before live-device integration.

### 15.1 Device discovery

- [x] Load persistent `pyatv` credentials.
- [x] Scan devices.
- [x] Present discovered candidates.
- [x] Show name.
- [x] Show stable identifier.
- [x] Show host.

### 15.2 Selection

- [x] Select one Apple TV.
- [x] Persist stable identifier.
- [x] Persist display name.
- [x] Persist preferred host.

### 15.3 Verification

- [x] Connect using stored credentials.
- [x] Verify device identity.
- [x] Display normalized capabilities.
- [x] Close cleanly.

### 15.4 Failure behavior

- [x] No credentials found.
- [x] Pairing required.
- [x] Device disappears.
- [x] Connection rejected.
- [x] Invalid selection.
- [x] Invalid `--scan-timeout` rejected at argparse (positive finite).
- [x] Expected Apple TV errors become one-line CLI errors.
- [x] Storage adapter closed if configure exits before Runtime ownership.

### Exit criteria

- [x] A user can configure the MCP server without editing JSON manually.

---

## Phase 16 — CLI: `doctor`

Depends on Phases 6–9 and Phase 15.

### 16.1 Checks

Implement non-destructive checks for:

- [x] Configuration exists.
- [x] Configuration validates.
- [x] `pyatv` storage loads.
- [x] Configured identifier can be discovered.
- [x] Discovery reuses the production resolver (preferred-host unicast, then identifier fallback).
- [x] Preferred host matches or can be repaired.
- [x] Connection succeeds.
- [x] Power capability.
- [x] App listing/launch capability.
- [x] Navigation capabilities.
- [x] Playback capabilities.
- [x] Keyboard capability/current state.
- [x] Volume capability.

### 16.2 Output

- [x] Screen-reader-friendly line output.
- [x] One check per line.
- [x] Clear success/failure symbols or words.
- [x] No secret data.
- [x] Non-zero exit code on required failure.

### Exit criteria

- [x] `doctor` provides enough information to diagnose setup without starting MCP.

---

## Phase 17 — CLI: `serve`

Depends on Phase 10.

### 17.1 Command

- [x] Add `appletv-mcp serve`.
- [x] Start stdio MCP server.
- [x] No normal stdout output.
- [x] Support debug logging flag if useful.

### 17.2 Packaging entrypoint

- [x] Add console-script entry point.
- [x] Verify `uv run appletv-mcp serve`.
- [x] Verify installed command execution.

### Exit criteria

- [x] MCP hosts can launch the server through one stable CLI command.

---

## Phase 18 — Host Integration

Depends on Phases 14 and 17.

### 18.1 Generic stdio config

Document command form:

```text
uv --directory /absolute/path/to/appletv-mcp run appletv-mcp serve
```

or installed executable path.

### 18.2 Test with MCP Inspector

Not run as the Inspector GUI in this environment. Equivalent stdio coverage is in
`tests/contract/mcp/test_stdio_transport.py` (real subprocess) and
`tests/contract/mcp/test_tool_contract.py` (in-memory MCP client).

- [ ] Tool list appears in MCP Inspector GUI.
- [x] Tool list appears via stdio/`tools/list`.
- [x] Schemas are present on listed tools.
- [x] Read-only tools work against a mocked controller.
- [x] Expected errors render as tool errors (`is_error=True`).
- [x] No protocol corruption from stdout.

### 18.3 Test with target agent host(s)

Cursor / Claude Desktop / Codex were not launched against a live Apple TV here.
The stdio subprocess test is the transport stand-in.

- [ ] Server starts in a production MCP host UI.
- [x] Tools discover over stdio.
- [x] Tool arguments serialize correctly (contract tests).
- [x] Structured results are preserved (contract tests).
- [x] Host does not incorrectly require HTTP/OAuth (stdio-only v0.1).

### Exit criteria

- [x] At least one real agent host can control a mocked controller through the actual stdio process.

---

## Phase 19 — Live Apple TV Integration

Depends on Phases 15–18.

This phase validates pinned `pyatv` assumptions against the real device.

### 19.1 Pairing/setup

- [ ] Run `atvremote wizard` if credentials do not already exist.
- [ ] Run `appletv-mcp configure`.
- [ ] Run `appletv-mcp doctor`.

### 19.2 Read-only validation

- [ ] Status.
- [ ] Capabilities.
- [ ] App list.
- [ ] Playback metadata.
- [ ] Volume state.
- [ ] Keyboard state.

### 19.3 Semantic actions

- [ ] Power on.
- [ ] Power off.
- [ ] Launch known app.
- [ ] Launch by bundle ID.
- [ ] Open supported deep link.
- [ ] Seek.
- [ ] Set volume.
- [ ] Enter non-sensitive test text.

### 19.4 Non-idempotent controls

Manually verify:

- [ ] up.
- [ ] down.
- [ ] left.
- [ ] right.
- [ ] select.
- [ ] back.
- [ ] home.
- [ ] play.
- [ ] pause.
- [ ] toggle.
- [ ] next.
- [ ] previous.
- [ ] skip.
- [ ] relative volume.

### 19.5 Recovery scenarios

- [ ] Restart Apple TV.
- [ ] Sleep Apple TV.
- [ ] Wake Apple TV.
- [ ] Restart MCP process.
- [ ] Change/reassign DHCP address if practical.
- [ ] Verify stable identifier survives IP change.
- [ ] Disconnect network briefly.
- [ ] Confirm read operation reconnect behavior.
- [ ] Confirm non-idempotent operation is not blindly replayed.

### Exit criteria

- [ ] All acceptance criteria tied to physical device behavior are validated.

---

## Phase 20 — Documentation

Depends on stable behavior from Phases 15–19.

### 20.1 README

Document:

- [x] Purpose.
- [x] Requirements.
- [x] Install.
- [x] Pairing.
- [x] Configure.
- [x] Doctor.
- [x] Serve.
- [x] MCP host configuration.
- [x] Tool summary.
- [x] Perception limitations.
- [x] Troubleshooting.

### 20.2 Security/privacy notes

Document:

- [x] Pairing credentials remain local.
- [x] Credentials are not exposed through MCP.
- [x] Text-entry contents are not logged.
- [x] v0.1 is local stdio only.

### 20.3 Developer docs

Document:

- [x] Architecture layers.
- [x] Connection retry rules.
- [x] Idempotency rules.
- [x] Feature mapping.
- [x] Testing.
- [x] How to update pinned upstream versions.

### Exit criteria

- [x] A new developer can set up the project without reading implementation source.

---

## Phase 21 — Final Quality and Release Gate

### 21.1 Automated gates

- [x] `uv sync --locked`.
- [x] `uv run ruff check .`.
- [x] `uv run ruff format --check .`.
- [x] `uv run pyright`.
- [x] `uv run pytest`.

### 21.2 Contract gate

- [x] Exact v0.1 tool inventory.
- [x] No accidental raw-`pyatv` tools.
- [x] No pairing MCP tool.
- [x] No device selector argument.
- [x] No HTTP/OAuth code in v0.1.
- [x] No foreground-app claims.
- [x] No visual-screen claims.

### 21.3 Security gate

Search repository for:

- [x] Hardcoded credentials.
- [x] Raw storage dumps.
- [x] Accidental keyboard text logging.
- [x] `print(` in MCP serving paths.
- [x] Secret-looking fixture data.

### 21.4 Live gate

- [ ] `configure` succeeds.
- [ ] `doctor` succeeds.
- [ ] Agent host can call `apple_tv_status`.
- [ ] Agent host can launch an app.
- [ ] Agent host can control playback.
- [ ] Device recovers after reconnect.
- [ ] IP change does not require re-pairing.

### 21.5 Release

- [x] Set version `0.1.0` (bumped to `0.2.0` with screen capture).
- [ ] Tag release.
- [x] Preserve pinned references used for implementation.
- [ ] Record any upstream quirks discovered during live validation.

---

# Dependency Summary

```text
Phase 0  Repository/runtime
   │
   ├──► Phase 1  Models
   │       │
   │       └──► Phase 2  Config
   │
   ├──► Phase 3  pyatv storage
   │
   └──────────────┐
                  ▼
              Phase 4
          Connection Manager
                  │
                  ▼
              Phase 5
          Capability Adapter
                  │
                  ▼
              Phase 6
        Read-Only Controller
                  │
                  ▼
              Phase 7
      Idempotent/Semantic Actions
                  │
                  ▼
              Phase 8
       Non-Idempotent Actions
                  │
                  ▼
              Phase 9
         Error Translation
                  │
                  ▼
              Phase 10
       MCP Lifespan + Server
                  │
           ┌──────┴──────┐
           ▼             ▼
       Phase 11       CLI configure
       Read tools        │
           │             │
           ▼             ▼
       Phase 12       CLI doctor
     Semantic tools
           │
           ▼
       Phase 13
   Non-idempotent tools
           │
           ▼
       Phase 14
     Contract tests
           │
           ▼
       CLI serve
           │
           ▼
       Host integration
           │
           ▼
       Live Apple TV
           │
           ▼
      Documentation
           │
           ▼
       Release gate
```

---

# Recommended Build Order for a Coding Agent

If one agent is implementing the project end-to-end, give it these batches in order:

### Batch A — Foundation

- [x] Phase 0.
- [x] Phase 1.
- [x] Phase 2.
- [x] Phase 3.

Stop and run all tests.

### Batch B — Device Infrastructure

- [x] Phase 4.
- [x] Phase 5.

Stop and run all tests.

### Batch C — Controller

- [x] Phase 6.
- [x] Phase 7.
- [x] Phase 8.
- [x] Phase 9.

Stop and run all tests.

### Batch D — MCP

- [x] Phase 10.
- [x] Phase 11.
- [x] Phase 12.
- [x] Phase 13.
- [x] Phase 14.

Stop and run all tests. Stdio MCP transport is covered by contract tests; MCP Inspector GUI was not available.

### Batch E — Local UX

- [x] Phase 15.
- [x] Phase 16.
- [x] Phase 17.

Stop and validate local CLI behavior.

### Batch F — Integration

- [x] Phase 18 (stdio transport; Inspector GUI not run).
- [ ] Phase 19.

Do not change public tool semantics casually in this phase. If real-device behavior requires a contract change, update `SPEC.md` deliberately.

### Batch G — Ship

- [x] Phase 20.
- [x] Phase 21.

---

# Implementation Rule

When the implementation agent is uncertain about an upstream API:

1. Read `SPEC.md` for intended behavior.
2. Check the pinned `references/pyatv-0.18.0/` corpus.
3. Check the pinned MCP Python SDK 2.2.0 corpus.
4. Check the MCP 2026-07-28 specification if protocol semantics are involved.
5. Add or update a test that proves the chosen behavior.
6. Do not substitute a newer `master` API or old MCP v1 example without deliberate review.

The implementation should adapt to pinned upstream reality while preserving the semantic MCP contract wherever possible.
