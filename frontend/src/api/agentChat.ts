export const runStatuses = ["queued", "running", "cancelling", "completed", "failed", "cancelled", "interrupted"] as const;
export type RunStatus = (typeof runStatuses)[number];

export const completionReasons = ["stop", "output_limit", "context_limit"] as const;
export type CompletionReason = (typeof completionReasons)[number];

export const UNASSIGNED_WORKSPACE_ID = "00000000-0000-4000-8000-000000000000";

export const runEventTypes = ["run.started", "context.compaction.started", "model.started", "response.continuation.started", "assistant.delta", "tool.approval_requested", "tool.approval_decided", "tool.started", "tool.completed", "tool.failed", "run.completed", "run.failed", "run.cancelled", "run.interrupted"] as const;
export type RunEventType = (typeof runEventTypes)[number];

export const chatErrorCodes = ["invalid_request", "not_found", "run_busy", "run_not_active", "model_not_selected", "provider_not_connected", "invalid_credentials", "provider_rate_limited", "provider_timeout", "provider_unreachable", "credential_store_unavailable", "settings_store_unavailable", "database_unavailable", "agent_limit_reached", "context_limit_exceeded", "context_preparation_failed", "tool_failure", "scheduled_tool_approval_required", "invalid_provider_response", "internal_error", "workspace_not_found", "workspace_mismatch", "workspace_store_unavailable", "revision_conflict", "workspace_managed_by_schedule"] as const;
export type ChatServerErrorCode = (typeof chatErrorCodes)[number];
export type AgentChatErrorCode = ChatServerErrorCode | "malformed_response" | "network_error";

export type ConversationSummary = {
  id: string;
  workspaceId: string;
  revision: number;
  workspaceManagedBySchedule: boolean;
  title: string;
  latestMessagePreview: string | null;
  createdAt: string;
  updatedAt: string;
};

export type ConversationPage = {
  conversations: ConversationSummary[];
  nextCursor: string | null;
};

export type ChatMessage = {
  id: string;
  conversationId: string;
  runId: string;
  role: "user" | "assistant";
  content: string;
  sequence: number;
  createdAt: string;
};

export type MessagePage = {
  messages: ChatMessage[];
  nextBeforeSequence: number | null;
};

export type RunError = {
  code: ChatServerErrorCode;
  message: string;
  retryable: boolean;
};

export type RunSnapshot = {
  id: string;
  conversationId: string;
  workspaceId: string;
  workspaceRevision: number;
  workspaceName: string;
  workspaceRootHash: string | null;
  userMessageId: string;
  assistantMessageId: string | null;
  providerId: "openai" | "anthropic" | "openrouter";
  modelId: string;
  responseMode: "default" | "fast" | "balanced" | "deep";
  status: RunStatus;
  completionReason: CompletionReason | null;
  error: RunError | null;
  partialText: string;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
};

export type RunEvent = {
  sequence: number;
  type: RunEventType;
  runId: string;
  conversationId: string;
  createdAt: string;
  data: Record<string, unknown>;
};

export type ContextUsage = {
  providerId: "openai" | "anthropic" | "openrouter";
  modelId: string;
  contextTokens: number;
  contextLimitTokens: number;
  inputBudgetTokens: number;
};

export type StartRunInput = {
  conversationId: string | null;
  workspaceId: string;
  clientRequestId: string;
  message: string;
};

export type StartRunResult = {
  conversationId: string;
  workspaceId: string;
  runId: string;
  status: "queued";
};

export type CancelRunResult = {
  runId: string;
  status: "cancelling" | "cancelled";
};

export type RunEventStreamHandlers = {
  onEvent: (event: RunEvent) => void;
  onError: (error: AgentChatApiError) => void;
};

export type RunEventStream = { close: () => void };

export class AgentChatApiError extends Error {
  constructor(readonly code: AgentChatErrorCode) {
    super(code);
    this.name = "AgentChatApiError";
  }
}

const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const exactKeys = (value: Record<string, unknown>, expected: readonly string[]) => Object.keys(value).length === expected.length && Object.keys(value).every((key) => expected.includes(key));
const codePointLength = (value: string) => Array.from(value).length;
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

export function isIdentifier(value: unknown): value is string {
  return typeof value === "string" && uuidPattern.test(value);
}

