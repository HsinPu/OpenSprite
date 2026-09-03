import { defaultTranslator, type MessageKey, type Translator } from "../i18n/catalog";


export type ToolApprovalDecision = "allow_once" | "deny";
export type ToolApprovalDetail = {
  id: string;
  runId: string;
  conversationId: string;
  toolId: string;
  toolName: string;
  serverId: string;
  arguments: Record<string, unknown>;
  argumentHash: string;
  createdAt: string;
  expiresAt: string;
};
export type ToolApprovalErrorCode = "invalid_request" | "not_found" | "approval_expired" | "approval_already_decided" | "database_unavailable" | "internal_error" | "malformed_response" | "network_error";
export class ToolApprovalApiError extends Error { constructor(readonly code: ToolApprovalErrorCode) { super(code); this.name = "ToolApprovalApiError"; } }

const identifier = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const exactKeys = (value: Record<string, unknown>, expected: readonly string[]) => Object.keys(value).length === expected.length && Object.keys(value).every((key) => expected.includes(key));
const utc = (value: unknown) => typeof value === "string" && value.endsWith("Z") && Number.isFinite(Date.parse(value));
const codes: ToolApprovalErrorCode[] = ["invalid_request", "not_found", "approval_expired", "approval_already_decided", "database_unavailable", "internal_error"];

function errorCode(value: unknown): ToolApprovalErrorCode {
  if (!record(value) || !exactKeys(value, ["error"]) || !record(value.error) || !exactKeys(value.error, ["code", "message", "retryable"]) || typeof value.error.code !== "string" || !codes.includes(value.error.code as ToolApprovalErrorCode) || typeof value.error.message !== "string" || typeof value.error.retryable !== "boolean") throw new ToolApprovalApiError("malformed_response");
  return value.error.code as ToolApprovalErrorCode;
}

async function request(id: string, init?: RequestInit): Promise<unknown> {
  let response: Response;
  try { response = await apiFetch(`/api/tool-approvals/${id}`, init); } catch { throw new ToolApprovalApiError("network_error"); }
  let body: unknown;
  try { body = await response.json(); } catch { throw new ToolApprovalApiError("malformed_response"); }
  if (response.status !== 200) throw new ToolApprovalApiError(errorCode(body));
  return body;
}

export async function getToolApproval(id: string): Promise<ToolApprovalDetail> {
  const value = await request(id);
  if (!record(value) || !exactKeys(value, ["id", "runId", "conversationId", "toolId", "toolName", "serverId", "arguments", "argumentHash", "createdAt", "expiresAt"]) || value.id !== id || typeof value.runId !== "string" || !identifier.test(value.runId) || typeof value.conversationId !== "string" || !identifier.test(value.conversationId) || typeof value.toolId !== "string" || typeof value.toolName !== "string" || typeof value.serverId !== "string" || !identifier.test(value.serverId) || !record(value.arguments) || typeof value.argumentHash !== "string" || !/^[0-9a-f]{64}$/.test(value.argumentHash) || !utc(value.createdAt) || !utc(value.expiresAt)) throw new ToolApprovalApiError("malformed_response");
  return value as ToolApprovalDetail;
}

export async function putToolApproval(id: string, decision: ToolApprovalDecision): Promise<void> {
  const value = await request(id, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision }) });
  if (!record(value) || !exactKeys(value, ["id", "decision"]) || value.id !== id || value.decision !== decision) throw new ToolApprovalApiError("malformed_response");
}

export function toolApprovalErrorText(error: unknown, t: Translator = defaultTranslator): string {
  const code = error instanceof ToolApprovalApiError ? error.code : "network_error";
  const keys: Record<ToolApprovalErrorCode, MessageKey> = {
    invalid_request: "error.mcp.invalidRequest",
    not_found: "error.approval.notFound",
    approval_expired: "error.approval.expired",
    approval_already_decided: "error.approval.decided",
    database_unavailable: "error.approval.database",
    internal_error: "error.approval.internal",
    malformed_response: "error.approval.malformed",
    network_error: "error.network",
  };
  return t(keys[code]);
}
import { apiFetch } from "./http";
