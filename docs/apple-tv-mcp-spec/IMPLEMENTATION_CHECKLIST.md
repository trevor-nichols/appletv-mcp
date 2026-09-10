# AgenAI Apple TV MCP — Implementation Checklist

This checklist is ordered by dependency. Complete each phase before moving to later phases unless a task is explicitly marked as parallelizable.

The goal is to eliminate architectural decision-making during implementation: later work should build only on interfaces and behavior already established in earlier phases.

---

## Phase 0 — Repository and Version Baseline

### 0.1 Create repository structure

- [ ] Create `agenai-appletv-mcp/`.
- [ ] Add `SPEC.md`.
- [ ] Add `IMPLEMENTATION_CHECKLIST.md`.
- [ ] Add `README.md`.
- [ ] Add `.gitignore`.
- [ ] Add `.python-version`.
- [ ] Add `references/`.
- [ ] Add `src/agenai_appletv_mcp/`.
- [ ] Add `tests/`.

### 0.2 Pin runtime

- [ ] Set `.python-version` to `3.14.7`.
- [ ] Initialize project with `uv`.
- [ ] Set `requires-python = ">=3.14,<3.15"`.
- [ ] Add `pyatv==0.18.0`.
- [ ] Add `mcp[cli]==2.2.0`.
- [ ] Add `pydantic>=2.12,<3`.
- [ ] Add `platformdirs`.
- [ ] Add dev dependency `pytest`.
- [ ] Add dev dependency `pytest-asyncio`.
- [ ] Add dev dependency `ruff`.
- [ ] Add dev dependency `pyright`.
- [ ] Generate `uv.lock`.
- [ ] Commit `uv.lock`.

### 0.3 Configure quality tooling

- [ ] Configure Ruff linting.
- [ ] Configure Ruff formatting.
- [ ] Configure Pyright.
- [ ] Configure Pytest.
- [ ] Add basic CI workflow.
- [ ] Verify an empty/minimal project passes all quality gates.

### Exit criteria

- [ ] `uv sync` succeeds from a clean checkout.
- [ ] `uv run ruff check .` passes.
- [ ] `uv run ruff format --check .` passes.
- [ ] `uv run pyright` passes.
- [ ] `uv run pytest` passes.

---

## Phase 1 — Domain Models and Constants

This phase has no Apple TV network dependency.

### 1.1 Define enums and literals

Create normalized domain types for:

- [ ] `PowerTarget`.
- [ ] `PowerState`.
- [ ] `FeatureAvailability`.
- [ ] `RemoteButton`.
- [ ] `PressAction`.
- [ ] `PlaybackAction`.
- [ ] `SkipDirection`.
- [ ] `VolumeDirection`.
- [ ] Playback state.
- [ ] Media type.
- [ ] Keyboard focus state.

### 1.2 Define configuration model

Create `Settings` with:

- [ ] `device_identifier`.
- [ ] `device_name`.
- [ ] `preferred_host`.
- [ ] `scan_timeout_seconds`.
- [ ] `command_timeout_seconds`.

Validation:

- [ ] Positive timeouts.
- [ ] Empty identifier rejected.
- [ ] Host remains optional.
- [ ] Device name remains optional/informational.

### 1.3 Define output models

Create:

- [ ] `DeviceInfo`.
- [ ] `AppInfo`.
- [ ] `PlaybackInfo`.
- [ ] `AppleTVStatus`.
- [ ] `AppleTVCapabilities`.
- [ ] `PowerResult`.
- [ ] `OpenAppResult`.
- [ ] `OpenUrlResult`.
- [ ] `PressResult`.
- [ ] `PlaybackResult`.
- [ ] `SeekResult`.
- [ ] `SkipResult`.
- [ ] `TextResult`.
- [ ] `VolumeResult`.
- [ ] `VolumeAdjustResult`.

### 1.4 Define internal exceptions

Create internal exception types only where they improve translation clarity, for example:

- [ ] `DeviceNotConfiguredError`.
- [ ] `DeviceNotFoundError`.
- [ ] `DeviceConnectionError`.
- [ ] `FeatureUnavailableError`.
- [ ] `FeatureUnsupportedError`.
- [ ] `AmbiguousAppError`.
- [ ] `AppNotFoundError`.
- [ ] `UncertainExecutionError`.

Do not recreate upstream exception hierarchies unnecessarily.