function utc(value: unknown): value is string {
  const match = typeof value === "string" && /^(\d{4})-(\d{2})-(\d{2})T([01]\d|2[0-3]):([0-5]\d):([0-5]\d)(?:\.\d+)?Z$/.exec(value);
  if (!match) return false;
  const [year, month, day, hour, minute, second] = match.slice(1, 7).map(Number);
  const date = new Date(Date.UTC(year, month - 1, day, hour, minute, second));
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day && date.getUTCHours() === hour && date.getUTCMinutes() === minute && date.getUTCSeconds() === second;
}

function boundedString(value: unknown, minimum: number, maximum: number): value is string {
  return typeof value === "string" && codePointLength(value) >= minimum && codePointLength(value) <= maximum;
}

function conversation(value: unknown): ConversationSummary {
  if (!record(value) || !exactKeys(value, ["id", "workspaceId", "revision", "workspaceManagedBySchedule", "title", "latestMessagePreview", "createdAt", "updatedAt"]) || !isIdentifier(value.id) || !isIdentifier(value.workspaceId) || !Number.isInteger(value.revision) || (value.revision as number) < 1 || typeof value.workspaceManagedBySchedule !== "boolean" || !boundedString(value.title, 1, 160) || (value.latestMessagePreview !== null && !boundedString(value.latestMessagePreview, 1, 280)) || !utc(value.createdAt) || !utc(value.updatedAt)) {
    throw new AgentChatApiError("malformed_response");
  }
  return value as ConversationSummary;
}

function message(value: unknown, expectedConversationId?: string): ChatMessage {
  if (!record(value) || !exactKeys(value, ["id", "conversationId", "runId", "role", "content", "sequence", "createdAt"]) || !isIdentifier(value.id) || !isIdentifier(value.conversationId) || (expectedConversationId !== undefined && value.conversationId !== expectedConversationId) || !isIdentifier(value.runId) || (value.role !== "user" && value.role !== "assistant") || !boundedString(value.content, 1, 1048576) || !Number.isInteger(value.sequence) || (value.sequence as number) < 1 || !utc(value.createdAt)) {
    throw new AgentChatApiError("malformed_response");
  }
  return value as ChatMessage;
}

function runError(value: unknown): RunError {
  if (!record(value) || !exactKeys(value, ["code", "message", "retryable"]) || !chatErrorCodes.includes(value.code as ChatServerErrorCode) || !boundedString(value.message, 1, 512) || typeof value.retryable !== "boolean") {
    throw new AgentChatApiError("malformed_response");
  }
  return value as RunError;
}

function runSnapshot(value: unknown, expectedRunId?: string): RunSnapshot {
  if (!record(value) || !exactKeys(value, ["id", "conversationId", "workspaceId", "workspaceRevision", "workspaceName", "workspaceRootHash", "userMessageId", "assistantMessageId", "providerId", "modelId", "responseMode", "status", "completionReason", "error", "partialText", "createdAt", "startedAt", "finishedAt"]) || !isIdentifier(value.id) || (expectedRunId !== undefined && value.id !== expectedRunId) || !isIdentifier(value.conversationId) || !isIdentifier(value.workspaceId) || !Number.isInteger(value.workspaceRevision) || (value.workspaceRevision as number) < 1 || !boundedString(value.workspaceName, 1, 80) || (value.workspaceRootHash !== null && (typeof value.workspaceRootHash !== "string" || !/^[0-9a-f]{64}$/.test(value.workspaceRootHash))) || !isIdentifier(value.userMessageId) || (value.assistantMessageId !== null && !isIdentifier(value.assistantMessageId)) || !["openai", "anthropic", "openrouter"].includes(value.providerId as string) || !boundedString(value.modelId, 1, 256) || !["default", "fast", "balanced", "deep"].includes(value.responseMode as string) || !runStatuses.includes(value.status as RunStatus) || (value.completionReason !== null && !completionReasons.includes(value.completionReason as CompletionReason)) || (value.error !== null && !record(value.error)) || !boundedString(value.partialText, 0, 1048576) || !utc(value.createdAt) || (value.startedAt !== null && !utc(value.startedAt)) || (value.finishedAt !== null && !utc(value.finishedAt))) {
    throw new AgentChatApiError("malformed_response");
  }
  const parsedError = value.error === null ? null : runError(value.error);
  const status = value.status as RunStatus;
  if ((status === "queued" && (value.startedAt !== null || value.finishedAt !== null || value.completionReason !== null || parsedError !== null || value.assistantMessageId !== null)) || (["running", "cancelling"].includes(status) && (value.startedAt === null || value.finishedAt !== null || value.completionReason !== null || parsedError !== null || value.assistantMessageId !== null)) || (status === "completed" && (value.startedAt === null || value.finishedAt === null || value.completionReason === null || value.assistantMessageId === null || parsedError !== null)) || (status === "failed" && (value.startedAt === null || value.finishedAt === null || value.completionReason !== null || value.assistantMessageId !== null || parsedError === null)) || (status === "cancelled" && (value.finishedAt === null || value.completionReason !== null || value.assistantMessageId !== null || parsedError !== null)) || (status === "interrupted" && (value.finishedAt === null || value.completionReason !== null || value.assistantMessageId !== null || parsedError === null))) {
    throw new AgentChatApiError("malformed_response");
  }
  return { ...value, error: parsedError } as RunSnapshot;
}

