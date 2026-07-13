import { normalizeMcpSettings, normalizeMcpTransport, type McpTransportType } from "./settingsNormalizers";
import { toPayloadSource } from "./payloadBoundary";
import type { McpForm, McpRuntimeView, McpServerView, McpSettings } from "./useSettingsState";

type RequestSettingsJson = (pathname: string, options?: RequestInit) => Promise<unknown>;
type McpSettingsPayload = {
  servers?: unknown;
  runtime?: unknown;
  reload_message?: unknown;
};
type McpImportedServerPayload = {
  id?: unknown;
  name?: unknown;
  server_id?: unknown;
  server_name?: unknown;
  serverId?: unknown;
  serverName?: unknown;
  type?: unknown;
  transport_type?: unknown;
  transport?: unknown;
  command?: unknown;
  args?: unknown;
  url?: unknown;
  tool_timeout?: unknown;
  toolTimeout?: unknown;
  enabled_tools?: unknown;
  enabledTools?: unknown;
  env?: unknown;
  headers?: unknown;
};
type McpImportedServerMapPayload = {
  [serverId: string]: unknown;
};
type McpImportedJsonPayload = {
  [key: string]: unknown;
};
type McpKeyValuePayload = {
  [key: string]: unknown;
};
type ExtractedMcpServer = {
  serverId: string;
  server: McpImportedServerPayload;
};
type McpServerPayload = {
  server_id: string;
  type: McpTransportType;
  command: string;
  args: string[];
  url: string;
  tool_timeout: number;
  enabled_tools: string[];
  env?: McpKeyValuePayload;
  headers?: McpKeyValuePayload;
};

interface McpSettingsState {
  mcpLoading: boolean;
  mcpError: string;
  mcpNotice: string;
  mcpToolGroupsExpanded: Record<string, boolean>;
  mcp: McpSettings;
  mcpForm: McpForm;
}

interface McpSettingsCopy {
  notices: {
    mcpJsonInvalid: (fieldLabel: string) => string;
    mcpJsonSingleServer: string;
    mcpJsonEditingMismatch: string;
    mcpJsonApplied: string;
    mcpLoadFailed: string;
    mcpServerIdRequired: string;
    mcpCommandRequired: string;
    mcpUrlRequired: string;
    mcpSaved: string;
    mcpSaveFailed: string;
    mcpRemoved: string;
    mcpRemoveFailed: string;
    mcpReloaded: string;
    mcpReloadFailed: string;
  };
  settings: {
    mcp: {
      configJson: string;
      env: string;
      headers: string;
    };
  };
}

type SettingsActionContext = {
  settingsState: McpSettingsState;
  requestSettingsJson: RequestSettingsJson;
  copy: { value: McpSettingsCopy };
  setSettingsSuccess: (key: string, message: string) => void;
};

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "";
}

function optionalText(value: unknown): string {
  return String(value || "").trim();
}

function toMcpSettingsPayload(value: unknown): McpSettingsPayload | null {
  const payload = toPayloadSource<McpSettingsPayload>(value);
  return payload
    ? {
        servers: payload.servers,
        runtime: payload.runtime,
        reload_message: payload.reload_message,
      }
    : null;
}

function toMcpImportedServerPayload(value: unknown): McpImportedServerPayload | null {
  const payload = toPayloadSource<McpImportedServerPayload>(value);
  return payload
    ? {
        id: payload.id,
        name: payload.name,
        server_id: payload.server_id,
        server_name: payload.server_name,
        serverId: payload.serverId,
        serverName: payload.serverName,
        type: payload.type,
        transport_type: payload.transport_type,
        transport: payload.transport,
        command: payload.command,
        args: payload.args,
        url: payload.url,
        tool_timeout: payload.tool_timeout,
        toolTimeout: payload.toolTimeout,
        enabled_tools: payload.enabled_tools,
        enabledTools: payload.enabledTools,
        env: payload.env,
        headers: payload.headers,
      }
    : null;
}

