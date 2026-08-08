"""Stable naming contract for MCP-backed tools."""


MCP_TOOL_NAME_PREFIX = "mcp_"


def build_mcp_tool_name(server_name: str, tool_name: str) -> str:
    """Return the registry name for one tool exposed by an MCP server."""
    return f"{MCP_TOOL_NAME_PREFIX}{server_name}_{tool_name}"
