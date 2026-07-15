import { coerceNonNegativeInteger } from "./chatClientCoercion";
import { toPayloadList, toPayloadSource } from "./payloadBoundary";

type EntryCount = [string, number];
type DiffSummaryActionsPayload = {
  [action: string]: unknown;
};
type DiffSummaryActionEntry = [string, unknown];

export type DiffSummaryView = {
  schemaVersion: number;
  changedFiles: number;
  changeCount: number;
  additions: number;
  deletions: number;
  paths: string[];
  actions: Record<string, number>;
};

type DiffSummaryPayload = {
  schema_version?: unknown;
  schemaVersion?: unknown;
  changed_files?: unknown;
  changedFiles?: unknown;
  change_count?: unknown;
  changeCount?: unknown;
  additions?: unknown;
  deletions?: unknown;
  paths?: unknown;
  actions?: unknown;
};

type RunSummaryToolPayload = {
  name?: unknown;
};

type RunSummaryFileChangePayload = {
  path?: unknown;
};

export type RunSummaryView = {
  status: string;
  durationSeconds: number | null;
  toolCount: number;
  fileChangeCount: number;
};

type RunSummaryPayload = {
  status?: unknown;
  duration_seconds?: unknown;
  durationSeconds?: unknown;
  tools?: unknown;
  file_changes?: unknown;
  fileChanges?: unknown;
};

function toDiffSummaryPayload(value: unknown): DiffSummaryPayload | null {
  const payload = toPayloadSource<DiffSummaryPayload>(value);
  return payload
    ? {
        schema_version: payload.schema_version,
        schemaVersion: payload.schemaVersion,
        changed_files: payload.changed_files,
        changedFiles: payload.changedFiles,
        change_count: payload.change_count,
        changeCount: payload.changeCount,
        additions: payload.additions,
        deletions: payload.deletions,
        paths: payload.paths,
        actions: payload.actions,
      }
    : null;
}

function toDiffSummaryActionEntries(value: unknown): DiffSummaryActionEntry[] {
  const payload = toPayloadSource<DiffSummaryActionsPayload>(value);
  return payload ? Object.entries(payload) : [];
}

function normalizeDiffSummaryActions(payload: unknown): Record<string, number> {
  return Object.fromEntries(
    toDiffSummaryActionEntries(payload)
      .map(([action, count]): EntryCount => [String(action || "unknown").trim() || "unknown", coerceNonNegativeInteger(count)])
      .filter(([action, count]) => action && count > 0),
  );
}

export function normalizeDiffSummary(payload: unknown): DiffSummaryView | null {
  const summary = toDiffSummaryPayload(payload);
  if (!summary) {
    return null;
  }
  const paths = toPayloadList(summary.paths)
    .map((path) => String(path || "").trim())
    .filter(Boolean);
  return {
    schemaVersion: coerceNonNegativeInteger(summary.schema_version ?? summary.schemaVersion),
    changedFiles: coerceNonNegativeInteger(summary.changed_files ?? summary.changedFiles ?? paths.length),
    changeCount: coerceNonNegativeInteger(summary.change_count ?? summary.changeCount),
    additions: coerceNonNegativeInteger(summary.additions),
    deletions: coerceNonNegativeInteger(summary.deletions),
    paths,
    actions: normalizeDiffSummaryActions(summary.actions),
  };
}

function countRunSummaryTools(value: unknown): number {
  return toPayloadList(value).reduce<number>((count, item) => {
    const tool = toPayloadSource<RunSummaryToolPayload>(item);
    return count + (String(tool?.name || "").trim() ? 1 : 0);
  }, 0);
}

function countRunSummaryFileChanges(value: unknown): number {
  return toPayloadList(value).reduce<number>((count, item) => {
    const change = toPayloadSource<RunSummaryFileChangePayload>(item);
    return count + (String(change?.path || "").trim() ? 1 : 0);
  }, 0);
}

function toRunSummaryPayload(value: unknown): RunSummaryPayload | null {
  const payload = toPayloadSource<RunSummaryPayload>(value);
  return payload
    ? {
        status: payload.status,
        duration_seconds: payload.duration_seconds,
        durationSeconds: payload.durationSeconds,
        tools: payload.tools,
        file_changes: payload.file_changes,
        fileChanges: payload.fileChanges,
      }
    : null;
}

export function normalizeRunSummary(payload: unknown): RunSummaryView | null {
  const summary = toRunSummaryPayload(payload);
  if (!summary) {
    return null;
  }

  return {
    status: String(summary.status || "completed").trim() || "completed",
    durationSeconds: Number.isFinite(Number(summary.duration_seconds ?? summary.durationSeconds))
      ? Number(summary.duration_seconds ?? summary.durationSeconds)
      : null,
    toolCount: countRunSummaryTools(summary.tools),
    fileChangeCount: countRunSummaryFileChanges(summary.file_changes || summary.fileChanges),
  };
}
