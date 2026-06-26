type AnyRecord = Record<string, any>;

export function mcpRuntimeStatus(copy: AnyRecord, state: AnyRecord) {
  const mcpCopy = copy.settings.mcp || {};
  const runtime = state.mcp.runtime || {};
  if (runtime.connecting) {
    return mcpCopy.runtimeConnecting || "Connecting";
  }
  if (runtime.connected) {
    return mcpCopy.runtimeConnected || "Connected";
  }
  if (runtime.connect_failures) {
    return typeof mcpCopy.runtimeFailed === "function" ? mcpCopy.runtimeFailed(runtime.connect_failures) : `Failed ${runtime.connect_failures} times`;
  }
  return mcpCopy.runtimeDisconnected || "Disconnected";
}

export function mcpToolGroups(copy: AnyRecord, state: AnyRecord): AnyRecord[] {
  const toolNames = state.mcp.runtime?.tool_names || [];
  const servers = Array.isArray(state.mcp.servers) ? state.mcp.servers : [];
  const serverIds = servers.map((server: AnyRecord) => String(server.id || "").trim()).filter(Boolean);
  const groups = new Map<string, AnyRecord>();

  for (const server of servers) {
    const serverId = String(server.id || "").trim();
    if (!serverId) {
      continue;
    }
    groups.set(serverId, {
      serverId,
      serverName: server.name || serverId,
      expanded: state.mcpToolGroupsExpanded[serverId] === true,
      tools: [],
    });
  }

  for (const fullName of toolNames) {
    const normalized = String(fullName || "").trim();
    if (!normalized) {
      continue;
    }
    const withoutPrefix = normalized.startsWith("mcp_") ? normalized.slice(4) : normalized;
    const serverId = serverIds
      .filter((candidate) => withoutPrefix.startsWith(`${candidate}_`))
      .sort((left, right) => right.length - left.length)[0] || "unknown";
    const toolName = serverId === "unknown" ? withoutPrefix : withoutPrefix.slice(serverId.length + 1);
    if (!groups.has(serverId)) {
      groups.set(serverId, {
        serverId,
        serverName: serverId === "unknown" ? copy.settings.mcp?.unknownServer || "Unknown" : serverId,
        expanded: state.mcpToolGroupsExpanded[serverId] === true,
        tools: [],
      });
    }
    groups.get(serverId)?.tools.push({ fullName: normalized, name: toolName || normalized });
  }

  return (Array.from(groups.values()) as AnyRecord[])
    .map((group: AnyRecord) => ({
      serverId: group.serverId,
      serverName: group.serverName,
      expanded: group.expanded,
      tools: group.tools.sort((left: AnyRecord, right: AnyRecord) => left.name.localeCompare(right.name)),
    }))
    .filter((group) => group.tools.length > 0)
    .sort((left: AnyRecord, right: AnyRecord) => String(left.serverName).localeCompare(String(right.serverName)));
}