function errorCode(value: unknown, allowed: readonly ChatServerErrorCode[]): ChatServerErrorCode {
  if (!record(value) || !exactKeys(value, ["error"]) || !record(value.error) || !exactKeys(value.error, ["code", "message", "retryable"]) || !chatErrorCodes.includes(value.error.code as ChatServerErrorCode) || !allowed.includes(value.error.code as ChatServerErrorCode) || typeof value.error.message !== "string" || typeof value.error.retryable !== "boolean") {
    throw new AgentChatApiError("malformed_response");
  }
  return value.error.code as ChatServerErrorCode;
}

async function jsonRequest(path: string, init: RequestInit | undefined, successStatus: number, errors: ReadonlyMap<number, readonly ChatServerErrorCode[]>): Promise<unknown> {
  let response: Response;
  try {
    response = await apiFetch(path, init);
  } catch {
    throw new AgentChatApiError("network_error");
  }
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new AgentChatApiError("malformed_response");
  }
  if (response.status !== successStatus) {
    if (response.ok) throw new AgentChatApiError("malformed_response");
    throw new AgentChatApiError(errorCode(body, errors.get(response.status) ?? []));
  }
  return body;
}

export async function listConversations(options: { workspaceId: string; limit?: number; before?: string }): Promise<ConversationPage> {
  if (!isIdentifier(options.workspaceId)) throw new AgentChatApiError("malformed_response");
  const limit = options.limit ?? 50;
  const query = new URLSearchParams({ workspaceId: options.workspaceId, limit: String(limit) });
  if (options.before !== undefined) query.set("before", options.before);
  const body = await jsonRequest(`/api/conversations?${query}`, undefined, 200, new Map([[400, ["invalid_request"]], [404, ["workspace_not_found"]], [503, ["database_unavailable", "workspace_store_unavailable"]], [500, ["internal_error"]]]));
  if (!record(body) || !exactKeys(body, ["conversations", "nextCursor"]) || !Array.isArray(body.conversations) || body.conversations.length > 100 || (body.nextCursor !== null && !boundedString(body.nextCursor, 1, 512))) throw new AgentChatApiError("malformed_response");
  return { conversations: body.conversations.map(conversation), nextCursor: body.nextCursor as string | null };
}

export async function listConversationMessages(conversationId: string, options: { limit?: number; beforeSequence?: number } = {}): Promise<MessagePage> {
  if (!isIdentifier(conversationId)) throw new AgentChatApiError("malformed_response");
  const query = new URLSearchParams({ limit: String(options.limit ?? 100) });
  if (options.beforeSequence !== undefined) query.set("beforeSequence", String(options.beforeSequence));
  const body = await jsonRequest(`/api/conversations/${conversationId}/messages?${query}`, undefined, 200, new Map([[400, ["invalid_request"]], [404, ["not_found"]], [503, ["database_unavailable"]], [500, ["internal_error"]]]));
  if (!record(body) || !exactKeys(body, ["messages", "nextBeforeSequence"]) || !Array.isArray(body.messages) || body.messages.length > 200 || (body.nextBeforeSequence !== null && (!Number.isInteger(body.nextBeforeSequence) || (body.nextBeforeSequence as number) < 1))) throw new AgentChatApiError("malformed_response");
  const messages = body.messages.map((item) => message(item, conversationId));
  if (!messages.every((item, index) => index === 0 || messages[index - 1]!.sequence < item.sequence)) throw new AgentChatApiError("malformed_response");
  return { messages, nextBeforeSequence: body.nextBeforeSequence as number | null };
}

