# MCP Python SDK 2.2.0 references

Pinned target: **mcp 2.2.0**, the stable v2 SDK line.

`llms-full.md` is the project's LLM-ready Markdown capture of the official Python SDK documentation.

Implementation rules for this project:

- Use `from mcp.server import MCPServer`.
- Use `@mcp.tool()` with parentheses.
- Prefer typed tool inputs/outputs and SDK-generated schemas.
- For stdio servers, never write application logs to stdout; use stderr/logging.
- Treat v1 `FastMCP` examples as migration material, not current implementation guidance.
