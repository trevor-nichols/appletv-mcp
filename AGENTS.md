This file defines repository-wide instructions for coding agents working on Apple TV MCP (`appletv-mcp`).

These instructions apply to the entire repository unless a more specific nested `AGENTS.md` explicitly overrides them for a subtree.

The project is a production-quality local MCP server that exposes semantic Apple TV control to AI agents through `pyatv`. Treat it as infrastructure software, not a demo.

This project is named Apple TV MCP and is independent of AgenAI.
Do not introduce AgenAI branding, package prefixes, CLI prefixes, repository
links, environment-variable prefixes, or other AgenAI-specific naming.

---

## Naming

Use these canonical names. Do not invent aliases, shims, or "compatible" old names.

```text
Human/product name:                              Apple TV MCP
GitHub repository:                               trevor-nichols/appletv-mcp
Python distribution/project name:                appletv-mcp
Python import package:                           appletv_mcp
Source package:                                  src/appletv_mcp/
CLI executable:                                  appletv-mcp
MCP server name:                                 appletv-mcp
Configuration application/directory name:        appletv-mcp
Configuration override environment variable:     APPLETV_MCP_CONFIG_DIR
```

Do not use:

```text
AgenAI Apple TV MCP
agenai-appletv-mcp
agenai_appletv_mcp
agenai-appletv
AGENAI_APPLETV_CONFIG_DIR
github.com/agenai/...
```

MCP tool names remain `apple_tv_*` as listed in §8. Domain types such as `AppleTVController`, `AppleTVStatus`, and `AppleTVGateway` are not product-prefix names; do not rename them.

Live-test environment variables `APPLE_TV_INTEGRATION_TESTS` and `APPLE_TV_LIVE_WRITES` are unrelated to product branding; do not rename them.

---

## 1. Read Before Editing

Before modifying code, inspect the repository and read the project documentation.

At minimum, read:

```text
docs/apple-tv-mcp-spec/SPEC_v0.2.md
docs/apple-tv-mcp-spec/SPEC.md
docs/apple-tv-mcp-spec/IMPLEMENTATION_CHECKLIST.md
docs/apple-tv-mcp-spec/ADR-0001-screen-capture.md
```

Also inspect the pinned reference corpus under:

```text
docs/references/
```

That corpus is local-only (gitignored, not on GitHub). Keep a copy on development machines. Do not commit it. If the directory is absent, use the installed packages and public upstream docs instead.

The reference corpus should include material for:

```text
pyatv 0.18.0
MCP Python SDK 2.2.0
MCP protocol 2026-07-28
pymobiledevice3 11.12.4 (sidecar only, docs/references/pymobiledevice3/)
```

Do not implement from memory when an exact upstream API is available in the pinned references.

If file paths differ slightly, locate the actual files rather than assuming they are missing.

---

## 2. Source-of-Truth Order

When sources disagree, use this precedence:

1. `docs/apple-tv-mcp-spec/SPEC_v0.2.md` for screen-capture behavior, the sidecar contract, and `apple_tv_screenshot`.
2. `docs/apple-tv-mcp-spec/SPEC.md` for inherited v0.1 control behavior, architecture intent, and the rest of the public MCP contract.
3. `AGENTS.md` for repository-wide implementation rules.
4. `docs/apple-tv-mcp-spec/IMPLEMENTATION_CHECKLIST.md` for build order and completeness tracking.
5. `docs/apple-tv-mcp-spec/ADR-0001-screen-capture.md` for v0.2 transport and identity decisions.
6. Pinned `pyatv 0.18.0` references for exact `pyatv` APIs and behavior.
7. Pinned MCP Python SDK 2.2.0 references for exact SDK APIs and behavior.
8. Pinned `pymobiledevice3` 11.12.4 references and the installed sidecar package for helper transport APIs. Never import this library from `appletv_mcp`.
9. MCP 2026-07-28 specification for protocol semantics.
10. Tests in this repository.

If pinned upstream behavior conflicts with an assumption in the spec:

1. Verify the behavior in the pinned source/docs.
2. Preserve the semantic public contract where possible.
3. Add a regression test.
4. Update the spec deliberately if behavior must change.
5. Document the deviation.

Do not silently substitute a newer upstream API.

---

## 3. Version Policy

The intended baseline is:

