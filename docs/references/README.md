# Apple TV Agent — Reference Corpus

This directory is intended to be dropped into the Apple TV MCP project and supplied to a coding agent as the authoritative reference corpus.

## Version baseline

- **pyatv:** 0.18.0
- **MCP Python SDK:** 2.2.0 (stable v2 line)
- **MCP protocol/docs:** 2026-07-28 revision

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
└── mcp-spec-2026-07-28/
    ├── README.md
    └── llms-full.md
```

## Agent guidance

1. Treat these versions as pinned unless the project owner explicitly asks to upgrade.
2. Prefer MCP Python SDK v2 examples using `MCPServer`; ignore v1/FastMCP-era code unless reading migration context.
3. For Apple TV control, prefer pyatv's public abstractions and feature checks instead of binding the MCP layer directly to Companion/AirPlay/MRP internals.
4. Keep protocol-specific details behind an `AppleTVController` or equivalent adapter so the MCP tool surface remains stable.
5. For a local Apple TV bridge, start with MCP over stdio unless there is a concrete reason to expose Streamable HTTP.
6. Do not use documentation from `master` to override behavior documented for these pinned stable releases.

## Provenance

The MCP files are the user's LLM-ready Markdown captures of the official MCP documentation. The pyatv documents are the Markdown files supplied in `pyatv.zip` and have been reorganized under the pinned 0.18.0 reference directory.
