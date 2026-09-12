# Apple TV MCP v0.2 — Screen Capture Extension Specification

**Project:** Apple TV MCP  
**Repository:** `trevor-nichols/appletv-mcp`  
**Baseline:** `main` after v0.1 merge  
**Feature:** Explicit Apple TV screen capture returned to MCP as image content  
**Status:** Implementation specification

---

## 1. Purpose

Extend Apple TV MCP from semantic control with blind navigation into semantic control with optional point-in-time visual observation.

The new capability must allow an MCP client/model to explicitly request a screenshot of the currently rendered Apple TV screen and receive that screenshot as native MCP image content.

The feature must preserve the existing architecture and must not turn the existing `AppleTVController`, `PyAtvGateway`, MCP server, or CLI modules into monolithic mixed-responsibility components.

The desired control loop is:

```text
AI Agent
   │
   ├── apple_tv_open_app(...)
   ├── apple_tv_press(...)
   │
   ├── apple_tv_screenshot()
   │          │
   │          ▼
   │      PNG ImageContent
   │          │
   ▼          ▼
reason about current visible screen
   │
   └── next semantic action
```

Screen capture is observation.

It does not replace semantic control.

---

## 2. Existing v0.1 Behavior Must Remain Stable

Do not regress or redesign the established control subsystem.

The following existing behavior remains authoritative:

```text
pyatv 0.18.0 owns Apple TV control
stable pyatv identifier owns control-device identity
preferred_host is only an optimization
control connection is lazy
control retry policy remains unchanged
non-idempotent/replay-unsafe operations remain protected
pairing credentials remain outside MCP
stdio remains the default MCP transport
```

Existing MCP tool names and parameters remain unchanged.

The screenshot work adds one public tool.

Do not casually refactor unrelated v0.1 behavior while implementing screen capture.

---

## 3. Public MCP Surface

v0.2 has exactly fourteen tools.

Existing thirteen:

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
```

New tool:

```text
apple_tv_screenshot
```

Do not introduce additional visual tools in this change.

Specifically do not add:

```text
apple_tv_observe
apple_tv_watch_screen
apple_tv_press_until_visible
apple_tv_find_element
apple_tv_click_element
apple_tv_ocr
apple_tv_visual_sequence
```

Those are possible future features after basic screenshot capture has proven stable.

---

## 4. `apple_tv_screenshot` Contract

### 4.1 Input

No model-facing arguments.

Conceptually:

```python
async def apple_tv_screenshot(ctx: Context[AppContext]) -> Image:
    ...
```

Do not expose:

```text
file path
device identifier
RemoteXPC identifier
image format
quality
crop rectangle
pymobiledevice3 options
tunnel selection
pairing data
```

The MCP caller should not know or care how the screenshot is obtained.

### 4.2 Output

Return one PNG image as native MCP image content.

Use the pinned MCP Python SDK media helper:

```python
from mcp.server.mcpserver import Image
```

Conceptual tool body:

```python
@mcp.tool(
    name="apple_tv_screenshot",
    annotations=ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    ),
    structured_output=False,
)
async def apple_tv_screenshot(
    ctx: Context[AppContext],
) -> Image:
    capture = await run_tool(
        lambda: screen_capture(ctx).capture()
    )

    return Image(
        data=capture.data,
        format="png",
    )
```

Do not manually base64-encode image data.

Do not return base64 inside text or JSON.

Do not return a local path and require the model to open the file separately.

The MCP SDK should perform the protocol conversion to `ImageContent`.

### 4.3 Structured output

The screenshot tool intentionally has:

```text
output_schema = None
structured_content = None
```

This is correct behavior for an MCP image result.

Do not invent a Pydantic result wrapper merely to force an output schema.

---

## 5. Visual Semantics

A screenshot represents the screen at one point in time.

It does not establish persistent knowledge about later screen state.

After an action such as:

```text
press
open app
seek
playback command
power command
```

a prior screenshot may be stale.

Server/model instructions must explicitly state:

```text
Use apple_tv_screenshot when current visible state matters.

A screenshot is point-in-time evidence.

Do not assume screen contents remain unchanged after another Apple TV action.

Prefer semantic Apple TV operations whenever they can accomplish the task directly.