function toMcpImportedServerMapPayload(value: unknown): McpImportedServerMapPayload | null {
  return toPayloadSource<McpImportedServerMapPayload>(value);
}

function textList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => optionalText(item)).filter(Boolean) : [];
}

function optionalNumber(value: unknown): number | undefined {
  if (value === undefined || value === null || value === "") {
    return undefined;
  }
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : undefined;
}

function normalizeMcpRuntime(value: unknown, fallbackRuntime: McpRuntimeView): McpRuntimeView {
  const runtime = toPayloadSource<McpRuntimeView>(value);
  if (!runtime || Object.keys(runtime).length === 0) {
    return fallbackRuntime;
  }
  return {
    connected: Boolean(runtime.connected),
    connecting: Boolean(runtime.connecting),
    connect_failures: Number(runtime.connect_failures || 0),
    retry_after: optionalNumber(runtime.retry_after),
    tool_names: textList(runtime.tool_names),
  };
}

function normalizeMcpServerView(value: unknown): McpServerView | null {
  const server = toPayloadSource<McpServerView>(value);
  if (!server) {
    return null;
  }
  return {
    id: optionalText(server.id),
    name: optionalText(server.name),
    type: optionalText(server.type),
    command: optionalText(server.command),
    args: textList(server.args),
    url: optionalText(server.url),
    tool_timeout: optionalNumber(server.tool_timeout),
    enabled_tools: textList(server.enabled_tools),
    env_configured: server.env_configured === undefined ? undefined : Boolean(server.env_configured),
    env_keys: textList(server.env_keys),
    headers_configured: server.headers_configured === undefined ? undefined : Boolean(server.headers_configured),
    headers_keys: textList(server.headers_keys),
  };
}

function normalizeMcpServerList(value: unknown): McpServerView[] {
  return Array.isArray(value)
    ? value.map(normalizeMcpServerView).filter((server): server is McpServerView => server !== null)
    : [];
}

function normalizeMcpSettingsView(payload: McpSettingsPayload, fallbackRuntime: McpRuntimeView): McpSettings {
  const normalized = normalizeMcpSettings(payload, fallbackRuntime);
  return {
    servers: normalizeMcpServerList(normalized.servers),
    runtime: normalizeMcpRuntime(normalized.runtime, fallbackRuntime),
  };
}

