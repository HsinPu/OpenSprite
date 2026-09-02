# Streamable HTTP MCP contract

## Scope

- Expand the MCP Server transport contract from local stdio-only to a strict
  discriminated union of `stdio` and `streamable-http`.
- Upgrade `.opensprite/config/mcp.json` to schema v2 while reading schema v1
  stdio records without rewriting them until the next successful mutation.
- Keep Streamable HTTP authentication, custom headers, OAuth, LAN endpoints,
  SSE and WebSocket outside this slice.

## Safety and compatibility

The Streamable HTTP record contains only a bounded URL. Secrets and arbitrary
headers are not accepted. Existing Server ids, enabled state, Tool ids, Tool
settings, approvals, receipts and Run events remain unchanged.