```text
Python            3.14.7
pyatv             0.18.0
MCP Python SDK    2.2.0
Package manager   uv
Sidecar           pymobiledevice3 11.12.4 (sidecars/appletv-screenshot only)
```

Use stable releases only.

Do not upgrade pinned dependencies unless the task explicitly requires it.

Do not use:

```text
FastMCP
mcp.server.fastmcp
MCP v1 examples
deprecated MCP APIs
unreleased pyatv master APIs
old camelCase MCP Python attributes
```

The MCP server should use the v2 API:

```python
from mcp.server import MCPServer
```

Keep `uv.lock` reproducible and committed.

---

## 4. Development Philosophy

Optimize for:

```text
correctness
maintainability
clarity
strong typing
deterministic behavior
safe retries
clean async lifecycle
predictable errors
testability
clean agent-facing schemas
minimal hidden magic
```

The codebase should look deliberately engineered.

Avoid both extremes:

- Do not build monolithic modules.
- Do not create unnecessary enterprise abstraction layers.

Use the simplest design that preserves clear boundaries and testability.

---

## 5. Architecture

Maintain a layered package structure.

Preferred shape:

```text
src/
└── appletv_mcp/
    ├── domain/
    │   ├── enums.py
    │   ├── errors.py
    │   └── models/
    │
    ├── application/
    │   ├── services/
    │   ├── policies/
    │   └── ports/
    │
    ├── infrastructure/
    │   ├── config/
    │   ├── pyatv/
    │   └── observability/
    │
    └── interfaces/
        ├── mcp/
        │   └── tools/
        └── cli/
            └── commands/
```

You may refine the exact tree when a more cohesive structure emerges, but preserve the dependency boundaries below.

---

## 6. Layer Boundaries

### Domain

The domain layer contains:

- Normalized enums.
- Pydantic/domain models.
- Stable result models.
- Domain-level errors.
- Vocabulary used across the project.

The domain layer must not import:

```text
pyatv
mcp
CLI implementation
filesystem persistence implementation
```

Domain types model our contract, not upstream library internals.

### Application

The application layer contains:

- `AppleTVController`.
- Capability policy.
- Retry/idempotency policy.
- App-resolution logic.
- Semantic orchestration.
- Small ports/protocols where useful.

The application layer may depend on domain.

It should not depend on MCP.

Prefer `typing.Protocol` only when it creates a meaningful testability or boundary advantage.

Do not define interfaces for trivial classes merely for architectural symmetry.

### Infrastructure

Infrastructure contains concrete adapters for:

- `pyatv`.
- Discovery.
- Connection lifecycle.
- Pairing credential storage.
- Configuration persistence.
- Filesystem paths.
- Logging/redaction.

Direct `pyatv` imports belong here.

Keep raw `pyatv` objects close to this boundary.

### Interfaces

Interfaces expose the application through:

```text
MCP
CLI
```

MCP handlers should be thin.

CLI commands should delegate to application/infrastructure services rather than duplicate logic.

---

## 7. Module Size and Cohesion

Do not create monolithic files.

Treat files larger than roughly 250–350 substantive lines as a design smell requiring review.

A larger cohesive file can be acceptable, but a module combining unrelated concerns is not.

Do not place all MCP tools in one file.

Prefer cohesive tool modules such as:

```text
tools/status.py
tools/apps.py
tools/power.py
tools/remote.py
tools/playback.py
tools/text.py
tools/volume.py
```

Do not create one tiny file per trivial function either.

Group by responsibility.

---

## 8. Public MCP Contract

The v0.2 MCP surface is exactly:

```text
apple_tv_status
apple_tv_capabilities
apple_tv_list_apps
apple_tv_power
apple_tv_open_app
apple_tv_open_url
apple_tv_press
apple_tv_playback
apple_tv_seek
apple_tv_skip
apple_tv_set_text
apple_tv_set_volume
apple_tv_adjust_volume
apple_tv_screenshot
```

`apple_tv_screenshot` takes no arguments and returns one native MCP `ImageContent`
(`image/png`) built with the SDK `Image` helper. It is registered with
`structured_output=False` and is the only tool without an output schema. Do not weaken
the output-schema assertion for the other thirteen tools to accommodate it.

Do not add speculative MCP tools without updating the spec.

Do not expose raw `pyatv` or `pymobiledevice3` operations or protocol names.

