import type { ChatSession } from "./chatClientSessions";
import type {
  RunArtifactView,
  TraceEventCountsView,
  TraceEventView,
  TraceFileChangeView,
  TracePartView,
} from "./runTraceNormalizers";

const TERMINAL_RUN_STATUSES: ReadonlySet<string> = new Set([
  "completed",
  "failed",
  "cancelled",
  "stopped",
]);

type RunTraceCollections = {
  rawEvents: TraceEventView[];
  eventCounts: TraceEventCountsView;
  parts: TracePartView[];
  artifacts: RunArtifactView[];
  fileChanges: TraceFileChangeView[];
};

type CollectionWatermark = Map<string, string>;

const FILE_CHANGE_MATCH_WINDOW_MS = 5_000;

export type RunTraceWatermark = {
  rawEvents: CollectionWatermark;
  parts: CollectionWatermark;
  artifacts: CollectionWatermark;
  fileChanges: CollectionWatermark;
};

export type SessionSnapshotFence = {
  updatedAt: number;
  statusUpdatedAt: number;
};

export type SessionHistoryRefreshRequest = {
  quiet: boolean;
  pruneMissingHistorySessions: boolean;
  includeHiddenSessions: boolean;
};

export type SessionHistoryRefreshQueue = {
  pending: SessionHistoryRefreshRequest | null;
};

type MergeSessionSnapshotOptions = {
  preserveDetails?: boolean;
  changedSinceRequest?: boolean;
  snapshotFence?: SessionSnapshotFence;
  mergeRuns?: (existing: ChatSession, incoming: ChatSession) => void;
};

function normalizedStatus(value: unknown): string {
  return String(value || "").trim();
}