export async function getConversation(conversationId: string): Promise<ConversationSummary> {
  if (!isIdentifier(conversationId)) throw new AgentChatApiError("malformed_response");
  return conversation(await jsonRequest(`/api/conversations/${conversationId}`, undefined, 200, new Map([[404, ["not_found"]], [503, ["database_unavailable"]], [500, ["internal_error"]]])));
}

export async function moveConversationToWorkspace(conversationId: string, workspaceId: string, expectedRevision: number): Promise<ConversationSummary> {
  if (!isIdentifier(conversationId) || !isIdentifier(workspaceId) || !Number.isInteger(expectedRevision) || expectedRevision < 1) throw new AgentChatApiError("malformed_response");
  const body = await jsonRequest(`/api/conversations/${conversationId}/workspace`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ workspaceId, expectedRevision }) }, 200, new Map([[400, ["invalid_request"]], [404, ["not_found", "workspace_not_found"]], [409, ["run_busy", "revision_conflict", "workspace_managed_by_schedule"]], [503, ["database_unavailable", "workspace_store_unavailable"]], [500, ["internal_error"]]]));
  return conversation(body);
}

export async function startRun(input: StartRunInput): Promise<StartRunResult> {
  if ((input.conversationId !== null && !isIdentifier(input.conversationId)) || !isIdentifier(input.workspaceId) || !isIdentifier(input.clientRequestId) || !boundedString(input.message, 1, 32768) || !input.message.trim()) throw new AgentChatApiError("malformed_response");
  const body = await jsonRequest("/api/runs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input) }, 202, new Map([[400, ["invalid_request"]], [404, ["workspace_not_found"]], [409, ["run_busy", "model_not_selected", "provider_not_connected", "workspace_mismatch"]], [503, ["credential_store_unavailable", "settings_store_unavailable", "database_unavailable", "workspace_store_unavailable"]], [500, ["internal_error"]]]));
  if (!record(body) || !exactKeys(body, ["conversationId", "workspaceId", "runId", "status"]) || !isIdentifier(body.conversationId) || !isIdentifier(body.workspaceId) || body.workspaceId !== input.workspaceId || !isIdentifier(body.runId) || body.status !== "queued") throw new AgentChatApiError("malformed_response");
  return body as StartRunResult;
}

export async function getRun(runId: string): Promise<RunSnapshot> {
  if (!isIdentifier(runId)) throw new AgentChatApiError("malformed_response");
  return runSnapshot(await jsonRequest(`/api/runs/${runId}`, undefined, 200, new Map([[404, ["not_found"]], [503, ["database_unavailable"]], [500, ["internal_error"]]])), runId);
}

export async function cancelRun(runId: string): Promise<CancelRunResult> {
  if (!isIdentifier(runId)) throw new AgentChatApiError("malformed_response");
  const body = await jsonRequest(`/api/runs/${runId}/cancel`, { method: "POST" }, 202, new Map([[400, ["invalid_request"]], [404, ["not_found"]], [409, ["run_not_active"]], [503, ["database_unavailable"]], [500, ["internal_error"]]]));
  if (!record(body) || !exactKeys(body, ["runId", "status"]) || body.runId !== runId || (body.status !== "cancelling" && body.status !== "cancelled")) throw new AgentChatApiError("malformed_response");
  return body as CancelRunResult;
}

function parseEvent(value: unknown, expectedType: RunEventType, expectedRunId: string): RunEvent {
  if (!record(value) || !exactKeys(value, ["sequence", "type", "runId", "conversationId", "createdAt", "data"]) || !Number.isInteger(value.sequence) || (value.sequence as number) < 1 || value.type !== expectedType || value.runId !== expectedRunId || !isIdentifier(value.conversationId) || !utc(value.createdAt) || !record(value.data)) throw new AgentChatApiError("malformed_response");
  const data = value.data;
  const safeError = (candidate: unknown) => runError(candidate);
  if (expectedType === "run.started" && !exactKeys(data, [])) {
    if (!exactKeys(data, ["workspaceId", "workspaceRevision", "workspaceName", "workspaceRootHash", "workspaceAvailability"]) || !isIdentifier(data.workspaceId) || !Number.isInteger(data.workspaceRevision) || (data.workspaceRevision as number) < 1 || !boundedString(data.workspaceName, 1, 80) || (data.workspaceRootHash !== null && (typeof data.workspaceRootHash !== "string" || !/^[0-9a-f]{64}$/.test(data.workspaceRootHash))) || !["available", "unavailable", "not_applicable"].includes(data.workspaceAvailability as string)) throw new AgentChatApiError("malformed_response");
  }
  if (["context.compaction.started", "run.cancelled"].includes(expectedType) && !exactKeys(data, [])) throw new AgentChatApiError("malformed_response");
  if (expectedType === "model.started") {
    const legacyKeys = ["providerId", "modelId", "responseMode", "maxOutputTokens"] as const;
    const contextKeys = [...legacyKeys, "contextTokens", "contextLimitTokens", "inputBudgetTokens"] as const;
    const toolContextKeys = [...contextKeys, "toolNames"] as const;
    const hasContext = exactKeys(data, contextKeys) || exactKeys(data, toolContextKeys);
    if ((!exactKeys(data, legacyKeys) && !hasContext) || !["openai", "anthropic", "openrouter"].includes(data.providerId as string) || !boundedString(data.modelId, 1, 256) || !["default", "fast", "balanced", "deep"].includes(data.responseMode as string) || !Number.isInteger(data.maxOutputTokens) || (data.maxOutputTokens as number) < 1 || (data.maxOutputTokens as number) > 131_072) throw new AgentChatApiError("malformed_response");
    if (hasContext && (!Number.isInteger(data.contextTokens) || (data.contextTokens as number) < 1 || !Number.isInteger(data.contextLimitTokens) || (data.contextLimitTokens as number) < 1 || (data.contextLimitTokens as number) > 4_000_000 || !Number.isInteger(data.inputBudgetTokens) || (data.inputBudgetTokens as number) < 1 || (data.inputBudgetTokens as number) > (data.contextLimitTokens as number) || (data.contextTokens as number) > (data.inputBudgetTokens as number))) throw new AgentChatApiError("malformed_response");
    if (exactKeys(data, toolContextKeys)) {
      if (!Array.isArray(data.toolNames) || data.toolNames.length > 64 || data.toolNames.some((name) => !boundedString(name, 1, 64) || !/^[a-z][a-z0-9_]{0,63}$/.test(name)) || data.toolNames.join("\0") !== [...new Set(data.toolNames)].sort().join("\0")) throw new AgentChatApiError("malformed_response");
    }
  }
  if (expectedType === "response.continuation.started") {
    const maximum = data.maxAttempts;
    if (!exactKeys(data, ["attempt", "maxAttempts"]) || !Number.isInteger(data.attempt) || (data.attempt as number) < 1 || (data.attempt as number) > 64 || (maximum !== null && (!Number.isInteger(maximum) || ![1, 2, 3, 5, 10, 20, 50].includes(maximum as number) || (data.attempt as number) > (maximum as number)))) throw new AgentChatApiError("malformed_response");
  }
  if (expectedType === "assistant.delta" && (!exactKeys(data, ["text"]) || !boundedString(data.text, 1, 16384))) throw new AgentChatApiError("malformed_response");
  if (expectedType === "tool.approval_requested" && (!exactKeys(data, ["approvalId", "toolName", "toolDisplayName", "serverId", "argumentHash", "expiresAt"]) || !isIdentifier(data.approvalId) || !boundedString(data.toolName, 1, 64) || !boundedString(data.toolDisplayName, 1, 256) || !isIdentifier(data.serverId) || typeof data.argumentHash !== "string" || !/^[0-9a-f]{64}$/.test(data.argumentHash) || !utc(data.expiresAt))) throw new AgentChatApiError("malformed_response");
  if (expectedType === "tool.approval_decided" && (!exactKeys(data, ["approvalId", "decision"]) || !isIdentifier(data.approvalId) || !["allow_once", "deny", "expired"].includes(data.decision as string))) throw new AgentChatApiError("malformed_response");
  if (expectedType === "tool.started" && (!exactKeys(data, ["callId", "toolName"]) || !boundedString(data.callId, 1, 128) || !boundedString(data.toolName, 1, 64))) throw new AgentChatApiError("malformed_response");
  if (expectedType === "tool.completed" && (!exactKeys(data, ["callId", "toolName", "summary"]) || !boundedString(data.callId, 1, 128) || !boundedString(data.toolName, 1, 64) || !boundedString(data.summary, 1, 4096))) throw new AgentChatApiError("malformed_response");
  if (expectedType === "tool.failed" && (!exactKeys(data, ["callId", "toolName", "error"]) || !boundedString(data.callId, 1, 128) || !boundedString(data.toolName, 1, 64) || !record(data.error))) throw new AgentChatApiError("malformed_response");
  if (expectedType === "tool.failed") safeError(data.error);
  if (expectedType === "run.completed" && (!exactKeys(data, ["assistantMessageId", "completionReason"]) || !isIdentifier(data.assistantMessageId) || !completionReasons.includes(data.completionReason as CompletionReason))) throw new AgentChatApiError("malformed_response");
  if (["run.failed", "run.interrupted"].includes(expectedType) && (!exactKeys(data, ["error"]) || !record(data.error))) throw new AgentChatApiError("malformed_response");
  if (["run.failed", "run.interrupted"].includes(expectedType)) safeError(data.error);
  return value as RunEvent;
}

export function openRunEventStream(runId: string, handlers: RunEventStreamHandlers): RunEventStream {
  if (!isIdentifier(runId)) throw new AgentChatApiError("malformed_response");
  let source: EventSource;
  try {
    source = new EventSource(`/api/runs/${runId}/events`);
  } catch {
    throw new AgentChatApiError("network_error");
  }
  let closed = false;
  const close = () => { if (!closed) { closed = true; source.close(); } };
  for (const type of runEventTypes) {
    source.addEventListener(type, (raw) => {
      if (closed) return;
      try {
        if (!(raw instanceof MessageEvent) || (raw.lastEventId && raw.lastEventId !== String(JSON.parse(raw.data).sequence))) throw new AgentChatApiError("malformed_response");
        const event = parseEvent(JSON.parse(raw.data), type, runId);
        handlers.onEvent(event);
      } catch {
        close();
        handlers.onError(new AgentChatApiError("malformed_response"));
      }
    });
  }
  source.onerror = () => {
    if (closed) return;
    void getAuthStatus().then((status) => {
      if (status.state !== "authenticated") notifyAuthenticationRequired();
      else handlers.onError(new AgentChatApiError("network_error"));
    }).catch(() => handlers.onError(new AgentChatApiError("network_error")));
  };
  return { close };
}

export function agentChatErrorText(error: unknown, t: Translator = defaultTranslator): string {
  const code = error instanceof AgentChatApiError ? error.code : "network_error";
  const keys = {
    invalid_request: "error.chat.invalidRequest",
    not_found: "error.chat.notFound",
    run_busy: "error.chat.runBusy",
    run_not_active: "error.chat.runNotActive",
    model_not_selected: "error.chat.modelNotSelected",
    provider_not_connected: "error.chat.providerNotConnected",
    invalid_credentials: "error.chat.invalidCredentials",
    provider_rate_limited: "error.chat.rateLimited",
    provider_timeout: "error.chat.timeout",
    provider_unreachable: "error.chat.unreachable",
    credential_store_unavailable: "error.chat.credentialStore",
    settings_store_unavailable: "error.chat.settingsStore",
    database_unavailable: "error.chat.database",
    agent_limit_reached: "error.chat.agentLimit",
    context_limit_exceeded: "error.chat.contextLimit",
    context_preparation_failed: "error.chat.contextPreparation",
    tool_failure: "error.chat.toolFailure",
    scheduled_tool_approval_required: "error.chat.scheduledToolApprovalRequired",
    invalid_provider_response: "error.chat.invalidProviderResponse",
    internal_error: "error.chat.internal",
    workspace_not_found: "error.chat.workspaceNotFound",
    workspace_mismatch: "error.chat.workspaceMismatch",
    workspace_store_unavailable: "error.chat.workspaceStore",
    revision_conflict: "error.chat.revisionConflict",
    workspace_managed_by_schedule: "error.chat.workspaceManaged",
    malformed_response: "error.chat.malformed",
    network_error: "error.network",
  } satisfies Record<AgentChatErrorCode, MessageKey>;
  return t(keys[code]);
}
import { defaultTranslator, type MessageKey, type Translator } from "../i18n/catalog";
import { getAuthStatus } from "./authentication";
import { apiFetch, notifyAuthenticationRequired } from "./http";