function parseLines(value: unknown): string[] {
  return String(value || "")
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseListText(value: unknown, fallback: string[] = []): string[] {
  const items = String(value || "")
    .replace(/,/g, "\n")
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
  return items.length ? items : fallback;
}

function formatJsonObject(value: unknown): string {
  return toPayloadSource<McpKeyValuePayload>(value)
    ? JSON.stringify(value, null, 2)
    : "";
}

function formatListField(value: unknown, fallback = ""): string {
  if (Array.isArray(value)) {
    return value.map((item) => String(item || "").trim()).filter(Boolean).join("\n");
  }
  if (typeof value === "string") {
    return value.trim();
  }
  return fallback;
}

function getMcpServerMap(parsed: McpImportedJsonPayload): McpImportedServerMapPayload | null {
  return toMcpImportedServerMapPayload(parsed.mcpServers)
    || toMcpImportedServerMapPayload(parsed.mcp_servers)
    || toMcpImportedServerMapPayload(parsed.servers);
}

function serverIdFromJson(server: McpImportedServerPayload): string {
  return optionalText(server.id || server.name || server.server_id || server.server_name || server.serverId || server.serverName);
}

export function useMcpSettingsActions({ settingsState, requestSettingsJson, copy, setSettingsSuccess }: SettingsActionContext) {
  function parseOptionalJsonObject(value: unknown, fieldLabel: string): McpKeyValuePayload | null | undefined {
    const text = String(value || "").trim();
    if (!text) {
      return null;
    }
    try {
      const parsed = JSON.parse(text);
      const parsedObject = toPayloadSource<McpKeyValuePayload>(parsed);
      if (!parsedObject) {
        throw new Error("not object");
      }
      return parsedObject;
    } catch {
      settingsState.mcpError = copy.value.notices.mcpJsonInvalid(fieldLabel);
      return undefined;
    }
  }

  function extractMcpServerFromJson(parsed: unknown): ExtractedMcpServer | null {
    const parsedObject = toPayloadSource<McpImportedJsonPayload>(parsed);
    if (!parsedObject) {
      settingsState.mcpError = copy.value.notices.mcpJsonInvalid(copy.value.settings.mcp.configJson);
      return null;
    }

    const serverMap = getMcpServerMap(parsedObject);
    if (serverMap) {
      const entries = Object.entries(serverMap).filter(([, value]) => toMcpImportedServerPayload(value) !== null);
      if (entries.length !== 1) {
        settingsState.mcpError = copy.value.notices.mcpJsonSingleServer;
        return null;
      }
      const [serverId, server] = entries[0];
      return { serverId, server: toMcpImportedServerPayload(server) || {} };
    }

    const servers = parsedObject.servers;
    if (Array.isArray(servers)) {
      const server = servers.length === 1 ? toMcpImportedServerPayload(servers[0]) : null;
      if (!server) {
        settingsState.mcpError = copy.value.notices.mcpJsonSingleServer;
        return null;
      }
      return { serverId: serverIdFromJson(server), server };
    }

    const nestedServer = toMcpImportedServerPayload(parsedObject.server);
    if (nestedServer) {
      return {
        serverId: optionalText(parsedObject.server_name || parsedObject.server_id || parsedObject.id || parsedObject.name),
        server: nestedServer,
      };
    }

    return {
      serverId: optionalText(parsedObject.server_id || parsedObject.serverId || parsedObject.server_name || parsedObject.serverName || parsedObject.id || parsedObject.name),
      server: toMcpImportedServerPayload(parsedObject) || {},
    };
  }

  function resetMcpForm(): void {
    settingsState.mcpForm.showEditor = false;
    settingsState.mcpForm.editingId = "";
    settingsState.mcpForm.serverId = "";
    settingsState.mcpForm.type = "stdio";
    settingsState.mcpForm.command = "";
    settingsState.mcpForm.argsText = "";
    settingsState.mcpForm.url = "";
    settingsState.mcpForm.envJson = "";
    settingsState.mcpForm.headersJson = "";
    settingsState.mcpForm.toolTimeout = "30";
    settingsState.mcpForm.enabledToolsText = "*";
    settingsState.mcpForm.showAdvanced = false;
    settingsState.mcpForm.showJsonInput = false;
    settingsState.mcpForm.jsonText = "";
  }

  function buildMcpServerPayload(): McpServerPayload | null {
    settingsState.mcpError = "";
    const form = settingsState.mcpForm;
    const env = parseOptionalJsonObject(form.envJson, copy.value.settings.mcp.env);
    if (env === undefined) {
      return null;
    }
    const headers = parseOptionalJsonObject(form.headersJson, copy.value.settings.mcp.headers);
    if (headers === undefined) {
      return null;
    }

    const payload: McpServerPayload = {
      server_id: String(form.serverId || "").trim(),
      type: normalizeMcpTransport(form.type),
      command: String(form.command || "").trim(),
      args: parseLines(form.argsText),
      url: String(form.url || "").trim(),
      tool_timeout: Number(form.toolTimeout || 30),
      enabled_tools: parseListText(form.enabledToolsText, ["*"]),
    };
    if (env !== null) {
      payload.env = env;
    }
    if (headers !== null) {
      payload.headers = headers;
    }
    return payload;
  }

  async function loadMcpSettings(): Promise<void> {
    settingsState.mcpLoading = true;
    settingsState.mcpError = "";
    try {
      const response = toMcpSettingsPayload(await requestSettingsJson("/api/settings/mcp")) || {};
      settingsState.mcp = normalizeMcpSettingsView(response, settingsState.mcp.runtime);
    } catch (error: unknown) {
      settingsState.mcpError = errorMessage(error) || copy.value.notices.mcpLoadFailed;
    } finally {
      settingsState.mcpLoading = false;
    }
  }

  function beginMcpEdit(server: McpServerView): void {
    settingsState.mcpNotice = "";
    settingsState.mcpError = "";
    settingsState.mcpForm.showEditor = true;
    settingsState.mcpForm.editingId = optionalText(server.id);
    settingsState.mcpForm.serverId = optionalText(server.id);
    settingsState.mcpForm.type = normalizeMcpTransport(server.type);
    settingsState.mcpForm.command = optionalText(server.command);
    settingsState.mcpForm.argsText = Array.isArray(server.args) ? server.args.join("\n") : "";
    settingsState.mcpForm.url = optionalText(server.url);
    settingsState.mcpForm.envJson = "";
    settingsState.mcpForm.headersJson = "";
    settingsState.mcpForm.toolTimeout = String(server.tool_timeout || 30);
    settingsState.mcpForm.enabledToolsText = Array.isArray(server.enabled_tools) ? server.enabled_tools.join("\n") : "*";
    settingsState.mcpForm.showAdvanced = false;
    settingsState.mcpForm.showJsonInput = false;
    settingsState.mcpForm.jsonText = "";
  }

  function cancelMcpEdit(): void {
    resetMcpForm();
  }

  function beginMcpCreate(): void {
    resetMcpForm();
    settingsState.mcpError = "";
    settingsState.mcpNotice = "";
    settingsState.mcpForm.showEditor = true;
  }

  function toggleMcpAdvanced(): void {
    settingsState.mcpForm.showAdvanced = !settingsState.mcpForm.showAdvanced;
  }

  function toggleMcpJsonInput(): void {
    settingsState.mcpForm.showJsonInput = !settingsState.mcpForm.showJsonInput;
  }

  function toggleMcpToolGroup(serverId: string): void {
    const key = String(serverId || "").trim() || "unknown";
    settingsState.mcpToolGroupsExpanded[key] = settingsState.mcpToolGroupsExpanded[key] !== true;
  }

  function applyMcpJson(): void {
    settingsState.mcpError = "";
    settingsState.mcpNotice = "";
    let parsed: unknown;
    try {
      parsed = JSON.parse(String(settingsState.mcpForm.jsonText || ""));
    } catch {
      settingsState.mcpError = copy.value.notices.mcpJsonInvalid(copy.value.settings.mcp.configJson);
      return;
    }

    const extracted = extractMcpServerFromJson(parsed);
    if (!extracted) {
      return;
    }

    const form = settingsState.mcpForm;
    const server = extracted.server;
    const nextServerId = String(extracted.serverId || "").trim();
    if (form.editingId && nextServerId && nextServerId !== form.editingId) {
      settingsState.mcpError = copy.value.notices.mcpJsonEditingMismatch;
      return;
    }
    if (!form.editingId && nextServerId) {
      form.serverId = nextServerId;
    }

    const rawType = server.type || server.transport_type || server.transport;
    form.type = normalizeMcpTransport(rawType, server.url ? "streamableHttp" : "stdio");
    form.command = String(server.command || "").trim();
    form.argsText = formatListField(server.args, form.argsText);
    form.url = String(server.url || "").trim();
    form.toolTimeout = String(server.tool_timeout || server.toolTimeout || form.toolTimeout || 30);
    form.enabledToolsText = formatListField(server.enabled_tools || server.enabledTools, form.enabledToolsText || "*") || "*";
    form.envJson = formatJsonObject(server.env) || form.envJson;
    form.headersJson = formatJsonObject(server.headers) || form.headersJson;
    form.showAdvanced = Boolean(server.env || server.headers || server.tool_timeout || server.toolTimeout || server.enabled_tools || server.enabledTools);
    form.showJsonInput = false;
    setSettingsSuccess("mcpNotice", copy.value.notices.mcpJsonApplied);
  }

  async function saveMcpServer(): Promise<void> {
    const payload = buildMcpServerPayload();
    if (payload === null) {
      return;
    }
    const serverId = optionalText(payload.server_id);
    const transportType = payload.type;
    const command = optionalText(payload.command);
    const url = optionalText(payload.url);
    if (!serverId) {
      settingsState.mcpError = copy.value.notices.mcpServerIdRequired;
      return;
    }
    if (transportType === "stdio" && !command) {
      settingsState.mcpError = copy.value.notices.mcpCommandRequired;
      return;
    }
    if ((transportType === "sse" || transportType === "streamableHttp") && !url) {
      settingsState.mcpError = copy.value.notices.mcpUrlRequired;
      return;
    }

    settingsState.mcpLoading = true;
    settingsState.mcpError = "";
    settingsState.mcpNotice = "";
    try {
      const editingId = settingsState.mcpForm.editingId;
      const response = toMcpSettingsPayload(await requestSettingsJson(editingId ? `/api/settings/mcp/${encodeURIComponent(editingId)}` : "/api/settings/mcp", {
        method: editingId ? "PUT" : "POST",
        body: JSON.stringify(payload),
      })) || {};
      settingsState.mcp = normalizeMcpSettingsView(response, settingsState.mcp.runtime);
      setSettingsSuccess("mcpNotice", optionalText(response.reload_message) || copy.value.notices.mcpSaved);
      resetMcpForm();
    } catch (error: unknown) {
      settingsState.mcpError = errorMessage(error) || copy.value.notices.mcpSaveFailed;
    } finally {
      settingsState.mcpLoading = false;
    }
  }

  async function removeMcpServer(server: McpServerView): Promise<void> {
    const serverId = optionalText(server.id);
    settingsState.mcpLoading = true;
    settingsState.mcpError = "";
    settingsState.mcpNotice = "";
    try {
      const response = toMcpSettingsPayload(await requestSettingsJson(`/api/settings/mcp/${encodeURIComponent(serverId)}`, {
        method: "DELETE",
      })) || {};
      settingsState.mcp = normalizeMcpSettingsView(response, settingsState.mcp.runtime);
      setSettingsSuccess("mcpNotice", optionalText(response.reload_message) || copy.value.notices.mcpRemoved);
      if (settingsState.mcpForm.editingId === serverId) {
        resetMcpForm();
      }
    } catch (error: unknown) {
      settingsState.mcpError = errorMessage(error) || copy.value.notices.mcpRemoveFailed;
    } finally {
      settingsState.mcpLoading = false;
    }
  }

  async function reloadMcpSettings(): Promise<void> {
    settingsState.mcpLoading = true;
    settingsState.mcpError = "";
    settingsState.mcpNotice = "";
    try {
      const response = toMcpSettingsPayload(await requestSettingsJson("/api/settings/mcp/reload", { method: "POST" })) || {};
      settingsState.mcp = normalizeMcpSettingsView(response, settingsState.mcp.runtime);
      setSettingsSuccess("mcpNotice", optionalText(response.reload_message) || copy.value.notices.mcpReloaded);
    } catch (error: unknown) {
      settingsState.mcpError = errorMessage(error) || copy.value.notices.mcpReloadFailed;
    } finally {
      settingsState.mcpLoading = false;
    }
  }

  return {
    loadMcpSettings,
    beginMcpEdit,
    beginMcpCreate,
    cancelMcpEdit,
    saveMcpServer,
    removeMcpServer,
    reloadMcpSettings,
    toggleMcpAdvanced,
    toggleMcpJsonInput,
    toggleMcpToolGroup,
    applyMcpJson,
  };
}
