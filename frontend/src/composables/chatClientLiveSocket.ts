import { toPayloadSource } from "./payloadBoundary";

const LIVE_SOCKET_TYPES = ["session", "message", "run_event", "session_status", "error"] as const;
type LiveSocketType = (typeof LIVE_SOCKET_TYPES)[number];

const LIVE_SOCKET_TYPE_SET: ReadonlySet<string> = new Set<string>(LIVE_SOCKET_TYPES);

type LiveSocketPayload = {
  type?: unknown;
  text?: unknown;
  error?: unknown;
  session_id?: unknown;
  sessionId?: unknown;
  channel?: unknown;
  external_chat_id?: unknown;
  externalChatId?: unknown;
  status?: unknown;
  updated_at?: unknown;
  updatedAt?: unknown;
  metadata?: unknown;
  run_id?: unknown;
  runId?: unknown;
  event_type?: unknown;
  eventType?: unknown;
  payload?: unknown;
  artifact?: unknown;
  kind?: unknown;
  created_at?: unknown;
  createdAt?: unknown;
};

export type LiveSessionIdentityPayload = Pick<
  LiveSocketPayload,
  "session_id" | "sessionId" | "channel" | "external_chat_id" | "externalChatId"
>;

export type LiveSessionStatusPayload = LiveSessionIdentityPayload & Pick<
  LiveSocketPayload,
  "status" | "updated_at" | "updatedAt" | "metadata"
>;

export type LiveAssistantMessagePayload = LiveSessionIdentityPayload & Pick<LiveSocketPayload, "text">;
export type LiveSocketErrorPayload = Pick<LiveSocketPayload, "error" | "text">;
export type LiveRunEventPayload = LiveSessionIdentityPayload & Pick<
  LiveSocketPayload,
  "run_id" | "runId" | "event_type" | "eventType" | "payload" | "artifact" | "kind" | "status" | "created_at" | "createdAt"
>;

export type LiveSocketEvent =
  | { type: "session"; payload: LiveSessionIdentityPayload }
  | { type: "message"; payload: LiveAssistantMessagePayload }
  | { type: "run_event"; payload: LiveRunEventPayload }
  | { type: "session_status"; payload: LiveSessionStatusPayload }
  | { type: "error"; payload: LiveSocketErrorPayload };

export type LiveSocketMessageParseResult =
  | { kind: "invalid" }
  | { kind: "unsupported" }
  | { kind: "event"; event: LiveSocketEvent };

function toLiveSocketPayload(value: unknown): LiveSocketPayload | null {
  const payload = toPayloadSource<LiveSocketPayload>(value);
  if (!payload) {
    return null;
  }
  return {
    type: payload.type,
    text: payload.text,
    error: payload.error,
    session_id: payload.session_id,
    sessionId: payload.sessionId,
    channel: payload.channel,
    external_chat_id: payload.external_chat_id,
    externalChatId: payload.externalChatId,
    status: payload.status,
    updated_at: payload.updated_at,
    updatedAt: payload.updatedAt,
    metadata: payload.metadata,
    run_id: payload.run_id,
    runId: payload.runId,
    event_type: payload.event_type,
    eventType: payload.eventType,
    payload: payload.payload,
    artifact: payload.artifact,
    kind: payload.kind,
    created_at: payload.created_at,
    createdAt: payload.createdAt,
  };
}

function toLiveSessionIdentityPayload(payload: LiveSocketPayload): LiveSessionIdentityPayload {
  return {
    session_id: payload.session_id,
    sessionId: payload.sessionId,
    channel: payload.channel,
    external_chat_id: payload.external_chat_id,
    externalChatId: payload.externalChatId,
  };
}

function toLiveRunEventPayload(payload: LiveSocketPayload): LiveRunEventPayload {
  return {
    session_id: payload.session_id,
    sessionId: payload.sessionId,
    channel: payload.channel,
    external_chat_id: payload.external_chat_id,
    externalChatId: payload.externalChatId,
    run_id: payload.run_id,
    runId: payload.runId,
    event_type: payload.event_type,
    eventType: payload.eventType,
    payload: payload.payload,
    artifact: payload.artifact,
    kind: payload.kind,
    status: payload.status,
    created_at: payload.created_at,
    createdAt: payload.createdAt,
  };
}

function toLiveSessionStatusPayload(payload: LiveSocketPayload): LiveSessionStatusPayload {
  return {
    session_id: payload.session_id,
    sessionId: payload.sessionId,
    channel: payload.channel,
    external_chat_id: payload.external_chat_id,
    externalChatId: payload.externalChatId,
    status: payload.status,
    updated_at: payload.updated_at,
    updatedAt: payload.updatedAt,
    metadata: payload.metadata,
  };
}

function toLiveAssistantMessagePayload(payload: LiveSocketPayload): LiveAssistantMessagePayload {
  return {
    session_id: payload.session_id,
    sessionId: payload.sessionId,
    channel: payload.channel,
    external_chat_id: payload.external_chat_id,
    externalChatId: payload.externalChatId,
    text: payload.text,
  };
}

function toLiveSocketErrorPayload(payload: LiveSocketPayload): LiveSocketErrorPayload {
  return {
    error: payload.error,
    text: payload.text,
  };
}

function isLiveSocketType(value: string): value is LiveSocketType {
  return LIVE_SOCKET_TYPE_SET.has(value);
}

function normalizeLiveSocketType(value: unknown): LiveSocketType | "" {
  const payloadType = String(value || "").trim();
  return isLiveSocketType(payloadType) ? payloadType : "";
}

function toLiveSocketEvent(payload: LiveSocketPayload): LiveSocketEvent | null {
  const type = normalizeLiveSocketType(payload.type);
  if (type === "session") {
    return { type, payload: toLiveSessionIdentityPayload(payload) };
  }
  if (type === "message") {
    return { type, payload: toLiveAssistantMessagePayload(payload) };
  }
  if (type === "run_event") {
    return { type, payload: toLiveRunEventPayload(payload) };
  }
  if (type === "session_status") {
    return { type, payload: toLiveSessionStatusPayload(payload) };
  }
  if (type === "error") {
    return { type, payload: toLiveSocketErrorPayload(payload) };
  }
  return null;
}

export function parseLiveSocketMessage(rawData: string): LiveSocketMessageParseResult {
  let parsedPayload: unknown;
  try {
    parsedPayload = JSON.parse(rawData);
  } catch {
    return { kind: "invalid" };
  }

  const payload = toLiveSocketPayload(parsedPayload);
  if (!payload) {
    return { kind: "invalid" };
  }

  const event = toLiveSocketEvent(payload);
  return event ? { kind: "event", event } : { kind: "unsupported" };
}
