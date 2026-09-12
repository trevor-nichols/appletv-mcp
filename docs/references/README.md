# Apple TV Agent — Reference Corpus

This directory is intended to be dropped into the Apple TV MCP project and supplied to a coding agent as the authoritative reference corpus.

## Version baseline

- **pyatv:** 0.18.0
- **MCP Python SDK:** 2.2.0 (stable v2 line)
- **MCP protocol/docs:** 2026-07-28 revision
- **pymobiledevice3:** 11.12.4 pinned by the screen-capture sidecar (`sidecars/appletv-screenshot/`). The captured docs under `pymobiledevice3/` carry no version marker; every sidecar call was checked against the installed 11.12.4 sources and type hints in addition to these pages.

## Layout

```text
references/
├── README.md
├── MANIFEST.sha256
├── pyatv-0.18.0/
│   ├── README.md
│   └── docs/
│       ├── getting_started.md
│       ├── concepts.md
│       ├── supported_features.md
│       ├── protocols.md
│       ├── tutorial.md
│       ├── atvremote.md
│       ├── atvscript.md
│       ├── atvlog.md
│       ├── atvproxy.md
│       └── documentation.md
├── mcp-python-sdk-2.2.0/
│   ├── README.md
│   └── llms-full.md
├── mcp-spec-2026-07-28/
│   ├── README.md
│   └── llms-full.md
└── pymobiledevice3/
    ├── index.md
    ├── installation.md
    ├── api/            # connection, dvt, capture, services, ...
    ├── guides/         # ios17-tunnels, network-stacks, troubleshooting, python-api, ...
    ├── assets/
    └── _hooks/
```

For screen capture, the pages that matter are `guides/ios17-tunnels.md` (pairing, the no-root
userspace default, and when `tunneld` is still required), `guides/network-stacks.md` (native
`remoted` on macOS and userspace PyTCP), `guides/python-api.md` (`PreferredRsdTunnel` versus
`UserspaceRsdTunnel`; the sidecar does not wrap those classes, see
`ADR-0001-screen-capture.md`), `api/connection.md`, `api/dvt.md` (`Screenshot`), and
`guides/troubleshooting.md` (`InvalidServiceError`, Developer Mode, DDI).
The working Wi-Fi Apple TV path is RemotePairing browse
(`get_remote_pairing_tunnel_services`) plus the userspace TUN and dial-plane.

## Agent guidance

1. Treat these versions as pinned unless the project owner explicitly asks to upgrade.
2. Prefer MCP Python SDK v2 examples using `MCPServer`; ignore v1/FastMCP-era code unless reading migration context.
3. For Apple TV control, prefer pyatv's public abstractions and feature checks instead of binding the MCP layer directly to Companion/AirPlay/MRP internals.
4. Keep protocol-specific details behind an `AppleTVController` or equivalent adapter so the MCP tool surface remains stable.
5. For a local Apple TV bridge, start with MCP over stdio unless there is a concrete reason to expose Streamable HTTP.
6. Do not use documentation from `master` to override behavior documented for these pinned stable releases.
7. `pymobiledevice3` belongs to the sidecar only. Never import it from `appletv_mcp`; the MCP server reaches it through the `appletv-screenshot` subprocess and its exit-code contract.

## Provenance

The MCP files are the user's LLM-ready Markdown captures of the official MCP documentation. The pyatv documents are the Markdown files supplied in `pyatv.zip` and have been reorganized under the pinned 0.18.0 reference directory. The pymobiledevice3 pages are the project's Markdown documentation source as captured on 2026-09-11 (repository commit `d014985`), including its mkdocs hooks and assets.

## Integrity

`MANIFEST.sha256` lists every file in this directory except itself. Verify with:

```bash
cd docs/references && sha256sum -c MANIFEST.sha256
```

Regenerate after any change:

```bash
cd docs/references && find . -type f ! -name MANIFEST.sha256 | LC_ALL=C sort | xargs sha256sum > MANIFEST.sha256
```
