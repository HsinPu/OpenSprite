import { toPayloadSource } from "./payloadBoundary";

export type SessionHistoryPayload = {
  sessions?: Array<HistorySessionPayload | null>;
  total?: unknown;
  limit?: unknown;
  channel_totals?: unknown;
  channelTotals?: unknown;
};

type SessionHistoryChannelTotalsSource = Record<string, unknown>;

export type SessionHistoryChannelTotals = Record<string, number>;

export type SessionHistoryMetrics = {
  total: number;
  limit: number;
  channelTotals: SessionHistoryChannelTotals;
};

export type SessionClearPayload = {
  deleted?: unknown;
  deleted_count?: unknown;
  deletedCount?: unknown;
};

export type HistoryRunPayload = {
  run_id?: unknown;
  runId?: unknown;
  session_id?: unknown;
  sessionId?: unknown;
  status?: unknown;
  created_at?: unknown;
  createdAt?: unknown;
  updated_at?: unknown;
  updatedAt?: unknown;
  finished_at?: unknown;
  finishedAt?: unknown;
};

export type HistoryMessageMetadata = {
  sender_name?: unknown;
  sender_id?: unknown;
};

export type HistoryMessagePayload = {
  role?: unknown;
  content?: unknown;
  created_at?: unknown;
  createdAt?: unknown;
  metadata?: HistoryMessageMetadata;
};

export type HistoryEntryContentPayload = {
  part_id?: unknown;
  partId?: unknown;
  artifact_id?: unknown;
  artifactId?: unknown;
  type?: unknown;
  status?: unknown;
  title?: unknown;
  detail?: unknown;
  text?: unknown;
  created_at?: unknown;
  createdAt?: unknown;
  artifact?: unknown;
};

export type HistoryEntryPayload = {
  entry_id?: unknown;
  entryId?: unknown;
  entry_type?: unknown;
  entryType?: unknown;
  role?: unknown;
  run_id?: unknown;
  runId?: unknown;
  status?: unknown;
  text?: unknown;
  content?: Array<HistoryEntryContentPayload | null>;
  created_at?: unknown;
  createdAt?: unknown;
  updated_at?: unknown;
  updatedAt?: unknown;
  metadata?: unknown;
};

export type HistorySessionPayload = {
  session_id?: unknown;
  channel?: unknown;
  external_chat_id?: unknown;
  hidden_from_browser_history?: unknown;
  hiddenFromBrowserHistory?: unknown;
  title?: unknown;
  updated_at?: unknown;
  messages?: HistoryMessagePayload[];
  entries?: Array<HistoryEntryPayload | null>;
  runs?: Array<HistoryRunPayload | null>;
  work_state?: unknown;
  status?: HistorySessionStatusPayload;
};

export type HistorySessionStatusPayload = {
  status?: unknown;
  updated_at?: unknown;
  updatedAt?: unknown;
  metadata?: unknown;
};

function projectNullablePayloadList<Payload>(
  value: unknown,
  projector: (item: unknown) => Payload | null,
): Array<Payload | null> {
  return Array.isArray(value) ? value.map(projector) : [];
}

function toHistoryMessagePayloadList(value: unknown): HistoryMessagePayload[] {
  return Array.isArray(value) ? value.map(toHistoryMessagePayload) : [];
}

function toHistoryEntryContentPayloadList(value: unknown): Array<HistoryEntryContentPayload | null> {
  return projectNullablePayloadList(value, toHistoryEntryContentPayload);
}

function toHistoryEntryPayloadList(value: unknown): Array<HistoryEntryPayload | null> {
  return projectNullablePayloadList(value, toHistoryEntryPayload);
}

function toHistorySessionPayloadList(value: unknown): Array<HistorySessionPayload | null> {
  return projectNullablePayloadList(value, toHistorySessionPayload);
}

export function toHistoryRunPayloadList(value: unknown): Array<HistoryRunPayload | null> {
  return projectNullablePayloadList(value, toHistoryRunPayload);
}

function normalizeSessionHistoryCount(value: unknown, fallback: number): number {
  const count = Number(value);
  if (!Number.isFinite(count) || count < 0) {
    return Math.max(0, Math.floor(fallback));
  }
  return Math.floor(count);
}

function normalizeSessionHistoryChannelTotals(value: unknown, fallbackTotal: number): SessionHistoryChannelTotals {
  const source = toPayloadSource<SessionHistoryChannelTotalsSource>(value);
  const totals: SessionHistoryChannelTotals = {};
  if (source) {
    for (const [channel, count] of Object.entries(source)) {
      const key = String(channel || "").trim();
      if (key) {
        totals[key] = normalizeSessionHistoryCount(count, key === "all" ? fallbackTotal : 0);
      }
    }
  }
  if (!Object.prototype.hasOwnProperty.call(totals, "all")) {
    totals.all = normalizeSessionHistoryCount(fallbackTotal, 0);
  }
  return totals;
}

