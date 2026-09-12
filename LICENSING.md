# Licensing

This repository contains separately distributed components under
different open-source licenses.

| Component | Path | License |
| --- | --- | --- |
| Apple TV MCP | `src/appletv_mcp/` and the rest of this tree except the sidecar | MIT |
| Apple TV Screenshot | `sidecars/appletv-screenshot/` | GPL-3.0-or-later |

The root `LICENSE` file applies to Apple TV MCP.

The screenshot helper has its own license file at:

`sidecars/appletv-screenshot/LICENSE`

The screenshot helper depends on the GPL-3.0-or-later
`pymobiledevice3` project. It is not bundled into or imported by
the main Apple TV MCP package.

The two components communicate through a one-shot subprocess
interface (`appletv-screenshot capture --output PATH` plus exit codes).
