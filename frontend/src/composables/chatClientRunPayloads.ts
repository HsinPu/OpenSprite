import { coerceBoolean, coerceText as textField } from "./chatClientCoercion";
import { toPayloadSource } from "./payloadBoundary";
import { normalizeDiffSummary, type DiffSummaryView } from "./runSummaryNormalizers";
import {
  compactRunEvents,
  normalizeRunArtifact,
  normalizeTraceEvent,
  normalizeTraceEventCounts,
  normalizeTraceFileChange,
  normalizeTracePart,
  type RunArtifactView,
  type TraceEventCountsView,
  type TraceEventView,
  type TraceFileChangeView,
  type TracePartView,
} from "./runTraceNormalizers";

export type RunsPayload = {
  runs?: unknown;
};

type RunTraceSourcePayload = {
  events?: unknown;
  file_changes?: unknown;
  fileChanges?: unknown;
  parts?: unknown;
  artifacts?: unknown;
  event_counts?: unknown;
  eventCounts?: unknown;
  diff_summary?: unknown;
  diffSummary?: unknown;
};

export type RunTracePayload = {
  rawEvents: TraceEventView[];
  fileChanges: TraceFileChangeView[];
  parts: TracePartView[];
  artifacts: RunArtifactView[];
  eventCounts: TraceEventCountsView;
  diffSummary: DiffSummaryView | null;
};

type RunFileChangeRevertSourcePayload = {
  applied?: unknown;
  reason?: unknown;
  revert?: unknown;
};

type RunFileChangeRevertRecordSourcePayload = {
  applied?: unknown;
  reason?: unknown;
};

export type RunFileChangeRevertRecord = {
  applied: boolean;
  reason: string;
};

export type RunFileChangeRevertPayload = {
  revert: RunFileChangeRevertRecord | null;
  applied: boolean;
  reason: string;
};

export function toRunsPayload(value: unknown): RunsPayload | null {
  const payload = toPayloadSource<RunsPayload>(value);
  if (!payload) {
    return null;
  }
  return {
    runs: payload.runs,
  };
}

function normalizeRunTraceEvents(value: unknown): TraceEventView[] {
  const events = Array.isArray(value) ? value : [];
  return compactRunEvents(events.map(normalizeTraceEvent));
}

function normalizeRunTraceFileChanges(value: unknown): TraceFileChangeView[] {
  const fileChanges = Array.isArray(value) ? value : [];
  return fileChanges.reduce<TraceFileChangeView[]>((normalized, change) => {
    const fileChange = normalizeTraceFileChange(change);
    if (fileChange) {
      normalized.push(fileChange);
    }
    return normalized;
  }, []);
}

function normalizeRunTraceParts(value: unknown): TracePartView[] {
  const parts = Array.isArray(value) ? value : [];
  return parts.reduce<TracePartView[]>((normalized, part) => {
    const tracePart = normalizeTracePart(part);
    if (tracePart) {
      normalized.push(tracePart);
    }
    return normalized;
  }, []);
}

function normalizeRunTraceArtifacts(value: unknown): RunArtifactView[] {
  const artifacts = Array.isArray(value) ? value : [];
  return artifacts.reduce<RunArtifactView[]>((normalized, artifact) => {
    const runArtifact = normalizeRunArtifact(artifact);
    if (runArtifact) {
      normalized.push(runArtifact);
    }
    return normalized;
  }, []);
}

export function toRunTracePayload(value: unknown): RunTracePayload | null {
  const payload = toPayloadSource<RunTraceSourcePayload>(value);
  if (!payload) {
    return null;
  }
  const rawEvents = normalizeRunTraceEvents(payload.events);
  return {
    rawEvents,
    fileChanges: normalizeRunTraceFileChanges(payload.file_changes || payload.fileChanges),
    parts: normalizeRunTraceParts(payload.parts),
    artifacts: normalizeRunTraceArtifacts(payload.artifacts),
    eventCounts: normalizeTraceEventCounts(payload.event_counts || payload.eventCounts, rawEvents),
    diffSummary: normalizeDiffSummary(payload.diff_summary || payload.diffSummary),
  };
}

function normalizeRunFileChangeRevertRecord(
  value: unknown,
  fallback: RunFileChangeRevertRecordSourcePayload,
): RunFileChangeRevertRecord {
  const source = toPayloadSource<RunFileChangeRevertRecordSourcePayload>(value) || fallback;
  return {
    applied: coerceBoolean(source.applied),
    reason: textField(source.reason),
  };
}

export function toRunFileChangeRevertPayload(value: unknown): RunFileChangeRevertPayload | null {
  const payload = toPayloadSource<RunFileChangeRevertSourcePayload>(value);
  if (!payload) {
    return null;
  }
  const revert = normalizeRunFileChangeRevertRecord(payload.revert, payload);
  return {
    revert,
    applied: revert.applied,
    reason: revert.reason || textField(payload.reason),
  };
}
