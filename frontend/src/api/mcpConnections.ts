import { defaultTranslator, type MessageKey, type Translator } from "../i18n/catalog";


export type McpServerStatus = "disabled" | "stopped" | "starting" | "connected" | "error" | "stopping";
export type McpServerDraft = {
  name: string;
  startOnLaunch: boolean;
  transport: {
    type: "stdio";
    executable: string;
    arguments: string[];
    workingDirectory: string | null;
  };
};
export type McpServerSummary = McpServerDraft & {
  id: string;
  enabled: boolean;
  status: McpServerStatus;
  protocolVersion: string | null;
  errorCode: string | null;
  toolCount: number;
  unsupportedToolCount: number;
};
export type McpToolSummary = {
  id: string;
  serverId: string;
  originalName: string;
  title: string | null;
  description: string;
  supported: boolean;
  unsupportedReason: "unsupported_schema" | null;
  annotations: { readOnlyHint: boolean; destructiveHint: boolean; idempotentHint: boolean; openWorldHint: boolean };
};
export type McpErrorCode = "invalid_request" | "not_found" | "server_disabled" | "server_not_running" | "server_start_failed" | "server_stop_failed" | "server_unreachable" | "server_timeout" | "tools_not_supported" | "tool_catalog_invalid" | "mcp_store_unavailable" | "internal_error" | "malformed_response" | "network_error";

export class McpApiError extends Error {
  constructor(readonly code: McpErrorCode) { super(code); this.name = "McpApiError"; }
}

const identifier = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const toolId = /^[a-z][a-z0-9_]{0,63}$/;
const statuses: McpServerStatus[] = ["disabled", "stopped", "starting", "connected", "error", "stopping"];
const serverCodes: McpErrorCode[] = ["invalid_request", "not_found", "server_disabled", "server_not_running", "server_start_failed", "server_stop_failed", "server_unreachable", "server_timeout", "tools_not_supported", "tool_catalog_invalid", "mcp_store_unavailable", "internal_error"];
const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const exactKeys = (value: Record<string, unknown>, expected: readonly string[]) => Object.keys(value).length === expected.length && Object.keys(value).every((key) => expected.includes(key));
const bounded = (value: unknown, maximum: number): value is string => typeof value === "string" && value.length > 0 && value.length <= maximum;

function transport(value: unknown): McpServerDraft["transport"] {
  if (!record(value) || !exactKeys(value, ["type", "executable", "arguments", "workingDirectory"]) || value.type !== "stdio" || !bounded(value.executable, 2048) || !Array.isArray(value.arguments) || value.arguments.length > 64 || value.arguments.some((item) => !bounded(item, 2048)) || (value.workingDirectory !== null && !bounded(value.workingDirectory, 2048))) throw new McpApiError("malformed_response");
  return { type: "stdio", executable: value.executable, arguments: [...value.arguments] as string[], workingDirectory: value.workingDirectory as string | null };
}

function server(value: unknown): McpServerSummary {
  if (!record(value) || !exactKeys(value, ["id", "name", "enabled", "startOnLaunch", "transport", "status", "protocolVersion", "errorCode", "toolCount", "unsupportedToolCount"]) || typeof value.id !== "string" || !identifier.test(value.id) || !bounded(value.name, 80) || typeof value.enabled !== "boolean" || typeof value.startOnLaunch !== "boolean" || typeof value.status !== "string" || !statuses.includes(value.status as McpServerStatus) || (value.protocolVersion !== null && !bounded(value.protocolVersion, 32)) || (value.errorCode !== null && !bounded(value.errorCode, 64)) || !Number.isInteger(value.toolCount) || (value.toolCount as number) < 0 || (value.toolCount as number) > 128 || !Number.isInteger(value.unsupportedToolCount) || (value.unsupportedToolCount as number) < 0 || (value.unsupportedToolCount as number) > 128) throw new McpApiError("malformed_response");
  return { id: value.id, name: value.name, enabled: value.enabled, startOnLaunch: value.startOnLaunch, transport: transport(value.transport), status: value.status as McpServerStatus, protocolVersion: value.protocolVersion as string | null, errorCode: value.errorCode as string | null, toolCount: value.toolCount as number, unsupportedToolCount: value.unsupportedToolCount as number };
}