Do not expose pairing (Companion or RemoteXPC) as an MCP tool.

Do not add a device selector argument.

Do not casually rename tool parameters or result fields after contract tests exist.

Public MCP tool inputs and outputs are API surface.

---

## 9. Semantic Control First

Prefer semantic actions over blind UI navigation.

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

The agent does not watch the Apple TV screen. It can request one point-in-time PNG through
`apple_tv_screenshot` when the optional helper is installed and paired; that image is stale
as soon as it is returned.

Never imply visual state that cannot be observed. A claim about what is on screen needs
either observable `pyatv` state or a screenshot taken after the action.

---

## 10. Perception Semantics

Use:

```text
media_app
```

for the application associated with current media metadata.

Do not rename it to:

```text
active_app
foreground_app
current_app
```

unless the pinned upstream API provides a separate signal that truly guarantees foreground state.

Do not claim:

```text
"The Netflix screen is open."
"The Search button is highlighted."
"The movie visibly started."
```

unless actual observable device state or a fresh screenshot supports the claim.

Missing metadata should generally become `None`, not fabricated values.

Do not add screenshot availability to `apple_tv_capabilities` or `apple_tv_status`. Those
report `pyatv` state; screen capture is a separate path with its own errors.

---

## 10a. Screen Capture Boundary

Screen capture is observation, not control. Keep the two apart:

```text
control      AppleTVController → PyAtvGateway → ConnectionManager → pyatv
observation  ScreenCaptureService → ExternalScreenCaptureBackend → appletv-screenshot helper
```

They meet only in `composition.py` and the MCP lifespan context.

Hard boundary: `appletv_mcp` must never import `pymobiledevice3`, and it must not appear in
the root `pyproject.toml` or `uv.lock`. The helper lives in `sidecars/appletv-screenshot/`
as a separate `uv` project (not a workspace member) with its own lockfile and gates.

The helper contract is exit codes plus one PNG at `--output PATH`. Do not parse helper
stderr as an API. `HelperExitCode` in `infrastructure/screen_capture/contract.py` and the
helper's `exit_codes.py` must stay identical; `tests/contract/test_helper_contract.py`
compares them.

Rules for the backend:

- `asyncio.create_subprocess_exec`, never a shell, fixed argument list.
- All three standard streams detached (`DEVNULL`). MCP stdio owns the parent's stdout.
- Per-call private temporary directory, removed in `finally`.
- Timeout and cancellation stop the helper with terminate, wait, kill.
- Validate PNG structure without Pillow. Require the signature, IHDR first, at least
  one IDAT, a complete IEND, and positive dimensions. Enforce `max_image_bytes`.
  Do not check CRCs or decode pixels.
- Screenshots are ephemeral. Never cache, persist, or log image bytes.
- No black-frame heuristics and no DRM circumvention. A black frame is returned as captured.
- Capture is lazy. The MCP process starts and controls the TV with no helper installed.
  `doctor` reports `SKIP` for a missing helper, an optional `FAIL` for a helper contract
  mismatch or missing capture UDID, and never fails the process on those optional checks.
- One capture at a time through the service's own `asyncio.Lock`, not the controller's
  command lock.

---

## 11. Device Identity

The stable `pyatv` device identifier is authoritative.

Never identify the configured Apple TV solely by:

```text
display name
IP address
scan order
first result
```

Use the last-known host only as an optimization.

Required discovery strategy:

```text
stable identifier
      │
      ▼
preferred_host available?
      │
      ├── yes → targeted/unicast discovery
      │         └── verify identifier
      │
      └── failure/mismatch
                │
                ▼
       identifier-based discovery
                │
                ▼
        matching device found
                │
                ▼
       update preferred_host
```

If the old IP now belongs to another Apple TV, reject it.

If the correct Apple TV is rediscovered at a new IP, update and persist `preferred_host` without requiring re-pairing.

---

## 12. Pairing Credentials

Pairing is setup, not an agent operation.

Credentials must never:

- Become MCP parameters.
- Appear in MCP results.
- Appear in normal logs.
- Be copied into application config.
- Be committed in tests.
- Be exposed through a diagnostic command.

Use the pinned `pyatv 0.18.0` storage API.

Reuse storage compatible with the `atvremote` pairing flow.

For v0.1, the expected pairing path is based on:

```text
atvremote wizard
```

followed by application configuration.

---

## 13. Configuration

Use Pydantic v2.

Persist only application configuration such as:

```text
device_identifier
device_name
preferred_host
scan_timeout_seconds
command_timeout_seconds
```

For persisted/external input models, prefer:

```python
ConfigDict(extra="forbid")
```

unless compatibility requires otherwise.

Validation expectations:

```text
device_identifier       required and non-empty
preferred_host          optional, validated
scan_timeout_seconds    finite and > 0
command_timeout_seconds finite and > 0
```

Use `platformdirs` with application name `appletv-mcp` for application paths.

The configuration directory may be overridden with `APPLETV_MCP_CONFIG_DIR` (tests and unusual installs). Do not introduce other environment-variable prefixes.

Configuration writes should be atomic.

Prefer:

1. Validate.
2. Serialize.
3. Write a sibling temp file.
4. Flush appropriately.
5. `os.replace()` into place.

Do not risk truncating the canonical config on interrupted writes.

---

## 14. MCP Input Validation

Validate inputs before upstream execution.

At minimum:

```text
volume percent      0 <= x <= 100
seek position       >= 0
skip seconds         >= 0 and finite
button count         1..10
volume steps         1..10
app string           non-empty after trim
deep-link URL        syntactically valid scheme
```

Custom URL schemes are allowed.

Do not restrict deep links to HTTP/HTTPS.

Reject malformed URLs and control characters before passing them upstream.

---

## 15. App Resolution

Application resolution must be deterministic.

Given an app string:

1. Trim whitespace.
2. Reject empty input.
3. Exact bundle-ID match wins.
4. Otherwise use case-insensitive exact display-name matching.
5. If exactly one result exists, use it.
6. If multiple exact normalized names exist, return ambiguity.
7. If no exact match exists, return not found.
8. Suggested close matches are informational only.

Never fuzzy-launch the closest candidate.

An agent typo must not launch the wrong application.

---

## 16. Capability Handling

Maintain one centralized mapping between normalized operations and exact `pyatv 0.18.0` feature enums.

Verify every raw enum member against pinned references.

Do not scatter `FeatureName` checks throughout the application.

Normalize upstream states into:

```text
available
unknown
unavailable
unsupported
```

Required semantics:

```text
available
→ execute

unknown
→ attempt execution

unavailable
→ model-readable current-state failure

unsupported
→ model-readable device-capability failure
```

---

## 17. Connection Lifecycle

The MCP process must start even if the Apple TV is:

```text
asleep
off
rebooting
temporarily unreachable
offline
```

Device connection must therefore be lazy.

The connection manager owns:

- Discovery.
- Connect.
- Cached connection.
- Reconnect.
- Invalidation.
- Disconnect listeners.
- Shutdown.

Use one async lock for connection establishment.

Concurrent requests while disconnected must converge on one connection attempt.

Use a separate command lock for commands that may interfere with each other.

Shutdown must be idempotent.

Do not delete credentials during ordinary invalidation.

---

## 18. Timeouts

No device/network operation may hang forever.

Use modern Python 3.14 async timeout handling, preferably:

```python
async with asyncio.timeout(...):
    ...
```

Apply bounded timeouts to appropriate:

- Discovery.
- Connect.
- Power transitions.
- App operations.
- Device commands.

Avoid redundant nested timeouts without a reason.

Translate timeout failures into useful domain/tool errors.

---

## 19. Retry and Idempotency

Retry behavior is a correctness feature.

Centralize retry policy.

### May reconnect and retry once

Examples:

```text
status
capabilities
list_apps
absolute seek
absolute set_volume
power on
```

### Must not blindly replay after uncertain dispatch

Examples:

```text
remote navigation
double tap
hold
play_pause toggle
next
previous
relative skip
relative volume adjustment
deep-link / URL launch
power off after uncertain dispatch
```

If a connection fails after a replay-unsafe command may have been delivered:

1. Invalidate the connection.
2. Close/dispose the retained session without opening a replacement.
3. Do not replay the command.
4. Raise an uncertainty error.
5. Translate it into `ToolError`.

The same rule applies to the retry attempt: a safe-to-retry first failure may
reconnect once, but if the second dispatch is then uncertain, raise
`UncertainExecutionError` instead of a raw connection error.