Use screenshots primarily to inspect, navigate, and verify UI state.
```

The screenshot may support statements such as:

```text
"The Search tab is visible in this screenshot."
"Netflix appears highlighted in the latest screenshot."
```

It must not justify statements such as:

```text
"Netflix is still highlighted."
```

after intervening control actions unless another screenshot verifies it.

---

## 6. DRM / Protected Content

Screen capture must not attempt to bypass HDCP, FairPlay, DRM, protected surfaces, or any platform protection.

Protected video may appear:

```text
black
blank
redacted
partially absent
```

while surrounding playback controls or application chrome remain visible.

A valid PNG containing a black protected region is still a successful screenshot.

Do not implement heuristics that classify a black image as:

```text
TV off
capture failed
playback failed
device unreachable
```

unless another independent signal supports that conclusion.

Do not attempt DRM circumvention.

---

## 7. Architecture

Screen capture is a separate vertical slice from Apple TV control.

Required conceptual architecture:

```text
                         MCP
                          │
             ┌────────────┴────────────┐
             │                         │
             ▼                         ▼
    AppleTVController         ScreenCaptureService
             │                         │
             ▼                         ▼
       PyAtvGateway          ScreenCaptureBackend
             │                         │
             ▼                         ▼
          pyatv                 external process
             │                         │
             │                         ▼
             │                 screenshot sidecar
             │                         │
             │                    RemoteXPC/DVT
             │                         │
             └───────────── Apple TV ──┘
```

The control and capture subsystems meet at the composition root, not inside each other's infrastructure.

---

## 8. Required Repository Structure

Extend the current layered tree approximately as follows:

```text
src/
└── appletv_mcp/
    ├── domain/
    │   ├── errors.py
    │   └── models/
    │       └── screen.py
    │
    ├── application/
    │   ├── ports/
    │   │   └── screen_capture.py
    │   └── services/
    │       └── screen_capture.py
    │
    ├── infrastructure/
    │   ├── config/
    │   ├── observability/
    │   ├── pyatv/
    │   └── screen_capture/
    │       ├── __init__.py
    │       ├── external.py
    │       └── png.py
    │
    ├── interfaces/
    │   ├── mcp/
    │   │   ├── context.py
    │   │   ├── lifespan.py
    │   │   └── tools/
    │   │       └── screenshot.py
    │   └── cli/
    │       └── commands/
    │           └── doctor.py
    │
    └── composition.py
