import { buildMessageBlocks } from "./messageMarkdown";

type AnyRecord = Record<string, any>;

const TRACE_MATCH_WINDOW_MS = 5000;

export function normalizeMessages({
  copy,
  entries,
  messages,
  runs,
  displayName,
}: {
  copy: AnyRecord;
  entries: AnyRecord[];
  messages: AnyRecord[];
  runs: AnyRecord[];
  displayName: string;
}) {
  const references = buildRunReferences(entries, runs);
  if (entries?.length) {
    return entries.filter(isChatEntry).map((entry, index) => normalizeEntry(copy, entry, index, displayName, references)).filter(Boolean);
  }
  return (messages || []).map((message, index) => normalizeMessage(copy, message, index, displayName, references)).filter((message) => message.text.trim());
}

export function artifactTypeLabel(copy: AnyRecord, type: string) {
  const labels = copy.message.artifactTypes || {};
  return labels[type] || type;
}

export function artifactStatusLabel(copy: AnyRecord, status: string) {
  const labels = copy.run?.statusLabels || {};
  return labels[status] || status;
}

function buildRunReferences(entries: AnyRecord[] = [], runs: AnyRecord[] = []) {
  const references = new Map<string, AnyRecord>();
  for (const run of runs || []) {
    upsertRunReference(references, normalizeRunReference(run));
  }
  for (const entry of entries || []) {
    upsertRunReference(references, normalizeRunReference(entry));
  }
  return Array.from(references.values()).sort((left, right) => Number(left.createdAt || 0) - Number(right.createdAt || 0));
}

function normalizeEntry(copy: AnyRecord, entry: AnyRecord, index: number, displayName: string, references: AnyRecord[]) {
  const role = entry.role === "user" ? "user" : "assistant";
  const content = Array.isArray(entry.content) ? entry.content.map((part: AnyRecord, partIndex: number) => normalizeTextPart(copy, part, partIndex)).filter(Boolean) : [];
  const text = sanitizeVisibleText(entry.text || "");
  if (!text && content.length === 0) {
    return null;
  }
  return {
    id: entry.id || `entry-${index}`,
    role,
    text,
    textBlocks: buildMessageBlocks(copy, text, `entry-${index}`),
    meta: entry.meta || (role === "user" ? displayName : "OpenSprite"),
    ...messageTimeFields(entry.createdAt ?? entry.created_at),
    content,
    traceRunId: findTraceRunIdForEntry(entry, role, references),
  };
}

function normalizeMessage(copy: AnyRecord, message: AnyRecord, index: number, displayName: string, references: AnyRecord[]) {
  const text = sanitizeVisibleText(message.text);
  const role = message.role === "user" ? "user" : "assistant";
  return {
    ...message,
    id: message.id || `message-${index}`,
    role,
    text,
    textBlocks: buildMessageBlocks(copy, text, message.id || `message-${index}`),
    meta: message.meta || (role === "user" ? displayName : "OpenSprite"),
    ...messageTimeFields(message.createdAt ?? message.created_at),
    content: [],
    traceRunId: findTraceRunIdForEntry(message, role, references),
  };
}

function normalizeTextPart(copy: AnyRecord, part: AnyRecord, index: number) {
  const text = sanitizeVisibleText(part?.text || part?.detail || "");
  if (!text) {
    return null;
  }
  return {
    id: part?.id || `text-${index}`,
    type: "text",
    text,
    textBlocks: buildMessageBlocks(copy, text, `part-${index}`),
  };
}

function isRunEntry(entry: AnyRecord) {
  const runId = String(entry?.runId || entry?.run_id || "").trim();
  const entryId = String(entry?.id || entry?.entry_id || entry?.entryId || "").trim();
  if (entryId.startsWith("run:")) {
    return true;
  }
  const entryType = String(entry?.type || entry?.entry_type || entry?.entryType || "").trim();
  if (entryType === "run") {
    return true;
  }
  const text = sanitizeVisibleText(entry?.text || "");
  const content = Array.isArray(entry?.content) ? entry.content : [];
  return Boolean(runId && !text && content.length === 0);
}

