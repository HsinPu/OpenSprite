# Browser MCP Spike

This spike documents the fastest way to try browser automation before OpenSprite grows native browser tools.

## Goal

Use the existing MCP integration to prove the browser-control workflow without changing OpenSprite runtime code. This is a spike path only; the long-term path should be native `browser_*` tools so permissions, run traces, and completion gates can understand browser evidence directly.

## Example Configuration

Add a browser MCP server to `~/.opensprite/mcp_servers.json`:

```json
{
  "playwright": {
    "type": "stdio",
    "command": "npx.cmd",
    "args": ["-y", "@playwright/mcp@latest"],
    "tool_timeout": 60,
    "enabled_tools": ["*"]
  }
}
```

Then reload MCP from the Web UI settings or by restarting `opensprite gateway`.

## What To Evaluate

- Can the agent navigate, inspect, click, and type reliably enough for common tasks?
- Are the MCP tool names and schemas understandable in the model prompt?
- Do run traces show enough browser context for debugging?
- Does the final answer cite page URLs or titles when browser results provide external information?

## Expected Limitations

- MCP tools appear as `mcp_<server>_<tool>` instead of stable OpenSprite-native `browser_*` names.
- Browser outputs are not automatically first-class `TaskArtifact`s unless the MCP result format is parsed separately.
- Permission handling treats MCP browser tools as generic MCP/external-side-effect tools.
- Completion gates cannot reliably distinguish browser evidence from other MCP outputs.

## Native Follow-Up

Native browser support should use fixed tools such as `browser_navigate`, `browser_snapshot`, `browser_click`, `browser_type`, `browser_press`, `browser_scroll`, and `browser_back`. The first backend should wrap `agent-browser` local Chromium, then add CDP attach and cloud providers after the OpenSprite-native tool surface is stable.
