import {
  generateExternalChatId,
  isExternalChannelSessionId,
} from "./chatClientSessionIds";

function randomToken() {
  return Math.random().toString(36).slice(2, 8);
}

export function makeMessage(role, text, meta) {
  return {
    id: `msg-${Date.now().toString(36)}-${randomToken()}`,
    role,
    text,
    meta,
    createdAt: Date.now(),
  };
}

export function makeLiveEntry(message) {
  const role = message?.role === "user" ? "user" : "assistant";
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

export function summarizeTitle(text) {
  const singleLine = text.trim().replace(/\s+/g, " ");
  if (!singleLine) {
    return "New chat";
  }
  return singleLine.length > 30 ? `${singleLine.slice(0, 30)}...` : singleLine;
}

export function createSession(externalChatId) {
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
    workState: null,
    activeRunId: null,
    runs: [],
    runsLoaded: false,
    runsLoading: false,
    runsError: "",
  };
}

export function isLocalDraftSession(session) {
  return Boolean(session)
    && (!session.channel || session.channel === "web")
    && !session.sessionId
    && !session.messages?.length
    && !session.entries?.length
    && !session.runs?.length;
}

export function normalizeStoredDraftSession(payload, normalizeEventTimestamp) {
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

export function readStoredDraftSessions(storageKey, normalizeEventTimestamp) {
  try {
    const raw = localStorage.getItem(storageKey);
    const drafts = raw ? JSON.parse(raw) : [];
    return Array.isArray(drafts)
      ? drafts
          .map((draft) => normalizeStoredDraftSession(draft, normalizeEventTimestamp))
          .filter(Boolean)
      : [];
  } catch {
    return [];
  }
}

export function writeStoredDraftSessions(sessions, storageKey, limit) {
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