### 1.5 Tests

- [ ] Test Settings validation.
- [ ] Test enum serialization.
- [ ] Test output-model serialization.
- [ ] Test optional fields.
- [ ] Test field constraints.

### Exit criteria

- [ ] Models are independent of MCP.
- [ ] Models are independent of live `pyatv` connections.
- [ ] All model tests pass.

---

## Phase 2 — Configuration Persistence

Depends on Phase 1.

### 2.1 Determine config location

- [ ] Use `platformdirs`.
- [ ] Define application name consistently.
- [ ] Define config filename.
- [ ] Make config location overridable in tests.

### 2.2 Implement configuration repository

Implement:

- [ ] `load_settings()`.
- [ ] `save_settings()`.
- [ ] Atomic write strategy.
- [ ] Helpful error for missing config.
- [ ] Helpful error for malformed config.

### 2.3 Safety

- [ ] Do not put `pyatv` credentials into this config.
- [ ] Do not copy raw `pyatv` storage into this config.
- [ ] Ensure logs do not dump entire config objects if future secret fields are added.

### 2.4 Tests

- [ ] Round-trip save/load.
- [ ] Missing file.
- [ ] Invalid JSON.
- [ ] Invalid settings.
- [ ] Atomic replacement behavior where practical.

### Exit criteria

- [ ] Device profile persistence works independently of `pyatv` credentials.

---

## Phase 3 — `pyatv` Persistent Storage Adapter

Depends on Phase 0.

### 3.1 Review pinned storage API

Using the pinned `pyatv 0.18.0` references:

- [ ] Confirm exact `FileStorage` construction API.
- [ ] Confirm default storage path behavior.
- [ ] Confirm required async load/save lifecycle.
- [ ] Confirm compatibility with `atvremote` credentials.

### 3.2 Implement storage helper

Create a small adapter that:

- [ ] Creates/opens persistent `pyatv` storage.
- [ ] Loads it once during application lifespan.
- [ ] Exposes it to `ConnectionManager`.
- [ ] Closes/saves only as required by pinned API behavior.

### 3.3 Logging

- [ ] Never log raw credentials.
- [ ] Never log raw storage objects.
- [ ] Never serialize storage into MCP results.

### 3.4 Tests

- [ ] Mock storage load.
- [ ] Mock load failure.
- [ ] Verify storage object reaches connection layer.

### Exit criteria

- [ ] Credentials can be loaded without involving MCP tools.

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
    async def close(self) -> None: ...
    def invalidate(self) -> None: ...