function tool(value: unknown): McpToolSummary {
  if (!record(value) || !exactKeys(value, ["id", "serverId", "originalName", "title", "description", "supported", "unsupportedReason", "annotations"]) || typeof value.id !== "string" || !toolId.test(value.id) || typeof value.serverId !== "string" || !identifier.test(value.serverId) || !bounded(value.originalName, 128) || (value.title !== null && !bounded(value.title, 256)) || !bounded(value.description, 1024) || typeof value.supported !== "boolean" || ![null, "unsupported_schema"].includes(value.unsupportedReason as null | string) || !record(value.annotations) || !exactKeys(value.annotations, ["readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint"]) || Object.values(value.annotations).some((item) => typeof item !== "boolean")) throw new McpApiError("malformed_response");
  return { id: value.id, serverId: value.serverId, originalName: value.originalName, title: value.title as string | null, description: value.description, supported: value.supported, unsupportedReason: value.unsupportedReason as "unsupported_schema" | null, annotations: value.annotations as McpToolSummary["annotations"] };
}

function errorCode(value: unknown): McpErrorCode {
  if (!record(value) || !exactKeys(value, ["error"]) || !record(value.error) || !exactKeys(value.error, ["code", "message", "retryable"]) || typeof value.error.code !== "string" || !serverCodes.includes(value.error.code as McpErrorCode) || typeof value.error.message !== "string" || typeof value.error.retryable !== "boolean") throw new McpApiError("malformed_response");
  return value.error.code as McpErrorCode;
}

async function request(path: string, init?: RequestInit, expected = 200): Promise<unknown> {
  let response: Response;
  try { response = await fetch(path, init); } catch { throw new McpApiError("network_error"); }
  if (response.status === 204 && expected === 204) return null;
  let body: unknown;
  try { body = await response.json(); } catch { throw new McpApiError("malformed_response"); }
  if (response.status !== expected) throw new McpApiError(errorCode(body));
  return body;
}

export async function listMcpServers(): Promise<McpServerSummary[]> {
  const body = await request("/api/mcp/servers");
  if (!record(body) || !exactKeys(body, ["servers"]) || !Array.isArray(body.servers) || body.servers.length > 32) throw new McpApiError("malformed_response");
  return body.servers.map(server);
}
export async function createMcpServer(payload: McpServerDraft): Promise<McpServerSummary> { return server(await request("/api/mcp/servers", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }, 201)); }
export async function updateMcpServer(id: string, payload: McpServerDraft): Promise<McpServerSummary> { return server(await request(`/api/mcp/servers/${id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) })); }
export async function deleteMcpServer(id: string): Promise<void> { await request(`/api/mcp/servers/${id}`, { method: "DELETE" }, 204); }
export async function testMcpServer(id: string): Promise<McpServerSummary> { return server(await request(`/api/mcp/servers/${id}/test`, { method: "POST" })); }
export async function startMcpServer(id: string): Promise<McpServerSummary> { return server(await request(`/api/mcp/servers/${id}/start`, { method: "POST" })); }
export async function stopMcpServer(id: string): Promise<McpServerSummary> { return server(await request(`/api/mcp/servers/${id}/stop`, { method: "POST" })); }
export async function listMcpTools(id: string): Promise<McpToolSummary[]> {
  const body = await request(`/api/mcp/servers/${id}/tools`);
  if (!record(body) || !exactKeys(body, ["tools"]) || !Array.isArray(body.tools) || body.tools.length > 128) throw new McpApiError("malformed_response");
  return body.tools.map(tool);
}

export function mcpErrorText(error: unknown, t: Translator = defaultTranslator): string {
  const code = error instanceof McpApiError ? error.code : "network_error";
  const keys: Record<McpErrorCode, MessageKey> = {
    invalid_request: "error.mcp.invalidRequest", not_found: "error.mcp.notFound", server_disabled: "error.mcp.disabled", server_not_running: "error.mcp.notRunning", server_start_failed: "error.mcp.startFailed", server_stop_failed: "error.mcp.stopFailed", server_unreachable: "error.mcp.unreachable", server_timeout: "error.mcp.timeout", tools_not_supported: "error.mcp.noTools", tool_catalog_invalid: "error.mcp.catalog", mcp_store_unavailable: "error.mcp.store", internal_error: "error.mcp.internal", malformed_response: "error.mcp.malformed", network_error: "error.network",
  };
  return t(keys[code]);
}