export function normalizeSessionHistoryMetrics(
  payload: SessionHistoryPayload | null,
  fallbackCount: number,
): SessionHistoryMetrics {
  const total = normalizeSessionHistoryCount(payload?.total, fallbackCount);
  return {
    total,
    limit: normalizeSessionHistoryCount(payload?.limit, fallbackCount),
    channelTotals: normalizeSessionHistoryChannelTotals(
      payload?.channel_totals ?? payload?.channelTotals,
      total,
    ),
  };
}

export function toSessionHistoryPayload(value: unknown): SessionHistoryPayload | null {
  const payload = toPayloadSource<SessionHistoryPayload>(value);
  if (!payload) {
    return null;
  }
  return {
    sessions: toHistorySessionPayloadList(payload.sessions),
    total: payload.total,
    limit: payload.limit,
    channel_totals: payload.channel_totals,
    channelTotals: payload.channelTotals,
  };
}

export function toSessionClearPayload(value: unknown): SessionClearPayload | null {
  const payload = toPayloadSource<SessionClearPayload>(value);
  if (!payload) {
    return null;
  }
  return {
    deleted: payload.deleted,
    deleted_count: payload.deleted_count,
    deletedCount: payload.deletedCount,
  };
}

function toHistoryRunPayload(value: unknown): HistoryRunPayload | null {
  const payload = toPayloadSource<HistoryRunPayload>(value);
  if (!payload) {
    return null;
  }
  return {
    run_id: payload.run_id,
    runId: payload.runId,
    session_id: payload.session_id,
    sessionId: payload.sessionId,
    status: payload.status,
    created_at: payload.created_at,
    createdAt: payload.createdAt,
    updated_at: payload.updated_at,
    updatedAt: payload.updatedAt,
    finished_at: payload.finished_at,
    finishedAt: payload.finishedAt,
  };
}

function toHistoryMessagePayload(value: unknown): HistoryMessagePayload {
  const payload = toPayloadSource<HistoryMessagePayload>(value);
  if (!payload) {
    return {};
  }
  return {
    role: payload.role,
    content: payload.content,
    created_at: payload.created_at,
    createdAt: payload.createdAt,
    metadata: toHistoryMessageMetadata(payload.metadata),
  };
}

function toHistoryMessageMetadata(value: unknown): HistoryMessageMetadata {
  const payload = toPayloadSource<HistoryMessageMetadata>(value);
  if (!payload) {
    return {};
  }
  return {
    sender_name: payload.sender_name,
    sender_id: payload.sender_id,
  };
}

function toHistoryEntryContentPayload(value: unknown): HistoryEntryContentPayload | null {
  const payload = toPayloadSource<HistoryEntryContentPayload>(value);
  if (!payload) {
    return null;
  }
  return {
    part_id: payload.part_id,
    partId: payload.partId,
    artifact_id: payload.artifact_id,
    artifactId: payload.artifactId,
    type: payload.type,
    status: payload.status,
    title: payload.title,
    detail: payload.detail,
    text: payload.text,
    created_at: payload.created_at,
    createdAt: payload.createdAt,
    artifact: payload.artifact,
  };
}

function toHistoryEntryPayload(value: unknown): HistoryEntryPayload | null {
  const payload = toPayloadSource<HistoryEntryPayload>(value);
  if (!payload) {
    return null;
  }
  return {
    entry_id: payload.entry_id,
    entryId: payload.entryId,
    entry_type: payload.entry_type,
    entryType: payload.entryType,
    role: payload.role,
    run_id: payload.run_id,
    runId: payload.runId,
    status: payload.status,
    text: payload.text,
    content: toHistoryEntryContentPayloadList(payload.content),
    created_at: payload.created_at,
    createdAt: payload.createdAt,
    updated_at: payload.updated_at,
    updatedAt: payload.updatedAt,
    metadata: payload.metadata,
  };
}

function toHistorySessionPayload(value: unknown): HistorySessionPayload | null {
  const payload = toPayloadSource<HistorySessionPayload>(value);
  if (!payload) {
    return null;
  }
  return {
    session_id: payload.session_id,
    channel: payload.channel,
    external_chat_id: payload.external_chat_id,
    hidden_from_browser_history: payload.hidden_from_browser_history,
    hiddenFromBrowserHistory: payload.hiddenFromBrowserHistory,
    title: payload.title,
    updated_at: payload.updated_at,
    messages: toHistoryMessagePayloadList(payload.messages),
    entries: toHistoryEntryPayloadList(payload.entries),
    runs: toHistoryRunPayloadList(payload.runs),
    work_state: payload.work_state,
    status: toHistorySessionStatusPayload(payload.status),
  };
}

function toHistorySessionStatusPayload(value: unknown): HistorySessionStatusPayload {
  const payload = toPayloadSource<HistorySessionStatusPayload>(value);
  if (!payload) {
    return {};
  }
  return {
    status: payload.status,
    updated_at: payload.updated_at,
    updatedAt: payload.updatedAt,
    metadata: payload.metadata,
  };
}