```

### 4.2 Implement preferred-host discovery

- [ ] If `preferred_host` exists, perform unicast scan.
- [ ] Verify returned device stable identifier.
- [ ] Reject a different Apple TV found at the old IP.
- [ ] Use stored credentials/configuration during connection.

### 4.3 Implement identifier fallback discovery

- [ ] Fall back to multicast scan when preferred-host resolution fails.
- [ ] Filter/select by configured stable identifier.
- [ ] Fail clearly when the configured device is not found.
- [ ] Update `preferred_host` when the correct device is rediscovered elsewhere.
- [ ] Persist updated host.

### 4.4 Implement connection caching

- [ ] Cache one live Apple TV connection.
- [ ] Reuse it across controller calls.
- [ ] Do not reconnect on every MCP tool call.

### 4.5 Implement concurrency

- [ ] Add async connection lock.
- [ ] Collapse simultaneous `get()` calls into one discovery/connect operation.
- [ ] Prevent duplicate connections during reconnect.

### 4.6 Implement invalidation

- [ ] Invalidate cached connection on disconnect callback.
- [ ] Invalidate cached connection on known broken-connection failures.
- [ ] Preserve persistent credentials.
- [ ] Preserve device profile.

### 4.7 Implement close

- [ ] Close active connection cleanly.
- [ ] Make repeated `close()` safe.
- [ ] Prevent new connection use during shutdown if practical.

### 4.8 Unit tests

Mock all `pyatv` network calls.

Test:

- [ ] Cached reuse.
- [ ] Preferred-host success.
- [ ] Preferred-host wrong-device rejection.
- [ ] Preferred-host failure followed by multicast success.
- [ ] Configured identifier not found.
- [ ] Preferred-host update after rediscovery.
- [ ] Concurrent `get()` calls.
- [ ] Explicit reconnect.
- [ ] Invalidation.
- [ ] Close.
- [ ] Connection failure translation.

### Exit criteria

- [ ] One configured device can be discovered and connected by stable identifier.
- [ ] IP changes are recoverable without reconfiguration.
- [ ] No MCP code is required to use the connection manager.

---

## Phase 5 — Capability Adapter

Depends on Phase 4.

### 5.1 Verify exact `pyatv 0.18.0` feature enum names

From the pinned source/docs, map normalized operations to exact `FeatureName` members.

Required coverage:

- [ ] Turn on.
- [ ] Turn off.
- [ ] App list.
- [ ] App launch.
- [ ] Up.
- [ ] Down.
- [ ] Left.
- [ ] Right.
- [ ] Select.
- [ ] Menu/back.
- [ ] Home.
- [ ] Play.
- [ ] Pause.
- [ ] Play/pause.
- [ ] Stop.
- [ ] Next.
- [ ] Previous.
- [ ] Set position.
- [ ] Skip forward.
- [ ] Skip backward.
- [ ] Text get/set where applicable.
- [ ] Keyboard focus where applicable.
- [ ] Volume get/set/up/down where applicable.

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

- [ ] `feature_state(operation)`.
- [ ] `require_feature(operation)`.
- [ ] `normalized_capabilities()`.

Behavior:

- [ ] Available → execute.
- [ ] Unknown → permit attempt.
- [ ] Unavailable → expected operational failure.
- [ ] Unsupported → expected device-capability failure.

### 5.5 Tests

- [ ] Every public MCP operation has expected feature mapping where relevant.
- [ ] Unknown behavior.
- [ ] Unavailable behavior.
- [ ] Unsupported behavior.
- [ ] Capability output normalization.

### Exit criteria

- [ ] No controller operation needs to understand raw feature-state semantics itself.

---

## Phase 6 — AppleTVController: Read-Only Surface

Depends on Phases 4–5.

Implement read-only functionality first because it is easiest to test and safest against a live device.

### 6.1 `status()`

Normalize:

- [ ] Connection/device identity.
- [ ] Power state.
- [ ] Playback state.
- [ ] Media metadata.
- [ ] `media_app`.
- [ ] Position.
- [ ] Duration.
- [ ] Repeat.
- [ ] Shuffle.
- [ ] Volume.
- [ ] Keyboard focus.

Critical semantic rule:

- [ ] Name the field `media_app`.
- [ ] Do not call it `active_app`.
- [ ] Do not imply foreground-app certainty.

### 6.2 `capabilities()`

- [ ] Return normalized controller operations.
- [ ] Do not expose raw `FeatureName` enum values.

### 6.3 `list_apps()`

- [ ] Return typed `AppInfo`.
- [ ] Optional case-insensitive filtering by name.
- [ ] Optional case-insensitive filtering by bundle ID.
- [ ] No fuzzy auto-selection.

### 6.4 Read retry policy

- [ ] Broken cached connection may reconnect and retry once.
- [ ] Do not loop indefinitely.
- [ ] Convert final failures into domain-level errors.

### 6.5 Tests

- [ ] Full status normalization.
- [ ] Missing metadata.
- [ ] Unknown power.
- [ ] No media app.
- [ ] No volume support.
- [ ] Keyboard focus unavailable.
- [ ] Capability normalization.
- [ ] App filtering.
- [ ] Read retry success.
- [ ] Read retry exhaustion.

### Exit criteria

- [ ] The project can report meaningful device state without MCP.

---

## Phase 7 — AppleTVController: Idempotent/Semantic Actions

Depends on Phase 6.

Add a controller command lock before write actions.

### 7.1 Command serialization

- [ ] Add async command lock.
- [ ] Ensure action methods execute serially.
- [ ] Keep status reads outside the lock unless required by upstream behavior.

### 7.2 Power

Implement:

- [ ] `power("on")`.
- [ ] `power("off")`.
- [ ] Feature checks.
- [ ] Optional state verification.
- [ ] Bounded wait.
- [ ] Idempotent retry rules.

### 7.3 Open app

Implement deterministic resolution:

1. [ ] Exact bundle ID wins.
2. [ ] Case-insensitive exact name.
3. [ ] Ambiguity returns error.
4. [ ] Missing app returns error.
5. [ ] Candidate suggestions may be included.
6. [ ] Fuzzy match never executes automatically.

Then:

- [ ] Launch resolved bundle ID.
- [ ] Return `OpenAppResult`.

### 7.4 Open URL

- [ ] Accept URL string.
- [ ] Invoke `apps.launch_app(url)` as supported by pinned API.
- [ ] Return acceptance only.
- [ ] Do not claim content success.

### 7.5 Absolute seek

- [ ] Validate position >= 0.
- [ ] Feature gate.
- [ ] Invoke set-position API.
- [ ] Safe reconnect/retry only when semantics remain certain.

### 7.6 Absolute volume

- [ ] Validate 0–100.
- [ ] Feature gate.
- [ ] Set volume.
- [ ] Read back current volume where feasible.
- [ ] Return requested and observed values.

### 7.7 Set text

- [ ] Feature gate.
- [ ] Prefer keyboard text-set API.
- [ ] Permit empty string to clear field.
- [ ] Never log input text.
- [ ] Return only character count and acceptance.

### 7.8 Tests

- [ ] Power on/off.
- [ ] App bundle-ID resolution.
- [ ] App exact-name resolution.
- [ ] App ambiguity.
- [ ] App missing with candidates.
- [ ] URL launch.
- [ ] Seek.
- [ ] Volume set.
- [ ] Text set.
- [ ] Empty text.
- [ ] Text never appears in logs.
- [ ] Command serialization.

### Exit criteria

- [ ] Semantic write actions work through controller without MCP.

---

## Phase 8 — AppleTVController: Non-Idempotent Actions

Depends on Phase 7.

### 8.1 Remote press

Support:

- [ ] up.
- [ ] down.
- [ ] left.
- [ ] right.
- [ ] select.
- [ ] back.
- [ ] home.

Support action styles:

- [ ] tap.
- [ ] double tap.
- [ ] hold.

Support:

- [ ] count 1–10.
- [ ] sequential execution.
- [ ] completed-count reporting.

Confirm exact pinned `pyatv` APIs for press behavior before implementation.

### 8.2 Back mapping

- [ ] Map MCP `back` to the correct `pyatv` menu/back operation for 0.18.0.
- [ ] Do not expose `menu` to the MCP user unless later desired.

### 8.3 Playback

Support:

- [ ] play.
- [ ] pause.
- [ ] toggle.
- [ ] stop.
- [ ] next.
- [ ] previous.

### 8.4 Relative skip

Support:

- [ ] forward.
- [ ] backward.
- [ ] optional seconds.
- [ ] seconds=0 default-device interval semantics.

### 8.5 Relative volume

Support:

- [ ] up.
- [ ] down.
- [ ] steps 1–10.
- [ ] completed-step count.

### 8.6 Uncertain execution handling

For every non-idempotent operation:

- [ ] Do not automatically replay after uncertain transport failure.
- [ ] Invalidate broken connection.
- [ ] Return an error explaining execution may have occurred.
- [ ] Let a later independent call reconnect.

### 8.7 Tests

- [ ] Every button maps correctly.
- [ ] Tap behavior.
- [ ] Double tap behavior.
- [ ] Hold behavior.
- [ ] Count sequencing.
- [ ] Partial completion.
- [ ] Playback mappings.
- [ ] Skip mappings.
- [ ] Relative volume.
- [ ] No automatic replay after uncertain failure.

### Exit criteria

- [ ] Blind controls are available but handled more conservatively than semantic/idempotent controls.

---

## Phase 9 — Error Translation Layer

Depends on Phases 4–8.

### 9.1 Define translation rules

Map expected `pyatv` failures into clear controller/domain errors.

Cover:

- [ ] Device unavailable.
- [ ] Connection lost.
- [ ] Authentication/pairing unavailable.
- [ ] Feature unsupported.
- [ ] Feature temporarily unavailable.
- [ ] Timeout.
- [ ] App not found.
- [ ] Ambiguous app.
- [ ] Uncertain non-idempotent execution.

### 9.2 Preserve safe context

Error messages may include:

- [ ] Operation name.
- [ ] Device display name.
- [ ] Requested app name.
- [ ] Capability state.

Error messages must not include:

- [ ] Credentials.
- [ ] Passwords.
- [ ] Raw credential objects.
- [ ] Raw storage serialization.
- [ ] Keyboard text.

### 9.3 Tests

- [ ] Every expected failure becomes a deterministic domain error.
- [ ] Unexpected failures remain unexpected and retain traceback in logs.
- [ ] Secret-bearing values are absent from expected error strings.

### Exit criteria

- [ ] MCP layer will not need to understand `pyatv` exception types.

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

- [ ] Load settings.
- [ ] Load `pyatv` storage.
- [ ] Create `ConnectionManager`.
- [ ] Create `AppleTVController`.
- [ ] Do not connect to Apple TV.

Shutdown:

- [ ] Close connection manager.
- [ ] Clean up storage if required.

### 10.2 Server

Create explicitly:

- [ ] Name `agenai-appletv`.
- [ ] Version `0.1.0`.
- [ ] Lifespan.
- [ ] Server instructions.
- [ ] Default stdio execution path.

### 10.3 Logging

- [ ] Use Python `logging`.
- [ ] No `print()` in serving path.
- [ ] Default app logger INFO.
- [ ] Default `pyatv` logger WARNING.
- [ ] Optional debug mode.

### 10.4 Tests

- [ ] Server can instantiate with mocked dependencies.
- [ ] MCP server startup does not connect to Apple TV.
- [ ] MCP server startup succeeds while device mock is unavailable.
- [ ] Shutdown closes connection manager.

### Exit criteria

- [ ] MCP process lifecycle is independent of Apple TV availability.

---

## Phase 11 — MCP Read-Only Tools

Depends on Phase 10.

Implement thin MCP wrappers only.

### 11.1 `apple_tv_status`

- [ ] No user input.
- [ ] Return `AppleTVStatus`.
- [ ] `read_only_hint=True`.
- [ ] `open_world_hint=False`.

### 11.2 `apple_tv_capabilities`

- [ ] No user input.
- [ ] Return `AppleTVCapabilities`.
- [ ] `read_only_hint=True`.
- [ ] `open_world_hint=False`.

### 11.3 `apple_tv_list_apps`

- [ ] Optional `query`.
- [ ] Return typed app list.
- [ ] `read_only_hint=True`.
- [ ] `open_world_hint=False`.

### 11.4 MCP error conversion

- [ ] Expected domain/controller errors become `ToolError`.
- [ ] Do not return error strings as successful tool results.

### Exit criteria

- [ ] Read-only tools work via MCP in-memory client.

---

## Phase 12 — MCP Semantic Write Tools

Depends on Phase 11.

Implement:

### 12.1 `apple_tv_power`

- [ ] Typed `state`.
- [ ] Typed result.
- [ ] `idempotent_hint=True`.
- [ ] `destructive_hint=False`.
- [ ] `open_world_hint=False`.

### 12.2 `apple_tv_open_app`

- [ ] Typed `app`.
- [ ] Typed result.
- [ ] Exact-match semantics documented in tool docstring.

### 12.3 `apple_tv_open_url`

- [ ] Typed `url`.
- [ ] Typed result.
- [ ] Tool description avoids claiming visual verification.

### 12.4 `apple_tv_seek`

- [ ] `position_seconds >= 0`.
- [ ] Typed result.
- [ ] `idempotent_hint=True`.

### 12.5 `apple_tv_set_text`

- [ ] Typed text.
- [ ] Typed result.
- [ ] `idempotent_hint=True`.
- [ ] Description states focused text field requirement.

### 12.6 `apple_tv_set_volume`

- [ ] 0–100 constraint.
- [ ] Typed result.
- [ ] `idempotent_hint=True`.

### Exit criteria

- [ ] Semantic action tools expose only normalized domain concepts.

---

## Phase 13 — MCP Non-Idempotent Tools

Depends on Phase 12.

### 13.1 `apple_tv_press`

- [ ] Button enum.
- [ ] Action enum.
- [ ] Count range 1–10.
- [ ] Structured result.
- [ ] `idempotent_hint=False`.
- [ ] Description explicitly states blind navigation.

### 13.2 `apple_tv_playback`

- [ ] Action enum.
- [ ] Structured result.
- [ ] Treat toggle as non-idempotent.

### 13.3 `apple_tv_skip`

- [ ] Direction enum.
- [ ] Seconds >= 0.
- [ ] Structured result.

### 13.4 `apple_tv_adjust_volume`

- [ ] Direction enum.
- [ ] Steps range 1–10.
- [ ] Structured result.
- [ ] `idempotent_hint=False`.

### Exit criteria

- [ ] Agent has fallback control surface without raw `pyatv` concepts.

---

## Phase 14 — MCP Contract Test Suite

Depends on Phases 11–13.

Use the MCP SDK in-memory client.

### 14.1 Tool inventory

Assert exact v0.1 tool set:

- [ ] `apple_tv_status`.
- [ ] `apple_tv_capabilities`.
- [ ] `apple_tv_list_apps`.
- [ ] `apple_tv_power`.
- [ ] `apple_tv_open_app`.
- [ ] `apple_tv_open_url`.
- [ ] `apple_tv_press`.
- [ ] `apple_tv_playback`.
- [ ] `apple_tv_seek`.
- [ ] `apple_tv_skip`.
- [ ] `apple_tv_set_text`.
- [ ] `apple_tv_set_volume`.
- [ ] `apple_tv_adjust_volume`.

### 14.2 Schema assertions

For every tool:

- [ ] Tool name.
- [ ] Description.
- [ ] Required arguments.
- [ ] Optional arguments.
- [ ] Enum values.
- [ ] Numeric bounds.
- [ ] Output schema.
- [ ] Tool annotations.

### 14.3 Behavior assertions

- [ ] Structured content returned.
- [ ] Expected controller failures become `is_error=True` tool results.
- [ ] Invalid MCP input is rejected before controller execution.
- [ ] Server can be tested without subprocess.
- [ ] Server can be tested without physical Apple TV.

### Exit criteria

- [ ] MCP contract is stable and independently testable.

---

## Phase 15 — CLI: `configure`

Depends on Phases 2–5.

Can be implemented earlier after Phase 5, but should be complete before live-device integration.

### 15.1 Device discovery

- [ ] Load persistent `pyatv` credentials.
- [ ] Scan devices.
- [ ] Present discovered candidates.
- [ ] Show name.
- [ ] Show stable identifier.
- [ ] Show host.

### 15.2 Selection

- [ ] Select one Apple TV.
- [ ] Persist stable identifier.
- [ ] Persist display name.
- [ ] Persist preferred host.

### 15.3 Verification

- [ ] Connect using stored credentials.
- [ ] Verify device identity.
- [ ] Display normalized capabilities.
- [ ] Close cleanly.

### 15.4 Failure behavior

- [ ] No credentials found.
- [ ] Pairing required.
- [ ] Device disappears.
- [ ] Connection rejected.
- [ ] Invalid selection.

### Exit criteria

- [ ] A user can configure the MCP server without editing JSON manually.

---

## Phase 16 — CLI: `doctor`

Depends on Phases 6–9 and Phase 15.

### 16.1 Checks

Implement non-destructive checks for:

- [ ] Configuration exists.
- [ ] Configuration validates.
- [ ] `pyatv` storage loads.
- [ ] Configured identifier can be discovered.
- [ ] Preferred host matches or can be repaired.
- [ ] Connection succeeds.
- [ ] Power capability.
- [ ] App listing/launch capability.
- [ ] Navigation capabilities.
- [ ] Playback capabilities.
- [ ] Keyboard capability/current state.
- [ ] Volume capability.

### 16.2 Output

- [ ] Screen-reader-friendly line output.
- [ ] One check per line.
- [ ] Clear success/failure symbols or words.
- [ ] No secret data.
- [ ] Non-zero exit code on required failure.

### Exit criteria

- [ ] `doctor` provides enough information to diagnose setup without starting MCP.

---

## Phase 17 — CLI: `serve`

Depends on Phase 10.

### 17.1 Command

- [ ] Add `agenai-appletv serve`.
- [ ] Start stdio MCP server.
- [ ] No normal stdout output.
- [ ] Support debug logging flag if useful.

### 17.2 Packaging entrypoint

- [ ] Add console-script entry point.
- [ ] Verify `uv run agenai-appletv serve`.
- [ ] Verify installed command execution.

### Exit criteria

- [ ] MCP hosts can launch the server through one stable CLI command.

---

## Phase 18 — Host Integration

Depends on Phases 14 and 17.

### 18.1 Generic stdio config

Document command form:

```text
uv --directory /absolute/path/to/agenai-appletv-mcp run agenai-appletv serve
```

or installed executable path.

### 18.2 Test with MCP Inspector

- [ ] Tool list appears.
- [ ] Schemas render.
- [ ] Read-only tools work.
- [ ] Expected errors render as tool errors.
- [ ] No protocol corruption from stdout.

### 18.3 Test with target agent host(s)

For each intended host:

- [ ] Server starts.
- [ ] Tools discover.
- [ ] Tool arguments serialize correctly.
- [ ] Structured results are preserved.
- [ ] Host does not incorrectly require HTTP/OAuth.

### Exit criteria

- [ ] At least one real agent host can control a mocked controller through the actual stdio process.

---

## Phase 19 — Live Apple TV Integration

Depends on Phases 15–18.

This phase validates pinned `pyatv` assumptions against the real device.

### 19.1 Pairing/setup

- [ ] Run `atvremote wizard` if credentials do not already exist.
- [ ] Run `agenai-appletv configure`.
- [ ] Run `agenai-appletv doctor`.

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

- [ ] Purpose.
- [ ] Requirements.
- [ ] Install.
- [ ] Pairing.
- [ ] Configure.
- [ ] Doctor.
- [ ] Serve.
- [ ] MCP host configuration.
- [ ] Tool summary.
- [ ] Perception limitations.
- [ ] Troubleshooting.

### 20.2 Security/privacy notes

Document:

- [ ] Pairing credentials remain local.
- [ ] Credentials are not exposed through MCP.
- [ ] Text-entry contents are not logged.
- [ ] v0.1 is local stdio only.

### 20.3 Developer docs

Document:

- [ ] Architecture layers.
- [ ] Connection retry rules.
- [ ] Idempotency rules.
- [ ] Feature mapping.
- [ ] Testing.
- [ ] How to update pinned upstream versions.

### Exit criteria

- [ ] A new developer can set up the project without reading implementation source.

---

## Phase 21 — Final Quality and Release Gate

### 21.1 Automated gates

- [ ] `uv sync --locked`.
- [ ] `uv run ruff check .`.
- [ ] `uv run ruff format --check .`.
- [ ] `uv run pyright`.
- [ ] `uv run pytest`.

### 21.2 Contract gate

- [ ] Exact v0.1 tool inventory.
- [ ] No accidental raw-`pyatv` tools.
- [ ] No pairing MCP tool.
- [ ] No device selector argument.
- [ ] No HTTP/OAuth code in v0.1.
- [ ] No foreground-app claims.
- [ ] No visual-screen claims.

### 21.3 Security gate

Search repository for:

- [ ] Hardcoded credentials.
- [ ] Raw storage dumps.
- [ ] Accidental keyboard text logging.
- [ ] `print(` in MCP serving paths.
- [ ] Secret-looking fixture data.

### 21.4 Live gate

- [ ] `configure` succeeds.
- [ ] `doctor` succeeds.
- [ ] Agent host can call `apple_tv_status`.
- [ ] Agent host can launch an app.
- [ ] Agent host can control playback.
- [ ] Device recovers after reconnect.
- [ ] IP change does not require re-pairing.

### 21.5 Release

- [ ] Set version `0.1.0`.
- [ ] Tag release.
- [ ] Preserve pinned references used for implementation.
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

- [ ] Phase 0.
- [ ] Phase 1.
- [ ] Phase 2.
- [ ] Phase 3.

Stop and run all tests.

### Batch B — Device Infrastructure

- [ ] Phase 4.
- [ ] Phase 5.

Stop and run all tests.

### Batch C — Controller

- [ ] Phase 6.
- [ ] Phase 7.
- [ ] Phase 8.
- [ ] Phase 9.

Stop and run all tests.

### Batch D — MCP

- [ ] Phase 10.
- [ ] Phase 11.
- [ ] Phase 12.
- [ ] Phase 13.
- [ ] Phase 14.

Stop and run all tests plus MCP Inspector.

### Batch E — Local UX

- [ ] Phase 15.
- [ ] Phase 16.
- [ ] Phase 17.

Stop and validate local CLI behavior.

### Batch F — Integration

- [ ] Phase 18.
- [ ] Phase 19.

Do not change public tool semantics casually in this phase. If real-device behavior requires a contract change, update `SPEC.md` deliberately.

### Batch G — Ship

- [ ] Phase 20.
- [ ] Phase 21.

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