```

Do not create:

```text
vision.py
screenshot_everything.py
pymobiledevice.py
apple_tv_controller_and_screenshot.py
```

containing several layers of behavior.

Do not put RemoteXPC/pymobiledevice behavior in:

```text
AppleTVController
PyAtvGateway
ConnectionManager
interfaces/mcp/server.py
tools/remote.py
```

---

## 9. Layer Responsibilities

### 9.1 Domain

Domain owns vocabulary and expected operational failures.

Add a small screen model such as:

```python
class CapturedScreen(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    data: bytes
    mime_type: Literal["image/png"] = "image/png"
```

The domain model must not import:

```text
mcp
pyatv
pymobiledevice3
subprocess
filesystem infrastructure
```

Add specific operational errors as needed, for example:

```text
ScreenCaptureUnavailableError
ScreenCapturePairingRequiredError
ScreenCaptureTimeoutError
ScreenCaptureFailedError
ScreenCaptureInvalidImageError
```

All should inherit `AppleTVError` so the existing MCP `run_tool` boundary remains reusable.

### 9.2 Application port

Define a narrow backend protocol.

Conceptually:

```python
class ScreenCaptureBackend(Protocol):
    async def capture(self) -> CapturedScreen:
        ...
```

Do not expose tunnel or subprocess concepts through the application port.

### 9.3 Application service

Create a dedicated `ScreenCaptureService`.

Responsibilities:

```text
serialize simultaneous capture requests
delegate capture to the backend
provide one semantic application method
remain independent of MCP
remain independent of pymobiledevice3
```

Conceptually:

```python
class ScreenCaptureService:
    def __init__(self, backend: ScreenCaptureBackend) -> None:
        self._backend = backend
        self._lock = asyncio.Lock()

    async def capture(self) -> CapturedScreen:
        async with self._lock:
            return await self._backend.capture()
```

Do not add screenshot methods to `AppleTVController`.

### 9.4 Infrastructure

`infrastructure/screen_capture/` owns:

```text
external process execution
helper executable resolution
timeouts
temporary files
PNG validation
output-size validation
sidecar exit-code mapping
process cleanup
```

No other layer should know how the screenshot is physically produced.

### 9.5 MCP interface

`tools/screenshot.py` should contain only:

```text
tool metadata
context access
application service call
conversion of CapturedScreen -> MCP Image
```

It must not:

```text
spawn processes
open tunnels
read temp files
know pymobiledevice3
parse PNG
perform pairing
```

---

## 10. External Sidecar Boundary

The main `appletv-mcp` Python package must not import `pymobiledevice3`.

Do not add `pymobiledevice3` to:

```text
pyproject.toml dependencies
uv.lock as an appletv-mcp production dependency
src/appletv_mcp imports
```

The working screenshot implementation remains an external process.

This preserves:

```text
dependency isolation
protocol isolation
failure isolation
the existing pyatv control stack
a clean licensing boundary
future backend replaceability
```

This architectural separation is intentional.

It is not a legal conclusion regarding GPL obligations. If the sidecar is distributed, license obligations should be reviewed separately.

---

## 11. Sidecar Contract

The production integration must not depend on:

```text
/tmp/appletv-screenshot/screen.png
a shared fixed filename
the current working directory
scan order
the first Apple TV found
```

Harden the existing proof-of-concept behind a stable executable contract.

Canonical executable name:

```text
appletv-screenshot
```

Recommended one-shot interface:

```bash
appletv-screenshot capture --output /absolute/private/temp/path/screen.png
```

Successful behavior:

```text
exit code 0
output file exists
output file contains one PNG screenshot
```

The sidecar owns:

```text
pymobiledevice3
RemotePairing records
RemoteXPC discovery
userspace/native tunnel selection
DVT provider lifecycle
takeScreenshot invocation
deterministic target selection
tunnel cleanup
```

The main MCP owns none of those concerns.

The sidecar must be configured to one specific Apple TV.

It must never silently choose:

```text
first discovered device
first pair record
first network result
```

when multiple candidates exist.

Ambiguity must fail rather than capture another device.

---

## 12. Sidecar Versioning

Record the exact version of `pymobiledevice3` used by the already-working proof-of-concept.

Pin that version in the sidecar's own environment.

Do not automatically upgrade it merely because a newer release exists.

The Apple TV MCP repository should document:

```text
sidecar executable contract version
tested pymobiledevice3 version
tested tvOS version
tested host OS
```

without making pymobiledevice3 a production dependency of the MCP package.

---

## 13. Screen-Capture Configuration

Extend application settings with a cohesive nested model.

Recommended shape:

```python
class ScreenCaptureSettings(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    command: str = "appletv-screenshot"
    timeout_seconds: float = Field(
        default=20.0,
        gt=0,
        le=60,
    )
    max_image_bytes: int = Field(
        default=33_554_432,
        gt=0,
    )
```

Then:

```python
class Settings(BaseModel):
    ...
    screen_capture: ScreenCaptureSettings = Field(
        default_factory=ScreenCaptureSettings
    )
```

Existing v0.1 configuration files must remain valid.

Do not put in this application config:

```text
RemoteXPC private keys
pairing secrets
pymobiledevice3 pair records
DVT credentials
PIN values
```

Those stay under the external sidecar/pymobiledevice3 ownership.

---

## 14. External Process Execution

Use:

```python
asyncio.create_subprocess_exec
```

Never use:

```python
shell=True
os.system
shell command concatenation
```

Model input must never influence executable paths or command arguments.

For each capture:

1. Resolve the configured executable.
2. Create a unique private temporary directory.
3. Construct a unique output path inside it.
4. Start the helper with a fixed argument shape.
5. Apply the configured timeout.
6. Await process completion.
7. Require exit code `0`.
8. Require the expected output file.
9. Validate size before loading.
10. Read bytes.
11. Validate PNG.
12. Return `CapturedScreen`.
13. Remove temporary artifacts in `finally`.

On cancellation or timeout:

```text
terminate child
wait for child
escalate to kill if necessary
clean temporary directory
raise domain error
```

Do not leave orphan screenshot/tunnel processes.

---

## 15. Screenshot File Handling

Do not retain screenshots on disk after the tool finishes.

A screenshot may contain sensitive information such as:

```text
account names
notifications
search queries
email addresses
QR codes
authentication prompts
media history
```

Default behavior must be ephemeral.

Do not:

```text
cache screenshots
write screenshots to application config
write screenshots to logs
log image bytes
log base64
keep a "latest screenshot" file
```

unless a later feature explicitly requires persistent capture and has a separate privacy design.

The only disk use permitted in v0.2 is a private per-call temporary file required by the external sidecar contract.

---

## 16. PNG Validation

Before returning a screenshot:

- Require non-empty bytes.
- Require size <= configured `max_image_bytes`.
- Require PNG signature:

```python
b"\x89PNG\r\n\x1a\n"
```

- Reject malformed/non-PNG output.
- Do not re-encode or resize the image in v0.2.

Do not add Pillow or another imaging dependency solely for the initial screenshot feature.

Native framebuffer bytes should pass through unchanged once validated.

---

## 17. Timeouts and Concurrency

Screen capture has its own timeout.

Do not reuse:

```text
scan_timeout_seconds
command_timeout_seconds
```

because creating a RemoteXPC tunnel and DVT session has different latency characteristics.

Default:

```text
20 seconds
```

Only one screenshot capture may execute at a time per MCP process.

Use a dedicated screen-capture lock.

Do not use the `AppleTVController` command lock.

Control operations and screenshot operations are separate subsystems.

---

## 18. Lazy Availability

The MCP server must start normally when:

```text
pymobiledevice3 is absent
sidecar is absent
developer pairing is absent
Apple TV is offline
RemoteXPC is unavailable
```

Screen capture is lazy.

Failure of optional screen capture must not make:

```text
apple_tv_status
apple_tv_open_app
apple_tv_press
playback
volume
```

unavailable.

Calling `apple_tv_screenshot` when the backend is unavailable should return a clear `ToolError`.

---

## 19. Error Behavior

Expected examples:

### Helper missing

```text
Screen capture is unavailable because the configured screenshot helper
could not be found. Run `appletv-mcp doctor` and configure the external
screen-capture sidecar.
```

### Developer pairing unavailable

```text
Screen capture requires developer/RemoteXPC pairing for the configured
Apple TV. Re-run the screen-capture pairing flow outside MCP.
```

### Timeout

```text
Apple TV screen capture timed out before a screenshot was returned.
```

### Invalid helper output

```text
The screen-capture helper completed but did not return a valid PNG image.
```

Do not return raw Python tracebacks or raw sidecar stderr to the model.

Do not expose pair records or credentials when formatting errors.

---

## 20. Doctor Integration

Extend:

```bash
appletv-mcp doctor
```

with optional screen-capture diagnostics.

Suggested output:

```text
OK   Configuration
OK   pyatv storage
OK   Device discovery
OK   Control connection
OK   Screen capture helper
OK   Screen capture
```

If screen capture is not installed/configured, control diagnostics should still succeed.

Use an explicitly nonfatal status such as:

```text
SKIP Screen capture helper — optional backend not available
```

Do not make a missing optional screenshot sidecar cause the entire control-only doctor command to exit nonzero.

If the helper exists, doctor may perform one read-only capture and discard the bytes after validating them.

---

## 21. Capabilities Tool

Do **not** add screenshot to `NormalizedOperation`, the pyatv `FEATURE_MAP`, or the existing `AppleTVCapabilities` model in this implementation.

That existing path represents semantic control capabilities surfaced through pyatv.

Forcing an external DVT backend into that mapping would unnecessarily couple two independent infrastructures.

For v0.2:

```text
apple_tv_capabilities
    = control capability snapshot

apple_tv_screenshot
    = independent optional observation capability
```

Availability is communicated through:

```text
tool success/error
doctor
documentation
```

A future version may introduce an application-level capability aggregator if multiple observation backends justify it.

Do not perform that refactor now.

---

## 22. MCP Context and Composition

Extend runtime composition rather than hiding global state.

Conceptually:

```python
@dataclass
class Runtime:
    settings_repository: FileSettingsRepository
    storage: PyAtvStorageAdapter
    connection_manager: ConnectionManager
    controller: AppleTVController
    screen_capture: ScreenCaptureService
```

And:

```python
@dataclass
class AppContext:
    controller: AppleTVController
    screen_capture: ScreenCaptureService
    runtime: Runtime | None = None
```

Add a context helper:

```python
def screen_capture(
    ctx: Context[AppContext],
) -> ScreenCaptureService:
    return ctx.request_context.lifespan_context.screen_capture
```

Do not turn `Runtime` into a generic service locator.

Explicit typed fields remain preferable.

---

## 23. Lifecycle

v0.2 uses one-shot screen capture.

Each call:

```text
spawn helper
open tunnel inside helper
capture
close tunnel
exit helper
```

Do not create a persistent:

```text
pymobiledevice3 daemon
RemoteXPC daemon
DVT session pool
background screenshot loop
screen stream
```

in this release.

Correctness and deterministic cleanup come before screenshot latency.

A future version may add a persistent capture sidecar if measurements show one-shot tunnel startup is too expensive.

---

## 24. Server Instructions

Replace the old absolute statement:

```text
The server cannot see the Apple TV screen.
```

with semantics like:

```text
The server does not continuously observe the Apple TV screen.

When screen capture is configured, use `apple_tv_screenshot` to obtain a
point-in-time image of the currently rendered Apple TV screen.

A screenshot may become stale after any subsequent action.

Prefer semantic app, playback, seek, text, power, and volume tools over
visual navigation when possible.

Remote button presses remain non-idempotent. When using them for UI
navigation, screenshots may be used before or after presses to inspect or
verify visible state.

Protected DRM video may appear black in screenshots. Do not infer that the
TV is off or playback failed solely from a black protected video region.

`media_app` remains the application associated with current media metadata
and is not independently a guaranteed foreground-app signal.
```

---

## 25. Existing Tool Documentation

Update descriptions that currently say navigation is completely blind.

For `apple_tv_press`, explain:

```text
The press itself has no visual feedback.
Use apple_tv_screenshot separately when visible UI state needs to be
inspected or verified.
```

For `apple_tv_status`, remove the absolute statement that the server cannot see the screen.

Do not imply that status automatically performs screenshot capture.

---

## 26. MCP Contract Tests

Update exact tool inventory from 13 to 14.

Add:

```text
apple_tv_screenshot
```

Contract test requirements:

1. Tool appears exactly once.
2. Tool accepts no model arguments.
3. `read_only_hint=True`.
4. `destructive_hint=False`.
5. `idempotent_hint=True`.
6. `open_world_hint=False`.
7. Calling it returns exactly one `ImageContent`.
8. `ImageContent.mime_type == "image/png"`.
9. Base64-decoding `ImageContent.data` produces the exact fake PNG bytes.
10. `structured_content is None`.
11. `output_schema is None`.

The existing test that requires an output schema for every tool must be changed.

It should require output schemas for structured tools and explicitly assert the screenshot tool has no output schema.

Do not weaken output-schema checking globally.

---

## 27. Unit Tests — Application

Test `ScreenCaptureService` with a fake backend.

Required behavior:

```text
returns captured bytes
serializes concurrent captures
propagates expected domain errors
does not call control gateway
does not mutate Apple TV state
```

---

## 28. Unit Tests — Infrastructure

Test external screenshot adapter without a real Apple TV.

Required cases:

```text
successful PNG
missing executable
nonzero helper exit
timeout
helper cancellation
output file missing
empty file
invalid PNG signature
oversized PNG
temporary directory cleanup
child-process cleanup
stderr not exposed to model
```

Use a fake executable/script fixture.

Do not mock the entire adapter so thoroughly that subprocess semantics are untested.

---

## 29. Live Integration Test

Existing live tests remain gated by:

```text
APPLE_TV_INTEGRATION_TESTS=1
```

Add one read-only live screenshot test when the external sidecar is available.

It should:

1. Invoke the real screen-capture service.
2. Assert capture succeeds.
3. Assert PNG signature.
4. Assert nonzero size.
5. Discard bytes.
6. Perform no Apple TV write operation.

It does not require:

```text
APPLE_TV_LIVE_WRITES=1
```

because screenshot is observational.

If the sidecar is not configured, skip with a clear reason rather than failing unrelated control integration tests.

---

## 30. MCP End-to-End Visual Test

Add a hardware-only manual validation step:

```text
1. Open Apple TV Home.
2. Call apple_tv_screenshot.
3. Verify MCP host renders the image.
4. Press one directional button.
5. Capture again.
6. Verify the second screenshot visibly reflects the new state.
7. Open an application semantically.
8. Capture again.
9. Verify app UI is visible.
10. Start protected content if available.
11. Confirm protected video may be black without crashing capture.
12. Verify another screenshot still succeeds afterward.
```

This is the acceptance test for the visual feedback loop.

---

## 31. Privacy

Treat screenshot data as potentially sensitive.

The server must not:

```text
log screenshot bytes
log screenshot base64
persist captures
attach captures to ordinary status responses
capture periodically
capture at startup
capture after every command automatically
```

The image reaches the MCP client only because `apple_tv_screenshot` was explicitly called.

Pairing credentials remain outside the model-facing surface.

---

## 32. Logging

Application debug logging may include:

```text
screen capture requested
helper started
helper completed
capture byte count
capture duration
exit code
```

It must not include:

```text
image bytes
base64
raw pair records
PINs
RemoteXPC secrets
raw helper stderr if it may contain sensitive protocol data
```

Continue to keep the upstream `pyatv` logger at WARNING.

The external screenshot sidecar should also avoid verbose protocol/debug logging in normal operation.

---

## 33. Dependency Rules

Do not add an image-processing library in v0.2.

Do not add `pymobiledevice3` to the Apple TV MCP dependency graph.

Allowed new production code should rely primarily on:

```text
Python standard library
existing MCP SDK
existing Pydantic dependency
existing application infrastructure
```

The sidecar is an external runtime prerequisite only for screenshot functionality.

---

## 34. Module Size

Preserve the repository's existing cohesion rule.

Treat roughly 250–350 substantive lines as a design-review threshold.

Do not add screenshot code to already-large control modules merely because they are convenient import locations.

Expected screenshot implementation should remain distributed by responsibility:

```text
domain model/errors
application port/service
infrastructure adapter/PNG validation
MCP tool
composition
doctor integration
tests
```

Avoid both:

```text
one 500-line screenshot module
twenty one-function abstraction files
```

---

## 35. Current SPEC Architecture Correction

While implementing v0.2, update the main repository structure shown in:

```text
docs/apple-tv-mcp-spec/SPEC.md
```

The existing flat package example is stale.

Replace it with the real layered structure already used by `main`.

Do not redesign the working code to match the stale diagram.

Documentation should be brought into alignment with the implementation.

---

## 36. Files That Must Be Updated

At minimum review and update:

```text
AGENTS.md
README.md
docs/apple-tv-mcp-spec/SPEC.md
docs/apple-tv-mcp-spec/IMPLEMENTATION_CHECKLIST.md

src/appletv_mcp/domain/errors.py
src/appletv_mcp/domain/models/settings.py
src/appletv_mcp/composition.py

src/appletv_mcp/application/ports/
src/appletv_mcp/application/services/
src/appletv_mcp/infrastructure/screen_capture/

src/appletv_mcp/interfaces/mcp/context.py
src/appletv_mcp/interfaces/mcp/instructions.py
src/appletv_mcp/interfaces/mcp/lifespan.py
src/appletv_mcp/interfaces/mcp/tools/__init__.py
src/appletv_mcp/interfaces/mcp/tools/screenshot.py

src/appletv_mcp/interfaces/cli/commands/doctor.py

tests/contract/mcp/
tests/unit/application/
tests/unit/infrastructure/
tests/integration/live/
```

Do not touch unrelated modules without a concrete reason.

---

## 37. Versioning

This is a new public MCP capability.

Use:

```text
0.2.0
```

for the release containing screen capture.

Update the package/server version consistently.

Do not change tool names or existing result fields as part of the version bump.

---

## 38. Non-Goals for v0.2

Explicitly out of scope:

```text
continuous screen streaming
video capture
OCR
UI hierarchy extraction
focus-element APIs
XCUITest automation
automatic visual navigation
press-until-visible macros
persistent DVT tunnel pooling
HDMI capture
camera capture
DRM bypass
screenshot history
screenshot caching
multi-TV visual routing
remote Internet screen exposure
```

The v0.2 primitive is deliberately small:

```text
take one screenshot
return one image
```

---

## 39. Future Direction

Once v0.2 is proven against real hardware, later versions may evaluate:

```text
persistent sidecar / tunnel reuse
apple_tv_observe combining screenshot + status
UI hierarchy / accessibility metadata
agent-directed screenshot → action → screenshot loops
visual verification helpers
multiple screen-capture backends
HDMI/camera fallback backends
```

None of these should be pre-built now.

Keep the first visual primitive reliable and composable.

---

## 40. Quality Gates

Before completion run:

```bash
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
git diff --check
```

Also verify:

```text
no pymobiledevice3 import in src/appletv_mcp
no pymobiledevice3 production dependency in pyproject.toml
no hard-coded /tmp/appletv-screenshot path
no shared screen.png
no shell=True
no screenshot bytes/base64 in logs
no added screenshot logic inside AppleTVController
no added screenshot logic inside PyAtvGateway
```

Build/package smoke test:

```bash
uv build
```

Verify the wheel contains only Apple TV MCP package code and does not bundle the external screenshot sidecar or pymobiledevice3.

---

## 41. Acceptance Criteria

The feature is complete only when all of the following are true:

1. Existing thirteen tools continue to work unchanged.
2. `apple_tv_screenshot` is the fourteenth public tool.
3. Tool takes no model-facing arguments.
4. Tool returns native MCP `ImageContent` as PNG.
5. Tool has no structured output schema by design.
6. MCP host can visibly render the returned screenshot.
7. Apple TV MCP does not import pymobiledevice3.
8. pymobiledevice3 is not an Apple TV MCP production dependency.
9. Screenshot backend is separately replaceable.
10. Missing screenshot backend does not prevent MCP startup.
11. Missing screenshot backend does not break control tools.
12. Capture is bounded by its own timeout.
13. Concurrent screenshot calls are serialized.
14. Screenshot temporary files are unique and deleted.
15. Screenshot bytes are never logged.
16. Pairing credentials are never returned/logged.
17. Invalid/non-PNG output becomes a model-readable ToolError.
18. DRM-black video is not treated as a capture failure.
19. Existing MCP structured-output contract tests remain strict.
20. Screenshot-specific MCP media contract tests pass.
21. Existing unit and contract suites pass.
22. Live read-only screenshot test passes on the paired Apple TV.
23. Screenshot → remote action → screenshot works manually.
24. README and server instructions accurately describe point-in-time visual observation.
25. Main SPEC's stale flat architecture diagram is corrected.
26. No new monolithic production module is created.
27. Package builds successfully.
28. Hardware validation and known limitations are documented.

---

## 42. Final Implementation Report

When finished, the implementation agent must report:

### Architecture

Describe the new screen-capture vertical slice and confirm it is independent of pyatv control infrastructure.

### Public contract

Report the exact fourteen MCP tools and screenshot annotations.

### External backend

Report:

```text
sidecar executable
sidecar contract
pymobiledevice3 version actually tested
tvOS version tested
host OS tested
```

Do not report pairing credentials.

### Validation

Report exact results for:

```text
uv sync --locked
ruff check
ruff format --check
pyright
pytest
uv build
git diff --check
MCP screenshot contract test
```

### Hardware validation

Report whether:

```text
real screenshot capture
MCP image rendering
screenshot → action → screenshot
DRM-black behavior
restart/reconnect
```

were actually tested.

Do not claim hardware validation that was not performed.

### Deviations

List every deliberate deviation from this specification and explain why.

---

## 43. Core Rule

Apple TV MCP now has two intentionally separate capabilities:

```text
Control = pyatv
Observation = external screen-capture backend
```

Keep those boundaries explicit.

The MCP layer composes them for the model.

Do not merge the underlying protocols, credentials, connection lifecycles, or implementation dependencies merely because both operate on the same Apple TV.