function timestamp(value: unknown): number {
  const parsed = Number(value || 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function stableSerialize(value: unknown): string {
  if (value === undefined) {
    return "";
  }
  if (value === null || typeof value !== "object") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map(stableSerialize).join(",")}]`;
  }
  const record = value as Record<string, unknown>;
  return `{${Object.keys(record)
    .filter((key) => record[key] !== undefined)
    .sort()
    .map((key) => `${JSON.stringify(key)}:${stableSerialize(record[key])}`)
    .join(",")}}`;
}

function traceEventMatchKey(event: TraceEventView): string {
  return [
    "event",
    event.eventType,
    timestamp(event.createdAt),
    event.kind,
    event.status,
    stableSerialize(event.payload),
  ].join("\u0000");
}

function traceEventKey(event: TraceEventView): string {
  const eventId = String(event.id || "").trim();
  return eventId ? `event\u0000id\u0000${eventId}` : traceEventMatchKey(event);
}

function tracePartKey(part: TracePartView): string {
  const partId = String(part.partId || "").trim();
  return partId
    ? `part\u0000${partId}`
    : ["part", part.partType, timestamp(part.createdAt), part.toolName, stableSerialize(part.metadata)].join("\u0000");
}

function artifactKey(artifact: RunArtifactView): string {
  const toolCallId = String(artifact.toolCallId || "").trim();
  if (toolCallId) {
    return `artifact\u0000tool\u0000${toolCallId}`;
  }
  const path = String(artifact.path || "").trim();
  if (path) {
    return ["artifact", artifact.kind, path, artifact.action, timestamp(artifact.createdAt)].join("\u0000");
  }
  const artifactId = String(artifact.artifactId || "").trim();
  return artifactId
    ? `artifact\u0000${artifactId}`
    : ["artifact", artifact.artifactType, artifact.kind, timestamp(artifact.createdAt), artifact.source].join("\u0000");
}

function compactFileChangeDiff(value: unknown): string {
  const compacted = String(value || "").replace(/\s+/g, " ").trim();
  if (compacted.length <= 240) {
    return compacted;
  }
  return `${compacted.slice(0, 237)}...`;
}

function normalizedFileChangePreview(value: unknown): string {
  const preview = String(value || "").trim();
  return preview === "<empty>" ? "" : preview;
}

export function fileChangeCommonIdentity(change: TraceFileChangeView): string {
  const path = String(change.path || change.artifact?.path || "").trim();
  const diffPreview = normalizedFileChangePreview(change.diffPreview || change.artifact?.diffPreview)
    || compactFileChangeDiff(change.diff);
  const diffLen = timestamp(change.diffLen)
    || timestamp(change.artifact?.diffLen)
    || String(change.diff || "").length;
  return [
    "file",
    path,
    String(change.action || change.artifact?.action || "").trim(),
    String(change.toolName || change.artifact?.toolName || "").trim(),
    diffLen,
    diffPreview,
  ].join("\u0000");
}

export function fileChangesRepresentSameOccurrence(
  left: TraceFileChangeView,
  right: TraceFileChangeView,
): boolean {
  const leftId = String(left.changeId || left.sourceId || "").trim();
  const rightId = String(right.changeId || right.sourceId || "").trim();
  if (leftId && rightId && leftId === rightId) {
    return true;
  }
  return fileChangeCommonIdentity(left) === fileChangeCommonIdentity(right)
    && Math.abs(timestamp(left.createdAt) - timestamp(right.createdAt)) <= FILE_CHANGE_MATCH_WINDOW_MS;
}

function fileChangeKey(change: TraceFileChangeView): string {
  const changeId = String(change.changeId || change.sourceId || "").trim();
  return changeId
    ? `file\u0000id\u0000${changeId}`
    : `${fileChangeCommonIdentity(change)}\u0000${timestamp(change.createdAt)}`;
}

function captureCollectionWatermark<T>(items: T[], keyOf: (item: T) => string): CollectionWatermark {
  return new Map(items.map((item) => [keyOf(item), stableSerialize(item)]));
}

function mergeSnapshotCollection<T>(
  snapshotItems: T[],
  liveItems: T[],
  watermark: CollectionWatermark,
  keyOf: (item: T) => string,
): T[] {
  const merged: T[] = [];
  const indexes = new Map<string, number>();
  const snapshotKeys = new Set(snapshotItems.map(keyOf));
  const liveOverlay = liveItems.filter((item) => {
    const key = keyOf(item);
    const previousFingerprint = watermark.get(key);
    return !snapshotKeys.has(key)
      || previousFingerprint === undefined
      || previousFingerprint !== stableSerialize(item);
  });

  for (const item of [...snapshotItems, ...liveOverlay]) {
    const key = keyOf(item);
    const existingIndex = indexes.get(key);
    if (existingIndex === undefined) {
      indexes.set(key, merged.length);
      merged.push(item);
    } else {
      merged[existingIndex] = item;
    }
  }
  return merged;
}

function closestSnapshotMatch<T>(
  snapshotItems: T[],
  liveItem: T,
  matchedIndexes: ReadonlySet<number>,
  exactKeyOf: (item: T) => string,
  commonKeyOf: (item: T) => string,
  createdAtOf: (item: T) => number,
  maximumDistance = Number.POSITIVE_INFINITY,
): number {
  const exactKey = exactKeyOf(liveItem);
  if (exactKey) {
    const exactIndex = snapshotItems.findIndex(
      (item, index) => !matchedIndexes.has(index) && exactKeyOf(item) === exactKey,
    );
    if (exactIndex >= 0) {
      return exactIndex;
    }
  }

  const commonKey = commonKeyOf(liveItem);
  const liveCreatedAt = createdAtOf(liveItem);
  let bestIndex = -1;
  let bestDistance = Number.POSITIVE_INFINITY;
  snapshotItems.forEach((item, index) => {
    if (matchedIndexes.has(index) || commonKeyOf(item) !== commonKey) {
      return;
    }
    const distance = Math.abs(createdAtOf(item) - liveCreatedAt);
    if (distance <= maximumDistance && distance < bestDistance) {
      bestIndex = index;
      bestDistance = distance;
    }
  });
  return bestIndex;
}

function mergeTraceEventSnapshot(
  snapshotItems: TraceEventView[],
  liveItems: TraceEventView[],
  watermark: CollectionWatermark,
): TraceEventView[] {
  const merged = snapshotItems.slice();
  const matchedSnapshotIndexes = new Set<number>();
  for (const liveItem of liveItems) {
    const snapshotIndex = closestSnapshotMatch(
      snapshotItems,
      liveItem,
      matchedSnapshotIndexes,
      (event) => String(event.id || "").trim(),
      traceEventMatchKey,
      (event) => timestamp(event.createdAt),
    );
    if (snapshotIndex < 0) {
      merged.push(liveItem);
      continue;
    }
    matchedSnapshotIndexes.add(snapshotIndex);
    const previousFingerprint = watermark.get(traceEventKey(liveItem));
    if (previousFingerprint !== undefined && previousFingerprint !== stableSerialize(liveItem)) {
      merged[snapshotIndex] = liveItem;
    }
  }
  return merged;
}

function mergeMatchedFileChange(
  snapshot: TraceFileChangeView,
  live: TraceFileChangeView,
  liveChangedSinceRequest: boolean,
): TraceFileChangeView {
  const state = mergeMonotonicRunStatus(snapshot.state, live.state);
  const status = mergeMonotonicRunStatus(snapshot.status, live.status);
  return {
    ...live,
    ...snapshot,
    state,
    status,
    label: snapshot.label || live.label,
    diff: snapshot.diff || live.diff,
    diffPreview: liveChangedSinceRequest
      ? (live.diffPreview || snapshot.diffPreview)
      : (snapshot.diffPreview || live.diffPreview),
    beforeContent: snapshot.beforeContent ?? live.beforeContent,
    afterContent: snapshot.afterContent ?? live.afterContent,
    snapshotsAvailable: {
      before: snapshot.snapshotsAvailable.before || live.snapshotsAvailable.before,
      after: snapshot.snapshotsAvailable.after || live.snapshotsAvailable.after,
    },
    artifact: snapshot.artifact || live.artifact,
    revertSupported: snapshot.revertSupported || live.revertSupported,
  };
}

function mergeFileChangeSnapshot(
  snapshotItems: TraceFileChangeView[],
  liveItems: TraceFileChangeView[],
  watermark: CollectionWatermark,
): TraceFileChangeView[] {
  const merged = snapshotItems.slice();
  const matchedSnapshotIndexes = new Set<number>();
  for (const liveItem of liveItems) {
    const snapshotIndex = closestSnapshotMatch(
      snapshotItems,
      liveItem,
      matchedSnapshotIndexes,
      (change) => String(change.changeId || change.sourceId || "").trim(),
      fileChangeCommonIdentity,
      (change) => timestamp(change.createdAt),
      FILE_CHANGE_MATCH_WINDOW_MS,
    );
    if (snapshotIndex < 0) {
      merged.push(liveItem);
      continue;
    }
    matchedSnapshotIndexes.add(snapshotIndex);
    const previousFingerprint = watermark.get(fileChangeKey(liveItem));
    const liveChangedSinceRequest = previousFingerprint !== undefined
      && previousFingerprint !== stableSerialize(liveItem);
    merged[snapshotIndex] = mergeMatchedFileChange(
      snapshotItems[snapshotIndex],
      liveItem,
      liveChangedSinceRequest,
    );
  }
  return merged;
}

function mergeEventCounts(
  snapshot: TraceEventCountsView,
  live: TraceEventCountsView,
  returned: number,
): TraceEventCountsView {
  const total = Math.max(timestamp(snapshot.total), timestamp(live.total), returned);
  return {
    total,
    returned,
    compacted: Math.max(timestamp(snapshot.compacted), timestamp(live.compacted), total - returned),
    textTotal: Math.max(timestamp(snapshot.textTotal), timestamp(live.textTotal)),
    textReturned: Math.max(timestamp(snapshot.textReturned), timestamp(live.textReturned)),
    maxEvents: Math.max(timestamp(snapshot.maxEvents), timestamp(live.maxEvents)),
    maxTextEvents: Math.max(timestamp(snapshot.maxTextEvents), timestamp(live.maxTextEvents)),
  };
}

export function mergeMonotonicRunStatus(currentValue: unknown, incomingValue: unknown): string {
  const current = normalizedStatus(currentValue);
  const incoming = normalizedStatus(incomingValue);
  if (!incoming) {
    return current;
  }
  if (TERMINAL_RUN_STATUSES.has(current)) {
    return current;
  }
  return incoming;
}

export function beginRequestGeneration<Target extends object>(
  generations: WeakMap<Target, number>,
  target: Target,
): number {
  const generation = (generations.get(target) || 0) + 1;
  generations.set(target, generation);
  return generation;
}

export function isCurrentRequestGeneration<Target extends object>(
  generations: WeakMap<Target, number>,
  target: Target,
  generation: number,
): boolean {
  return generations.get(target) === generation;
}

export function createSessionSnapshotFence(): SessionSnapshotFence {
  return { updatedAt: 0, statusUpdatedAt: 0 };
}

export function createSessionHistoryRefreshQueue(): SessionHistoryRefreshQueue {
  return { pending: null };
}

export function coalesceSessionHistoryRefreshRequest(
  current: SessionHistoryRefreshRequest | null,
  incoming: SessionHistoryRefreshRequest,
): SessionHistoryRefreshRequest {
  return {
    quiet: incoming.quiet,
    includeHiddenSessions: incoming.includeHiddenSessions,
    pruneMissingHistorySessions: Boolean(
      current?.pruneMissingHistorySessions || incoming.pruneMissingHistorySessions,
    ),
  };
}

export function enqueueSessionHistoryRefresh(
  queue: SessionHistoryRefreshQueue,
  request: SessionHistoryRefreshRequest,
): void {
  queue.pending = coalesceSessionHistoryRefreshRequest(queue.pending, request);
}

export function takePendingSessionHistoryRefresh(
  queue: SessionHistoryRefreshQueue,
): SessionHistoryRefreshRequest | null {
  const pending = queue.pending;
  queue.pending = null;
  return pending;
}

export function captureRunTraceWatermark(trace: RunTraceCollections): RunTraceWatermark {
  return {
    rawEvents: captureCollectionWatermark(trace.rawEvents || [], traceEventKey),
    parts: captureCollectionWatermark(trace.parts || [], tracePartKey),
    artifacts: captureCollectionWatermark(trace.artifacts || [], artifactKey),
    fileChanges: captureCollectionWatermark(trace.fileChanges || [], fileChangeKey),
  };
}

export function mergeRunTraceSnapshot(
  snapshot: RunTraceCollections,
  live: RunTraceCollections,
  watermark: RunTraceWatermark,
): RunTraceCollections {
  const rawEvents = mergeTraceEventSnapshot(snapshot.rawEvents || [], live.rawEvents || [], watermark.rawEvents);
  return {
    rawEvents,
    eventCounts: mergeEventCounts(snapshot.eventCounts, live.eventCounts, rawEvents.length),
    parts: mergeSnapshotCollection(snapshot.parts || [], live.parts || [], watermark.parts, tracePartKey),
    artifacts: mergeSnapshotCollection(snapshot.artifacts || [], live.artifacts || [], watermark.artifacts, artifactKey),
    fileChanges: mergeFileChangeSnapshot(snapshot.fileChanges || [], live.fileChanges || [], watermark.fileChanges),
  };
}

export function mergeFreshSessionSnapshot(
  existing: ChatSession,
  incoming: ChatSession,
  options: MergeSessionSnapshotOptions = {},
): ChatSession {
  const changedSinceRequest = Boolean(options.changedSinceRequest);
  const snapshotFence = options.snapshotFence;
  const incomingUpdatedAt = timestamp(incoming.updatedAt);
  const existingUpdatedAt = timestamp(existing.updatedAt);
  const fencedUpdatedAt = timestamp(snapshotFence?.updatedAt);
  const incomingPassesFence = !fencedUpdatedAt || incomingUpdatedAt > fencedUpdatedAt;
  const incomingIsCurrent = !changedSinceRequest
    && incomingPassesFence
    && incomingUpdatedAt >= existingUpdatedAt;

  existing.channel = incoming.channel || existing.channel;
  existing.hiddenFromBrowserHistory = incoming.hiddenFromBrowserHistory;
  existing.transportExternalChatId = incoming.transportExternalChatId || existing.transportExternalChatId;
  existing.sessionId = incoming.sessionId || existing.sessionId;

  if (incomingIsCurrent) {
    existing.title = incoming.title;
  }
  existing.updatedAt = Math.max(existingUpdatedAt, incomingUpdatedAt);

  const incomingStatusAt = timestamp(incoming.status?.updatedAt);
  const existingStatusAt = timestamp(existing.status?.updatedAt);
  const fencedStatusUpdatedAt = timestamp(snapshotFence?.statusUpdatedAt);
  const incomingStatusPassesFence = !fencedStatusUpdatedAt || incomingStatusAt > fencedStatusUpdatedAt;
  const incomingStatusIsCurrent = !changedSinceRequest
    && incomingStatusPassesFence
    && incomingStatusAt >= existingStatusAt;
  if (incomingStatusIsCurrent) {
    existing.status = incoming.status;
  }

  if (changedSinceRequest && snapshotFence) {
    snapshotFence.updatedAt = Math.max(fencedUpdatedAt, incomingUpdatedAt);
    snapshotFence.statusUpdatedAt = Math.max(fencedStatusUpdatedAt, incomingStatusAt);
  }

  if (!options.preserveDetails && incomingIsCurrent) {
    existing.messages = incoming.messages;
    existing.entries = incoming.entries;
    if (options.mergeRuns) {
      options.mergeRuns(existing, incoming);
    } else {
      existing.runs = incoming.runs;
      existing.activeRunId = incoming.activeRunId;
    }
  }
  return existing;
}
