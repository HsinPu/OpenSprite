# Offline MCP Tool settings

The frontend Tool settings loader now preserves valid `mcp_` Tool ids while
their Server is offline, matching the backend schema-v1 settings contract.
Unknown non-MCP ids still fail closed as a malformed response. A hook regression
test proves an offline MCP selection remains in confirmed settings without
appearing as a local-service network failure.