Companion often wraps timeouts and dropped connections as `ProtocolError`. Translate
those back to `CommandTimeoutError` / `DeviceConnectionError` when the cause chain
or a stale connection listener says the transport failed. Only a protocol rejection
on a still-healthy session is `CommandFailedError`.

Error text should explain why retry did not occur.

This behavior requires tests.

---

## 20. Error Model

Use errors intentionally.

### `ToolError`

Use for model-recoverable operational failures:

```text
device unreachable
app not found
ambiguous app
feature unavailable
feature unsupported
keyboard not focused
timeout
uncertain non-idempotent execution
```

### `MCPError`

Use only when the MCP request itself should fail at the protocol layer.

The Apple TV being offline is not a protocol error.

### Unexpected Exceptions

Unexpected exceptions should:

- Produce server-side traceback.
- Be sanitized by the MCP SDK.
- Never expose credentials or keyboard text.

Do not convert unexpected exceptions into successful strings.

Never:

```python
except Exception:
    return "Something failed"
```

Use broad exception translation only at deliberate infrastructure boundaries where logging and mapping are correct.

---

## 21. Text Entry Privacy

Treat text sent to:

```text
apple_tv_set_text
```

as potentially sensitive.

Never log the actual value.

Allowed:

```python
logger.debug("Sending %d characters to Apple TV keyboard", len(text))
```

Forbidden:

```python
logger.info("Typing %s", text)
```

Do not include text-entry values in normal error strings.

Tests must assert that text values are absent from captured logs.

---

## 22. Logging and STDIO

Use:

```python
logger = logging.getLogger(__name__)
```

Do not use `print()` in the MCP serving path.

MCP stdio owns stdout.

Application logs belong on stderr.

Recommended defaults:

```text
appletv_mcp           INFO
pyatv                 WARNING
```

`--debug` raises `appletv_mcp` to DEBUG. Keep `pyatv` at WARNING. Companion logs full OPACK frames at DEBUG, including RTI keyboard payloads and pairing credentials; those cannot be redacted reliably after serialization.

Support explicit debug logging.

Never log:

```text
credentials
pairing blobs
raw storage
passwords
keyboard text
screenshot bytes
helper stdout/stderr
```

Log a screenshot only as its byte count and dimensions.

Centralize redaction when necessary.

---

## 23. MCP Server

Use a typed MCP lifespan.

Process-lifetime setup should create:

- Settings/config repository.
- `pyatv` storage.
- Connection manager.
- `AppleTVController`.

Do not eagerly connect to the Apple TV during server startup.

MCP tools must be thin wrappers.

Each tool should generally:

1. Accept typed/validated input.
2. Retrieve application service from lifespan context.
3. Call one semantic application operation.
4. Convert expected domain error to correct MCP error behavior.
5. Return a typed model.

Do not put discovery, retry, or raw `pyatv` logic in MCP tool functions.

---

## 24. Structured MCP Results

Every tool should return a stable typed result model unless naturally returning a list of typed models.

Avoid ad-hoc dictionaries and prose-only success responses.

Use Pydantic return types so MCP generates output schemas.

Treat output models as public API.

---

## 25. MCP Tool Annotations

Use accurate `ToolAnnotations`.

Read-only tools:

```text
read_only_hint=True
open_world_hint=False
```

Absolute/idempotent state changes:

```text
read_only_hint=False
destructive_hint=False
idempotent_hint=True
open_world_hint=False
```

Relative/toggle operations, deep-link launches, and `apple_tv_power`
(annotations cannot split ON vs OFF; power-off is replay-unsafe):

```text
idempotent_hint=False
```

Annotations are metadata, not security controls.

---

## 26. CLI

Implement:

```text
appletv-mcp configure
appletv-mcp doctor
appletv-mcp serve
```

CLI commands should reuse application/infrastructure services.

Do not duplicate Apple TV behavior in command modules. `doctor` must use the
same discovery path as the running server (preferred-host unicast, then
identifier fallback), not a multicast-only shortcut.

### `configure`

Must:

- Load `pyatv` storage.
- Discover candidates.
- Display stable identity.
- Select device.
- Save identifier/name/host.
- Verify connection.
- Display capability summary.
- Close cleanly.

### `doctor`

Must be non-destructive.

Check:

