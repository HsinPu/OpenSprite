import { toPayloadSource } from "../composables/payloadBoundary";
import type { McpRuntimeView, McpServerView, McpSettings } from "../composables/useSettingsState";

type McpCopyRootPayload = {
  settings?: unknown;
};
type McpSettingsCopyPayload = {
  mcp?: unknown;
};
type McpCopyView = {
  runtimeConnecting?: unknown;
  runtimeConnected?: unknown;
  runtimeFailed?: unknown;
  runtimeDisconnected?: unknown;
  unknownServer?: unknown;
};
type McpSettingsView = Partial<McpSettings>;
type McpStateView = {
  mcp?: McpSettingsView;
  mcpToolGroupsExpanded?: Record<string, boolean>;
};
type McpToolView = {
  fullName: string;
  name: string;
};
export type McpToolGroup = {
  serverId: string;
  serverName: string;
  expanded: boolean;
  tools: McpToolView[];
};

function text(value: unknown, fallback = ""): string {
  return String(value || fallback);
}

function mcpCopyFor(copy: unknown): McpCopyView {
  const root = toPayloadSource<McpCopyRootPayload>(copy);
  const settings = toPayloadSource<McpSettingsCopyPayload>(root?.settings);
  return toPayloadSource<McpCopyView>(settings?.mcp) || {};
}

function mcpSettingsFor(state: McpStateView): McpSettingsView {
  return state.mcp ?? {};
}

function mcpRuntimeFor(state: McpStateView): McpRuntimeView {
  return mcpSettingsFor(state).runtime ?? { connected: false, connecting: false, connect_failures: 0, tool_names: [] };
}

function mcpServers(value: unknown): McpServerView[] {
  return Array.isArray(value)
    ? value.filter((server): server is McpServerView => server !== null && typeof server === "object" && !Array.isArray(server))
    : [];
}

function mcpToolNames(value: unknown): string[] {
  return Array.isArray(value) ? value.map((name) => String(name || "").trim()).filter(Boolean) : [];
}

function formatRuntimeFailure(formatter: unknown, failures: unknown): string {
  const count = Number(failures || 0);
  return typeof formatter === "function" ? String(formatter(count)) : `Failed ${count} times`;
}

export function mcpRuntimeStatus(copy: unknown, state: McpStateView): string {
  const mcpCopy = mcpCopyFor(copy);
  const runtime = mcpRuntimeFor(state);
  if (runtime.connecting) {
    return text(mcpCopy.runtimeConnecting, "Connecting");
  }
  if (runtime.connected) {
    return text(mcpCopy.runtimeConnected, "Connected");
  }
  if (runtime.connect_failures) {
    return formatRuntimeFailure(mcpCopy.runtimeFailed, runtime.connect_failures);
  }
  return text(mcpCopy.runtimeDisconnected, "Disconnected");
}

export function mcpToolGroups(copy: unknown, state: McpStateView): McpToolGroup[] {
  const mcpCopy = mcpCopyFor(copy);
  const mcp = mcpSettingsFor(state);
  const runtime = mcpRuntimeFor(state);
  const expanded = state.mcpToolGroupsExpanded ?? {};
  const servers = mcpServers(mcp.servers);
  const serverIds = servers.map((server) => String(server.id || "").trim()).filter(Boolean);
  const groups = new Map<string, McpToolGroup>();

  for (const server of servers) {
    const serverId = String(server.id || "").trim();
    if (!serverId) {
      continue;
    }
    groups.set(serverId, {
      serverId,
      serverName: text(server.name, serverId),
      expanded: expanded[serverId] === true,
      tools: [],
    });
  }

  for (const normalized of mcpToolNames(runtime.tool_names)) {
    const withoutPrefix = normalized.startsWith("mcp_") ? normalized.slice(4) : normalized;
    const serverId = serverIds
      .filter((candidate) => withoutPrefix.startsWith(`${candidate}_`))
      .sort((left, right) => right.length - left.length)[0] || "unknown";
    const toolName = serverId === "unknown" ? withoutPrefix : withoutPrefix.slice(serverId.length + 1);
    if (!groups.has(serverId)) {
      groups.set(serverId, {
        serverId,
        serverName: serverId === "unknown" ? text(mcpCopy.unknownServer, "Unknown") : serverId,
        expanded: expanded[serverId] === true,
        tools: [],
      });
    }
    groups.get(serverId)?.tools.push({ fullName: normalized, name: toolName || normalized });
  }

  return Array.from(groups.values())
    .map((group) => ({
      ...group,
      tools: [...group.tools].sort((left, right) => left.name.localeCompare(right.name)),
    }))
    .filter((group) => group.tools.length > 0)
    .sort((left, right) => left.serverName.localeCompare(right.serverName));
}
