import {
  generateExternalChatId,
  isExternalChannelSessionId,
} from "./chatClientSessionIds";
import type { RunViewState } from "./chatClientRunHelpers";
import type { RunArtifactView } from "./runTraceNormalizers";
import { randomToken } from "./chatClientTokens";
import { toPayloadSource } from "./payloadBoundary";

export const SESSION_CHANNEL_FILTERS = ["all", "web"] as const;
export type SessionChannelFilter = (typeof SESSION_CHANNEL_FILTERS)[number];

export function normalizeSessionChannelFilter(value: unknown): SessionChannelFilter {
  return value === "web" ? "web" : "all";
}

export type ChatMessageRole = "user" | "assistant";

export function normalizeChatMessageRole(value: unknown): ChatMessageRole {
  return value === "user" ? "user" : "assistant";
}

export interface ChatMessage {
  id: string;
  role: ChatMessageRole;
  text: string;
  meta: string;
  createdAt: number;
  traceRunId?: string;
}

export interface LiveEntryContentItem {
  id: string;
  type: string;
  status: string;
  title: string;
  detail: string;
  text: string;
  createdAt: number;
  artifact: RunArtifactView | null;
}

export type LiveEntryMetadataPayload = {
  sender_name?: unknown;
  sender_id?: unknown;
  run_id?: unknown;
  runId?: unknown;
};
export type LiveEntryMetadata = {
  sender_name?: string;
  sender_id?: string;
  run_id?: string;
  runId?: string;
};

export interface LiveEntry {
  id: string;
  type: string;
  role: ChatMessageRole;
  runId: string;
  status: string;
  text: string;
  content: LiveEntryContentItem[];
  meta: string;
  createdAt: number;
  updatedAt: number;
  metadata: LiveEntryMetadata;
}

export type ChatSessionStatusMetadata = Record<string, never>;

export interface ChatSessionStatus {
  status: string;
  updatedAt: number;
  metadata: ChatSessionStatusMetadata;
}

export interface ChatSession {
  externalChatId: string;
  transportExternalChatId: string;
  channel: string;
  sessionId: string | null;
  title: string;
  updatedAt: number;
  messages: ChatMessage[];
  entries: LiveEntry[];
  hiddenFromBrowserHistory: boolean;
  status: ChatSessionStatus;
  activeRunId: string | null;
  runs: RunViewState[];
  runsLoaded: boolean;
  runsLoading: boolean;
  runsError: string;
}

type TimestampNormalizer = (value: unknown) => number;

type StoredDraftSessionPayload = {
  externalChatId?: unknown;
  title?: unknown;
  updatedAt?: unknown;
};

function toStoredDraftSessionPayload(value: unknown): StoredDraftSessionPayload | null {
  const payload = toPayloadSource<StoredDraftSessionPayload>(value);
  return payload
    ? {
        externalChatId: payload.externalChatId,
        title: payload.title,
        updatedAt: payload.updatedAt,
      }
    : null;
}

export function makeMessage(role: ChatMessageRole, text: string, meta: string): ChatMessage {
  return {
    id: `msg-${Date.now().toString(36)}-${randomToken()}`,
    role,
    text,
    meta,
    createdAt: Date.now(),
  };
}

export function makeLiveEntry(message: Partial<ChatMessage> | null | undefined): LiveEntry {
  const role = normalizeChatMessageRole(message?.role);
  const createdAt = Number(message?.createdAt || Date.now());
  const text = String(message?.text || "");
  return {
    id: `live-entry-${createdAt.toString(36)}-${randomToken()}`,
    type: role,
    role,
    runId: "",
    status: "",
    text,
    content: [],
    meta: message?.meta || (role === "user" ? "You" : "OpenSprite"),
    createdAt,
    updatedAt: createdAt,
    metadata: {},
  };
}

export function summarizeTitle(text: string): string {
  const singleLine = text.trim().replace(/\s+/g, " ");
  if (!singleLine) {
    return "New chat";
  }
  return singleLine.length > 30 ? `${singleLine.slice(0, 30)}...` : singleLine;
}

export function createSession(externalChatId?: string): ChatSession {
  return {
    externalChatId: externalChatId || generateExternalChatId(),
    transportExternalChatId: externalChatId || "",
    channel: "web",
    sessionId: null,
    title: "New chat",
    updatedAt: Date.now(),
    messages: [],
    entries: [],
    hiddenFromBrowserHistory: false,
    status: { status: "idle", updatedAt: Date.now(), metadata: {} },
    activeRunId: null,
    runs: [],
    runsLoaded: false,
    runsLoading: false,
    runsError: "",
  };
}

export function isLocalDraftSession(session: Partial<ChatSession> | null | undefined): boolean {
  return Boolean(session)
    && (!session.channel || session.channel === "web")
    && !session.sessionId
    && !session.messages?.length
    && !session.entries?.length
    && !session.runs?.length;
}

export function normalizeStoredDraftSession(
  value: unknown,
  normalizeEventTimestamp: TimestampNormalizer,
): ChatSession | null {
  const payload = toStoredDraftSessionPayload(value);
  const externalChatId = String(payload?.externalChatId || "").trim();
  if (!externalChatId || isExternalChannelSessionId(externalChatId)) {
    return null;
  }
  const session = createSession(externalChatId);
  session.title = String(payload?.title || "").trim() || "New chat";
  session.updatedAt = normalizeEventTimestamp(payload?.updatedAt);
  session.status = {
    status: "idle",
    updatedAt: session.updatedAt,
    metadata: {},
  };
  return session;
}

export function readStoredDraftSessions(
  storageKey: string,
  normalizeEventTimestamp: TimestampNormalizer,
): ChatSession[] {
  try {
    const raw = localStorage.getItem(storageKey);
    const drafts: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(drafts)
      ? drafts
          .map((draft) => normalizeStoredDraftSession(draft, normalizeEventTimestamp))
          .filter(Boolean)
      : [];
  } catch {
    return [];
  }
}

export function writeStoredDraftSessions(sessions: ChatSession[], storageKey: string, limit: number): void {
  try {
    const drafts = sessions
      .filter(isLocalDraftSession)
      .sort((left, right) => right.updatedAt - left.updatedAt)
      .slice(0, limit)
      .map((session) => ({
        externalChatId: session.externalChatId,
        title: session.title,
        updatedAt: session.updatedAt,
      }));
    localStorage.setItem(storageKey, JSON.stringify(drafts));
  } catch {
    return;
  }
}