function isChatEntry(entry: AnyRecord) {
  if (isRunEntry(entry)) {
    return false;
  }
  return entry?.role === "user" || entry?.role === "assistant";
}

function findTraceRunIdForEntry(entry: AnyRecord, role: string, references: AnyRecord[]) {
  if (role !== "assistant") {
    return "";
  }
  const directRunId = getEntryRunId(entry);
  if (directRunId) {
    return directRunId;
  }
  const createdAt = normalizeTimestamp(entry?.createdAt ?? entry?.created_at);
  if (!createdAt) {
    return "";
  }
  const matches = references
    .filter((run) => run.createdAt && run.updatedAt)
    .filter((run) => createdAt >= run.createdAt - TRACE_MATCH_WINDOW_MS && createdAt <= run.updatedAt + TRACE_MATCH_WINDOW_MS)
    .sort((left, right) => Math.abs(Number(left.updatedAt || 0) - createdAt) - Math.abs(Number(right.updatedAt || 0) - createdAt));
  return matches[0]?.runId || "";
}

function getEntryRunId(entry: AnyRecord) {
  return String(entry?.runId || entry?.run_id || entry?.metadata?.runId || entry?.metadata?.run_id || "").trim();
}

function normalizeRunReference(source: AnyRecord) {
  const runId = getEntryRunId(source);
  if (!runId) {
    return null;
  }
  const createdAt = normalizeTimestamp(source?.createdAt ?? source?.created_at);
  const updatedAt = normalizeTimestamp(source?.finishedAt ?? source?.finished_at ?? source?.updatedAt ?? source?.updated_at);
  return {
    runId,
    status: String(source?.status || "").trim(),
    createdAt,
    updatedAt: updatedAt || createdAt,
  };
}

function upsertRunReference(references: Map<string, AnyRecord>, next: AnyRecord | null) {
  if (!next?.runId) {
    return;
  }
  const existing = references.get(next.runId);
  if (!existing) {
    references.set(next.runId, next);
    return;
  }
  existing.status = next.status || existing.status;
  existing.createdAt = minPositiveTimestamp(existing.createdAt, next.createdAt);
  existing.updatedAt = Math.max(Number(existing.updatedAt || 0), Number(next.updatedAt || 0));
}

function minPositiveTimestamp(left: number, right: number) {
  const leftValue = Number(left || 0);
  const rightValue = Number(right || 0);
  if (leftValue > 0 && rightValue > 0) {
    return Math.min(leftValue, rightValue);
  }
  return leftValue || rightValue || 0;
}

function normalizeTimestamp(value: any) {
  const timestamp = Number(value || 0);
  if (!Number.isFinite(timestamp) || timestamp <= 0) {
    return 0;
  }
  return timestamp > 1_000_000_000_000 ? timestamp : timestamp * 1000;
}

function sanitizeVisibleText(value: any) {
  return String(value || "")
    .replace(/<\s*(think|thinking|system-reminder)\b[^>]*>[\s\S]*?<\s*\/\s*\1\s*>/gi, "")
    .replace(/<\s*(think|thinking|system-reminder)\b[^>]*>[\s\S]*$/i, "")
    .trim();
}

function messageTimeFields(value: any) {
  const timestamp = Number(value || 0);
  if (!Number.isFinite(timestamp) || timestamp <= 0) {
    return { isoTime: "", timeLabel: "", fullTimeLabel: "" };
  }
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return { isoTime: "", timeLabel: "", fullTimeLabel: "" };
  }
  return {
    isoTime: date.toISOString(),
    timeLabel: new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" }).format(date),
    fullTimeLabel: new Intl.DateTimeFormat(undefined, {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(date),
  };
}