```text
configuration
storage
discovery
identifier match
connection
power capability
apps capability
navigation capability
playback capability
keyboard capability/state
volume capability
```

Use concise, screen-reader-friendly one-line diagnostics.

Exit non-zero on required failure.

### `serve`

Runs local MCP over stdio.

Normal stdout output is forbidden.

---

## 27. Testing Structure

Prefer:

```text
tests/
├── unit/
│   ├── domain/
│   ├── application/
│   └── infrastructure/
├── contract/
│   └── mcp/
├── integration/
│   └── live/
└── helpers/
```

Keep reusable fakes/factories in `tests/helpers/`.

Do not let `conftest.py` become a giant utility module.

Ordinary tests must not require Apple hardware.

---

## 28. Required Unit Coverage

Test at minimum:

### Configuration

- Valid configuration.
- Missing configuration.
- Malformed configuration.
- Extra fields rejected.
- Invalid timeouts.
- Atomic persistence.
- Host update.

### Discovery/Connection

- Preferred host success.
- Preferred host wrong-device rejection.
- Preferred host failure then identifier discovery.
- Identifier absent.
- IP change.
- Cached reuse.
- Simultaneous connection requests.
- Invalidation.
- Reconnect.
- Clean shutdown.
- Repeated shutdown.

### Capabilities

- Available.
- Unknown.
- Unavailable.
- Unsupported.
- Correct normalized mapping.

### Status

- Full metadata.
- Partial metadata.
- No media.
- Unknown power.
- No volume.
- No keyboard.
- `media_app`.
- Optional metadata missing.

### Applications

- Exact bundle ID.
- Exact name.
- Case-insensitive name.
- Ambiguous match.
- Missing app.
- Suggested candidate is not launched.

### Commands

- Every remote button.
- Every press style.
- Count sequencing.
- Partial completion.
- Playback actions.
- Seek.
- Skip.
- Absolute volume.
- Relative volume.
- Text.
- Empty text.
- Power.

### Retry

- Read retry success.
- Read retry failure.
- Safe absolute retry.
- Toggle not replayed.
- Navigation not replayed.
- Skip not replayed.
- Relative volume not replayed.
- Uncertain execution error.

### Privacy

- Credentials absent from logs.
- Text input absent from logs.

---

## 29. MCP Contract Tests

Use the MCP SDK in-memory client.

Do not require a subprocess for contract tests.

Verify exact tool inventory and, for every tool:

- Name.
- Description.
- Required arguments.
- Optional arguments.
- Enums.
- Numeric constraints.
- Input schema.
- Output schema.
- Tool annotations.
- Structured result shape.

Verify:

- Invalid input is rejected before application execution.
- `ToolError` becomes an error tool result.
- Server initializes without physical hardware.
- Server initialization performs no eager device connection.

These tests protect the public contract.

---

## 30. Live Integration Tests

Live Apple TV tests must be opt-in.

Require an explicit switch such as:

```text
APPLE_TV_INTEGRATION_TESTS=1
```

Ordinary:

```bash
uv run pytest
```

must not require hardware.

Live tests may verify:

- Discovery.
- Stable identifier.
- Connection.
- Status.
- Capabilities.
- Apps.
- Power.
- App launch.
- Deep link.
- Seek.
- Volume.
- Harmless text entry.
- Navigation.
- Playback.
- Reconnection.

Do not automatically run disruptive live-device actions in normal CI.

---

## 31. Python Style

Use modern Python 3.14.

Prefer:

```python
str | None
list[str]
dict[str, object]
enum.StrEnum
pathlib.Path
asyncio.timeout
dataclasses where appropriate
typing.Protocol where useful
```

Avoid old compatibility syntax such as:

```python
Optional[str]
List[str]
Dict[str, Any]
```

unless an upstream API or readability case justifies it.

Avoid `Any` outside narrow third-party boundaries.

Avoid `cast()` as a substitute for correct typing.

Avoid `# type: ignore` unless an upstream typing defect genuinely requires it; include a short reason.

Avoid global mutable state.

Avoid circular imports.

---

## 32. Async Rules

This is an async device-control application.

Do not:

- Use `time.sleep`.
- Block the event loop with sync network calls.
- Spawn unmanaged tasks.
- Leak tasks after tests.
- Hold locks across unrelated work.
- Create nested lock patterns likely to deadlock.

If creating a background task:

