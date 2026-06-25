import { generateExternalChatId } from "./chatClientSessionIds";

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