- Own it.
- Retain a handle.
- Define shutdown behavior.
- Test cancellation/cleanup.

Follow pinned `pyatv` lifecycle patterns.

---

## 33. Avoid Architecture Theater

Do not introduce unnecessary:

```text
dependency injection containers
service locators
command buses
event sourcing
plugin frameworks
custom middleware frameworks
factory-of-factory layers
home-grown Result monads
one-class-per-function patterns
```

unless a concrete requirement demands them.

Constructor injection and small protocols are sufficient.

Complexity belongs where the domain is genuinely complex:

```text
connection lifecycle
stable identity
retry safety
capability mapping
async concurrency
MCP contracts
```

Keep everything else simple.

---

## 34. No Incomplete Production Code

Do not leave production:

```text
TODO
FIXME
pass
NotImplementedError
placeholder values
fake capability data
hardcoded device IDs
hardcoded app lists
```

unless explicitly documented as an intentional extension point outside v0.1.

Search for these before finishing.

Tests may use fakes.

Production may not.

---

## 35. Documentation

Keep the root `README.md` current.

It should cover:

- Purpose.
- Architecture.
- Requirements.
- Installation.
- Pairing.
- Configure.
- Doctor.
- Serve.
- MCP host configuration.
- Tool inventory.
- Perception limitations.
- Troubleshooting.
- Development.
- Tests.
- Optional live tests.
- Screen capture setup, its separate pairing, and its limits (point-in-time, black frames).

Do not imply continuous screen visibility or foreground-app knowledge.

---

## 36. Checklist Discipline

`docs/apple-tv-mcp-spec/IMPLEMENTATION_CHECKLIST.md` is a living project tracker.

As work is genuinely completed:

- Mark the corresponding item complete.
- Do not mark hardware validation complete without hardware execution.
- Add a brief note when implementation differs materially from the original plan.
- Do not delete unfinished checklist items to make progress appear complete.

---

## 37. Quality Gates

Before considering work complete, run:

```bash
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

Run the same five commands inside `sidecars/appletv-screenshot/`.

Also run:

```bash
git diff --check
uv build --wheel
```

when Git is available, and confirm the wheel contains no `sidecars/` or
`appletv_screenshot` files and no `pymobiledevice3` requirement.

Do not weaken lint/type configuration to make failures disappear.

Fix root causes.

---

## 38. Final Repository Review

Before final handoff, search for:

```text
TODO
FIXME
NotImplementedError
pass
print(
type: ignore
noqa
Any
pymobiledevice3      (must never be imported under src/appletv_mcp)
shell=True
```

Review every result.

Not every match is automatically wrong, but every match must be intentional.

Also inspect for:

```text
credentials
passwords
pairing data
tokens
raw storage
keyboard text
screenshot files or image bytes in tests or fixtures (use a generated PNG, never a real capture)
```

Ensure nothing sensitive was accidentally committed or logged.

---

## 39. Definition of Done

A task is not done merely because code was written.

For implementation work, done means:

1. Behavior implemented.
2. Tests added or updated.
3. Relevant tests pass.
4. Ruff passes.
5. Ruff formatting passes.
6. Pyright passes.
7. Public contracts remain correct.
8. Documentation/checklist updated when applicable.
9. No secrets or sensitive text leak.
10. No unrelated regressions introduced.

For hardware-dependent functionality, distinguish:

```text
implemented
automatically tested with fakes
live-device verified
```

Do not conflate these states.

---

## 40. Agent Handoff Format

When completing a substantial development task, report:

### Changed

Summarize the implementation.

### Architecture

Call out important structural decisions.

### Validation

Report actual results for:

```text
ruff check
ruff format --check
pyright
pytest
```

Include test counts when available.

### Live validation

State whether a real Apple TV was used.

If not, say the live-device checks remain unexecuted.

### Deviations

List any deliberate deviation from `docs/apple-tv-mcp-spec/SPEC.md`.

### Remaining work

List only genuine remaining work.

Do not invent future tasks merely to pad the report.

---

## 41. Core Rule

Preserve the semantic agent-facing contract even when upstream implementation details change.

The agent should think in terms of:

```text
power
apps
playback
navigation
text
volume
status
capabilities
```

not:

```text
Companion
MRP
AirPlay
RAOP
```

Those protocols are infrastructure details.

Keep them there.
