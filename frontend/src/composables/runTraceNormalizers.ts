import { randomToken } from "./chatClientTokens";
import {
  coerceBoolean,
  coerceNonNegativeInteger,
  normalizeEventTimestamp,
  previewText,
} from "./chatClientCoercion";
import { toPayloadSource } from "./payloadBoundary";

type SnapshotAvailability = { before: boolean; after: boolean };
type TraceEventCountsPayload = {
  returned?: unknown;
  total?: unknown;
  compacted?: unknown;
  text_total?: unknown;
  textTotal?: unknown;
  text_returned?: unknown;
  textReturned?: unknown;
  max_events?: unknown;
  maxEvents?: unknown;
  max_text_events?: unknown;
  maxTextEvents?: unknown;
};
export type TraceEventPayload = {
  action?: unknown;
  artifact?: unknown;
  command?: unknown;
  content?: unknown;
  created_at?: unknown;
  createdAt?: unknown;
  detail?: unknown;
  error?: unknown;
  exit_code?: unknown;
  exitCode?: unknown;
  kind?: unknown;
  message?: unknown;
  metadata?: unknown;
  ok?: unknown;
  path?: unknown;
  reason?: unknown;
  sandbox_path?: unknown;
  sandboxPath?: unknown;
  state?: unknown;
  status?: unknown;
  summary?: unknown;
  text?: unknown;
  tool_call_id?: unknown;
  toolCallId?: unknown;
  tool_name?: unknown;
  toolName?: unknown;
};
type TraceEventEnvelopePayload = {
  schema_version?: unknown;
  schemaVersion?: unknown;
  event_id?: unknown;
  eventId?: unknown;
  event_type?: unknown;
  eventType?: unknown;
  created_at?: unknown;
  createdAt?: unknown;
  payload?: unknown;
  artifact?: unknown;
  kind?: unknown;
  status?: unknown;
};
type RunArtifactFallbackPayload = {
  artifactType?: unknown;
  createdAt?: unknown;
  iteration?: unknown;
  kind?: unknown;
  phase?: unknown;
  source?: unknown;
  sourceId?: unknown;
  status?: unknown;
  toolCallId?: unknown;
};
type RunArtifactPayload = {
  artifact_id?: unknown;
  artifactId?: unknown;
  artifact_type?: unknown;
  artifactType?: unknown;
  kind?: unknown;
  status?: unknown;
  state?: unknown;
  phase?: unknown;
  title?: unknown;
  detail?: unknown;
  source?: unknown;
  source_id?: unknown;
  sourceId?: unknown;
  created_at?: unknown;
  createdAt?: unknown;
  tool_name?: unknown;
  toolName?: unknown;
  tool_call_id?: unknown;
  toolCallId?: unknown;
  iteration?: unknown;
  path?: unknown;
  action?: unknown;
  diff_len?: unknown;
  diffLen?: unknown;
  diff_preview?: unknown;
  diffPreview?: unknown;
  snapshots_available?: unknown;
  snapshotsAvailable?: unknown;
  metadata?: unknown;
};
export type BackgroundProcessEventPayload = {
  process_session_id?: unknown;
  processSessionId?: unknown;
  command?: unknown;
  cwd?: unknown;
  pid?: unknown;
  state?: unknown;
  status?: unknown;
  ok?: unknown;
  exit_code?: unknown;
  exitCode?: unknown;
  termination_reason?: unknown;
  terminationReason?: unknown;
  notify_mode?: unknown;
  notifyMode?: unknown;
  output_tail?: unknown;
  outputTail?: unknown;
  output_path?: unknown;
  outputPath?: unknown;
};

export const RUN_EVENT_KINDS = ["run", "llm", "tool", "verification", "work", "file", "process", "text", "system", "other"] as const;
export type RunEventKind = (typeof RUN_EVENT_KINDS)[number];

export type TraceEventCountsView = {
  total: number;
  returned: number;
  compacted: number;
  textTotal: number;
  textReturned: number;
  maxEvents: number;
  maxTextEvents: number;
};

export type TraceEventView = {
  id: string;
  schemaVersion: number;
  eventType: string;
  kind: RunEventKind;
  status: string;
  createdAt: number;
  payload: TraceEventPayload;
  artifact: RunArtifactView | null;
};

type MetadataTimestamp = string | number;

export type RunArtifactMetadataPayload = {
  finished_at?: unknown;
  finishedAt?: unknown;
};
export type RunArtifactMetadata = {
  [key: string]: unknown;
  finished_at?: MetadataTimestamp;
  finishedAt?: MetadataTimestamp;
};

export type RunArtifactView = {
  artifactId: string;
  artifactType: string;
  kind: RunEventKind;
  status: string;
  phase: string;
  title: string;
  detail: string;
  source: string;
  sourceId: string;
  createdAt: number;
  toolName: string;
  toolCallId: string;
  iteration: string;
  path: string;
  action: string;
  diffLen: number;
  diffPreview: string;
  snapshotsAvailable: SnapshotAvailability;
  metadata: RunArtifactMetadata;
};

export type TracePartMetadataPayload = {
  tool_call_id?: unknown;
  toolCallId?: unknown;
  finished_at?: unknown;
  finishedAt?: unknown;
  state?: unknown;
  streaming?: unknown;
};
export type TracePartMetadata = {
  [key: string]: unknown;
  tool_call_id?: string;
  toolCallId?: string;
  finished_at?: unknown;
  finishedAt?: unknown;
  state?: string;
  streaming?: boolean;
};
type TracePartPayload = {
  part_id?: unknown;
  partId?: unknown;
  part_type?: unknown;
  partType?: unknown;
  schema_version?: unknown;
  schemaVersion?: unknown;
  kind?: unknown;
  state?: unknown;
  status?: unknown;
  content?: unknown;
  tool_name?: unknown;
  toolName?: unknown;
  metadata?: unknown;
  artifact?: unknown;
  created_at?: unknown;
  createdAt?: unknown;
};

export type TracePartView = {
  partId: string;
  partType: string;
  schemaVersion: number;
  kind: RunEventKind;
  state: string;
  content: string;
  toolName: string;
  metadata: TracePartMetadata;
  artifact: RunArtifactView | null;
  createdAt: number;
};

export type TraceFileChangeView = {
  changeId: string;
  sourceId: string;
  schemaVersion: number;
  kind: RunEventKind;
  state: string;
  status: string;
  path: string;
  label: string;
  action: string;
  toolName: string;
  diffLen: number;
  diff: string;
  diffPreview: string;
  beforeContent: string | null;
  afterContent: string | null;
  snapshotsAvailable: SnapshotAvailability;
  artifact: RunArtifactView | null;
  revertSupported: boolean;
  createdAt: number;
};
type TraceFileChangePayload = {
  change_id?: unknown;
  changeId?: unknown;
  source_id?: unknown;
  sourceId?: unknown;
  schema_version?: unknown;
  schemaVersion?: unknown;
  kind?: unknown;
  state?: unknown;
  status?: unknown;
  path?: unknown;
  label?: unknown;
  action?: unknown;
  tool_name?: unknown;
  toolName?: unknown;
  diff_len?: unknown;
  diffLen?: unknown;
  diff?: unknown;
  diff_preview?: unknown;
  diffPreview?: unknown;
  before_content?: unknown;
  beforeContent?: unknown;
  after_content?: unknown;
  afterContent?: unknown;
  snapshots_available?: unknown;
  snapshotsAvailable?: unknown;
  artifact?: unknown;
  revert_supported?: unknown;
  revertSupported?: unknown;
  created_at?: unknown;
  createdAt?: unknown;
};

export type WorktreeSandboxMetadataPayload = {
  sandbox_path?: unknown;
  sandboxPath?: unknown;
  status?: unknown;
  reason?: unknown;
  cleanup_supported?: unknown;
  cleanupSupported?: unknown;
  repository_root?: unknown;
  repositoryRoot?: unknown;
  base_branch?: unknown;
  baseBranch?: unknown;
  base_commit?: unknown;
  baseCommit?: unknown;
};
type WorktreeSandboxPayload = WorktreeSandboxMetadataPayload & {
  metadata?: unknown;
  artifactType?: unknown;
  kind?: unknown;
};
export type WorktreeSandboxMetadata = {
  [key: string]: unknown;
  sandbox_path?: string;
  sandboxPath?: string;
  status?: string;
  reason?: string;
  cleanup_supported?: boolean;
  cleanupSupported?: boolean;
  repository_root?: string;
  repositoryRoot?: string;
  base_branch?: string;
  baseBranch?: string;
  base_commit?: string;
  baseCommit?: string;
};

export interface WorktreeSandboxView {
  sandboxPath: string;
  status: string;
  reason: string;
  cleanupSupported: boolean;
  repositoryRoot: string;
  baseBranch: string;
  baseCommit: string;
  cleanupPending: boolean;
  cleanupResult: unknown;
}

type TraceEventCountTarget = {
  eventCounts: TraceEventCountsView;
  rawEvents: TraceEventView[];
};

export function normalizeRunArtifactMetadata(value: unknown): RunArtifactMetadata {
  const payload = toRunArtifactMetadataPayload(value);
  if (!payload) {
    return {};
  }

  const metadata: RunArtifactMetadata = {};
  for (const [key, rawValue] of Object.entries(payload)) {
    if (key !== "finished_at" && key !== "finishedAt") {
      metadata[key] = rawValue;
    }
  }

  const finishedAt = normalizeMetadataTimestamp(payload.finished_at);
  const camelFinishedAt = normalizeMetadataTimestamp(payload.finishedAt);
  if (finishedAt !== null) {
    metadata.finished_at = finishedAt;
  }
  if (camelFinishedAt !== null) {
    metadata.finishedAt = camelFinishedAt;
  }
  return metadata;
}

function toRunArtifactMetadataPayload(value: unknown): RunArtifactMetadataPayload | null {
  return toPayloadSource<RunArtifactMetadataPayload>(value);
}

function normalizeMetadataTimestamp(value: unknown): MetadataTimestamp | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const timestamp = value.trim();
    return timestamp ? timestamp : null;
  }
  return null;
}

function toTracePartMetadataPayload(value: unknown): TracePartMetadataPayload | null {
  return toPayloadSource<TracePartMetadataPayload>(value);
}

export function normalizeTracePartMetadata(value: unknown): TracePartMetadata {
  const payload = toTracePartMetadataPayload(value);
  if (!payload) {
    return {};
  }

  const metadata: TracePartMetadata = {};
  for (const [key, rawValue] of Object.entries(payload)) {
    if (
      key !== "tool_call_id"
      && key !== "toolCallId"
      && key !== "state"
      && key !== "streaming"
    ) {
      metadata[key] = rawValue;
    }
  }

  const toolCallId = coerceText(payload.tool_call_id);
  const camelToolCallId = coerceText(payload.toolCallId);
  const state = coerceText(payload.state);
  if (toolCallId) {
    metadata.tool_call_id = toolCallId;
  }
  if (camelToolCallId) {
    metadata.toolCallId = camelToolCallId;
  }
  if (state) {
    metadata.state = state;
  }
  if (payload.streaming !== undefined && payload.streaming !== null && payload.streaming !== "") {
    metadata.streaming = coerceBoolean(payload.streaming);
  }
  return metadata;
}

function toWorktreeSandboxMetadataPayload(value: unknown): WorktreeSandboxMetadataPayload | null {
  return toPayloadSource<WorktreeSandboxMetadataPayload>(value);
}

function normalizeWorktreeSandboxMetadataPayload(payload: WorktreeSandboxMetadataPayload): WorktreeSandboxMetadata {
  const metadata: WorktreeSandboxMetadata = {};
  for (const [key, rawValue] of Object.entries(payload)) {
    if (
      key !== "sandbox_path"
      && key !== "sandboxPath"
      && key !== "status"
      && key !== "reason"
      && key !== "cleanup_supported"
      && key !== "cleanupSupported"
      && key !== "repository_root"
      && key !== "repositoryRoot"
      && key !== "base_branch"
      && key !== "baseBranch"
      && key !== "base_commit"
      && key !== "baseCommit"
    ) {
      metadata[key] = rawValue;
    }
  }

  const sandboxPath = coerceText(payload.sandbox_path);
  const camelSandboxPath = coerceText(payload.sandboxPath);
  const status = coerceText(payload.status);
  const reason = coerceText(payload.reason);
  const repositoryRoot = coerceText(payload.repository_root);
  const camelRepositoryRoot = coerceText(payload.repositoryRoot);
  const baseBranch = coerceText(payload.base_branch);
  const camelBaseBranch = coerceText(payload.baseBranch);
  const baseCommit = coerceText(payload.base_commit);
  const camelBaseCommit = coerceText(payload.baseCommit);

  if (sandboxPath) {
    metadata.sandbox_path = sandboxPath;
  }
  if (camelSandboxPath) {
    metadata.sandboxPath = camelSandboxPath;
  }
  if (status) {
    metadata.status = status;
  }
  if (reason) {
    metadata.reason = reason;
  }
  if (payload.cleanup_supported !== undefined && payload.cleanup_supported !== null && payload.cleanup_supported !== "") {
    metadata.cleanup_supported = coerceBoolean(payload.cleanup_supported);
  }
  if (payload.cleanupSupported !== undefined && payload.cleanupSupported !== null && payload.cleanupSupported !== "") {
    metadata.cleanupSupported = coerceBoolean(payload.cleanupSupported);
  }
  if (repositoryRoot) {
    metadata.repository_root = repositoryRoot;
  }
  if (camelRepositoryRoot) {
    metadata.repositoryRoot = camelRepositoryRoot;
  }
  if (baseBranch) {
    metadata.base_branch = baseBranch;
  }
  if (camelBaseBranch) {
    metadata.baseBranch = camelBaseBranch;
  }
  if (baseCommit) {
    metadata.base_commit = baseCommit;
  }
  if (camelBaseCommit) {
    metadata.baseCommit = camelBaseCommit;
  }
  return metadata;
}

export function normalizeWorktreeSandboxMetadata(
  value: unknown,
  fallback: WorktreeSandboxMetadataPayload | WorktreeSandboxMetadata = {},
): WorktreeSandboxMetadata {
  const payload = toWorktreeSandboxMetadataPayload(value);
  if (payload) {
    return normalizeWorktreeSandboxMetadataPayload(payload);
  }
  const fallbackPayload = toWorktreeSandboxMetadataPayload(fallback);
  return fallbackPayload ? normalizeWorktreeSandboxMetadataPayload(fallbackPayload) : {};
}

const MAX_RUN_EVENTS = 80;
const MAX_RUN_TEXT_EVENTS = 24;

const RUN_EVENT_KIND_SET: ReadonlySet<string> = new Set(RUN_EVENT_KINDS);

function isRunEventKind(value: string): value is RunEventKind {
  return RUN_EVENT_KIND_SET.has(value);
}

function coerceText(value: unknown): string {
  return String(value || "").trim();
}

function normalizeOptionalContent(value: unknown): string | null {
  return value === undefined || value === null ? null : String(value);
}

function normalizeArtifactIteration(value: unknown): string {
  return value === undefined || value === null ? "" : String(value);
}

export function coerceEventPayload(value: unknown): TraceEventPayload {
  return toPayloadSource<TraceEventPayload>(value) || {};
}

export function normalizeRunKind(value: unknown, fallback: RunEventKind = "other"): RunEventKind {
  const normalized = String(value || "").trim();
  return isRunEventKind(normalized) ? normalized : fallback;
}

export function inferRunEventKind(eventType: unknown): RunEventKind {
  const normalized = String(eventType || "").trim();
  if (normalized === "run_part_delta" || normalized === "message_part_delta") {
    return "text";
  }
  if (normalized.startsWith("run_")) {
    return "run";
  }
  if (normalized.startsWith("llm_") || normalized === "reasoning_delta" || normalized === "execution.stopped") {
    return "llm";
  }
  if (normalized.startsWith("tool_")) {
    return "tool";
  }
  if (normalized.startsWith("verification_")) {
    return "verification";
  }
  if (normalized === "file_changed") {
    return "file";
  }
  if (normalized.startsWith("background_process.")) {
    return "process";
  }
  return "other";
}

export function inferRunEventStatus(eventType: unknown, payload: TraceEventPayload = {}): string {
  const normalized = String(eventType || "").trim();
  const explicit = String(payload.status || payload.state || "").trim();
  if (explicit) {
    return explicit;
  }
  if (normalized === "run_part_delta" || normalized === "message_part_delta") {
    return "running";
  }
  if (normalized === "execution.stopped") {
    return "stopped";
  }
  if (normalized === "run_started" || normalized.endsWith("_started") || normalized === "llm_status") {
    return "running";
  }
  if (normalized === "run_failed") {
    return "failed";
  }
  if (normalized === "run_cancelled") {
    return "cancelled";
  }
  if (normalized === "run_cancel_requested") {
    return "cancelling";
  }
  if (normalized === "background_process.started") {
    return "running";
  }
  if (normalized === "background_process.lost") {
    return "lost";
  }
  if (normalized === "background_process.completed") {
    return Number(payload.exit_code ?? payload.exitCode ?? 0) === 0 ? "completed" : "failed";
  }
  if (payload.ok === false) {
    return inferRunEventKind(normalized) === "verification" ? "failed" : "error";
  }
  return "completed";
}

function isTextRunEvent(event: Pick<TraceEventView, "kind" | "eventType">): boolean {
  return event.kind === "text" || event.eventType === "run_part_delta" || event.eventType === "message_part_delta";
}

export function compactRunEvents(events: TraceEventView[]): TraceEventView[] {
  let textCount = 0;
  let otherCount = 0;
  const kept: TraceEventView[] = [];
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (isTextRunEvent(event)) {
      if (textCount >= MAX_RUN_TEXT_EVENTS) {
        continue;
      }
      textCount += 1;
    } else {
      if (otherCount >= MAX_RUN_EVENTS) {
        continue;
      }
      otherCount += 1;
    }
    kept.push(event);
  }
  return kept.reverse();
}

export function normalizeTraceEventCounts(counts: unknown, events: TraceEventView[] = []): TraceEventCountsView {
  const countsRecord = toPayloadSource<TraceEventCountsPayload>(counts) || {};
  const eventList = Array.isArray(events) ? events : [];
  const returned = coerceNonNegativeInteger(countsRecord.returned ?? eventList.length);
  const total = coerceNonNegativeInteger(countsRecord.total ?? returned);
  return {
    total,
    returned,
    compacted: coerceNonNegativeInteger(countsRecord.compacted ?? Math.max(0, total - returned)),
    textTotal: coerceNonNegativeInteger(countsRecord.text_total ?? countsRecord.textTotal),
    textReturned: coerceNonNegativeInteger(countsRecord.text_returned ?? countsRecord.textReturned),
    maxEvents: coerceNonNegativeInteger(countsRecord.max_events ?? countsRecord.maxEvents),
    maxTextEvents: coerceNonNegativeInteger(countsRecord.max_text_events ?? countsRecord.maxTextEvents),
  };
}

export function updateLiveTraceEventCounts(run: TraceEventCountTarget, event: TraceEventView): void {
  const previous = normalizeTraceEventCounts(run.eventCounts, run.rawEvents);
  const textTotal = previous.textTotal + (isTextRunEvent(event) ? 1 : 0);
  const textReturned = run.rawEvents.filter(isTextRunEvent).length;
  run.eventCounts = {
    total: previous.total + 1,
    returned: run.rawEvents.length,
    compacted: Math.max(0, previous.total + 1 - run.rawEvents.length),
    textTotal,
    textReturned,
    maxEvents: MAX_RUN_EVENTS,
    maxTextEvents: MAX_RUN_TEXT_EVENTS,
  };
}

export function normalizeRunArtifact(artifact: unknown, fallback: RunArtifactFallbackPayload = {}): RunArtifactView | null {
  const artifactRecord = toPayloadSource<RunArtifactPayload>(artifact);
  if (!artifactRecord) {
    return null;
  }
  const fallbackKind = normalizeRunKind(fallback.kind);
  const kind = normalizeRunKind(artifactRecord.kind, fallbackKind);
  const artifactType = String(artifactRecord.artifact_type || artifactRecord.artifactType || fallback.artifactType || "artifact").trim() || "artifact";
  const source = String(artifactRecord.source || fallback.source || "").trim();
  const sourceId = artifactRecord.source_id ?? artifactRecord.sourceId ?? fallback.sourceId ?? "";
  const createdAt = normalizeEventTimestamp(artifactRecord.created_at ?? artifactRecord.createdAt ?? fallback.createdAt);
  const toolCallId = String(artifactRecord.tool_call_id || artifactRecord.toolCallId || fallback.toolCallId || "").trim();
  const toolName = String(artifactRecord.tool_name || artifactRecord.toolName || "").trim();
  const iteration = normalizeArtifactIteration(artifactRecord.iteration ?? fallback.iteration);
  const inferredToolId = toolCallId
    ? `tool:${toolCallId}`
    : toolName && iteration !== ""
      ? `tool:${toolName}:${iteration}`
      : "";
  const artifactId = String(artifactRecord.artifact_id || artifactRecord.artifactId || inferredToolId || `${source || artifactType}:${sourceId || createdAt}`).trim();
  const snapshots = toPayloadSource<SnapshotAvailability>(artifactRecord.snapshots_available || artifactRecord.snapshotsAvailable) || {};
  return {
    artifactId,
    artifactType,
    kind,
    status: String(artifactRecord.status || artifactRecord.state || fallback.status || "completed").trim() || "completed",
    phase: String(artifactRecord.phase || fallback.phase || "").trim(),
    title: String(artifactRecord.title || artifactRecord.tool_name || artifactRecord.toolName || artifactRecord.path || artifactType).trim(),
    detail: String(artifactRecord.detail || artifactRecord.diff_preview || artifactRecord.diffPreview || "").trim(),
    source,
    sourceId: sourceId === null || sourceId === undefined ? "" : String(sourceId),
    createdAt,
    toolName,
    toolCallId,
    iteration,
    path: String(artifactRecord.path || "").trim(),
    action: String(artifactRecord.action || "").trim(),
    diffLen: coerceNonNegativeInteger(artifactRecord.diff_len ?? artifactRecord.diffLen),
    diffPreview: String(artifactRecord.diff_preview || artifactRecord.diffPreview || ""),
    snapshotsAvailable: {
      before: coerceBoolean(snapshots.before),
      after: coerceBoolean(snapshots.after),
    },
    metadata: normalizeRunArtifactMetadata(artifactRecord.metadata),
  };
}

function normalizeBackgroundProcessArtifact(
  eventType: unknown,
  payload: BackgroundProcessEventPayload,
  fallback: RunArtifactFallbackPayload = {},
): RunArtifactView | null {
  if (!String(eventType || "").startsWith("background_process.")) {
    return null;
  }
  const processSessionId = String(payload.process_session_id || payload.processSessionId || fallback.sourceId || "").trim();
  const command = String(payload.command || "").trim();
  if (!processSessionId && !command) {
    return null;
  }
  const normalizedEventType = String(eventType || "").trim();
  const state = normalizedEventType === "background_process.started"
    ? "running"
    : normalizedEventType === "background_process.lost"
      ? "lost"
      : normalizedEventType === "background_process.completed"
        ? (Number(payload.exit_code ?? payload.exitCode ?? 0) === 0 ? "completed" : "failed")
        : String(payload.state || fallback.status || inferRunEventStatus(eventType, payload)).trim() || "completed";
  const title = command ? previewText(command) : processSessionId;
  const exitCode = payload.exit_code ?? payload.exitCode;
  const termination = String(payload.termination_reason || payload.terminationReason || "").trim();
  const detailParts: string[] = [];
  if (processSessionId) {
    detailParts.push(processSessionId);
  }
  if (termination) {
    detailParts.push(termination);
  }
  if (exitCode !== null && exitCode !== undefined) {
    detailParts.push(`exit ${exitCode}`);
  }
  return {
    artifactId: `process:${processSessionId || fallback.sourceId || fallback.createdAt}`,
    artifactType: "background_process",
    kind: "process",
    status: state,
    phase: normalizedEventType.replace("background_process.", ""),
    title,
    detail: detailParts.join(" · "),
    source: "event",
    sourceId: processSessionId || String(fallback.sourceId || ""),
    createdAt: normalizeEventTimestamp(fallback.createdAt),
    toolName: "",
    toolCallId: "",
    iteration: "",
    path: "",
    action: "",
    diffLen: 0,
    diffPreview: "",
    snapshotsAvailable: { before: false, after: false },
    metadata: {
      process_session_id: processSessionId,
      command,
      cwd: String(payload.cwd || "").trim(),
      pid: payload.pid ?? null,
      state,
      termination_reason: termination,
      exit_code: exitCode ?? null,
      notify_mode: String(payload.notify_mode || payload.notifyMode || "").trim(),
      output_tail: String(payload.output_tail || payload.outputTail || "").trim(),
      output_path: String(payload.output_path || payload.outputPath || "").trim(),
    },
  };
}

export function normalizeTraceEventArtifact(
  eventType: unknown,
  payload: TraceEventPayload,
  artifact: unknown,
  fallback: RunArtifactFallbackPayload = {},
): RunArtifactView | null {
  return normalizeRunArtifact(artifact, fallback)
    || normalizeBackgroundProcessArtifact(eventType, payload, fallback);
}

function normalizeWorktreeSandbox(payload: unknown): WorktreeSandboxView | null {
  const payloadRecord = toPayloadSource<WorktreeSandboxPayload>(payload);
  if (!payloadRecord) {
    return null;
  }
  const metadata = normalizeWorktreeSandboxMetadata(payloadRecord.metadata, payloadRecord);
  const sandboxPath = metadata.sandbox_path || metadata.sandboxPath || "";
  if (!sandboxPath) {
    return null;
  }
  return {
    sandboxPath,
    status: metadata.status || coerceText(payloadRecord.status),
    reason: metadata.reason || "",
    cleanupSupported: metadata.cleanup_supported ?? metadata.cleanupSupported ?? false,
    repositoryRoot: metadata.repository_root || metadata.repositoryRoot || "",
    baseBranch: metadata.base_branch || metadata.baseBranch || "",
    baseCommit: metadata.base_commit || metadata.baseCommit || "",
    cleanupPending: false,
    cleanupResult: null,
  };
}

export function applyWorktreeCleanupEvent(
  sandbox: WorktreeSandboxView,
  event: TraceEventView,
): WorktreeSandboxView {
  if (event.eventType !== "worktree_cleanup.completed") {
    return sandbox;
  }
  const eventPath = coerceText(event.payload.sandbox_path ?? event.payload.sandboxPath);
  if (eventPath && eventPath !== sandbox.sandboxPath) {
    return sandbox;
  }
  const status = coerceText(event.payload.status);
  if (!coerceBoolean(event.payload.ok) && status !== "removed") {
    return sandbox;
  }
  return {
    ...sandbox,
    status: status || "removed",
    cleanupSupported: false,
    cleanupPending: false,
    cleanupResult: event.payload,
  };
}

export function preserveKnownRemovedWorktreeSandbox(
  previous: WorktreeSandboxView | null | undefined,
  incoming: WorktreeSandboxView | null,
): WorktreeSandboxView | null {
  if (!previous || previous.status.trim().toLowerCase() !== "removed") {
    return incoming;
  }
  if (!incoming) {
    return {
      ...previous,
      cleanupSupported: false,
      cleanupPending: false,
    };
  }
  if (incoming.sandboxPath !== previous.sandboxPath) {
    return incoming;
  }
  return {
    ...incoming,
    status: "removed",
    cleanupSupported: false,
    cleanupPending: false,
    cleanupResult: previous.cleanupResult ?? incoming.cleanupResult,
  };
}

function applyWorktreeCleanupEvents(
  sandbox: WorktreeSandboxView,
  events: TraceEventView[],
): WorktreeSandboxView {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const updated = applyWorktreeCleanupEvent(sandbox, events[index]);
    if (updated !== sandbox) {
      return updated;
    }
  }
  return sandbox;
}

export function findWorktreeSandbox(
  parts: unknown[] = [],
  artifacts: unknown[] = [],
  events: TraceEventView[] = [],
): WorktreeSandboxView | null {
  for (const part of parts) {
    const partRecord = toTracePartPayload(part);
    if (partRecord?.partType === "worktree_sandbox") {
      const sandbox = normalizeWorktreeSandbox(partRecord.metadata);
      if (sandbox) {
        return applyWorktreeCleanupEvents(sandbox, events);
      }
    }
  }
  for (const artifact of artifacts) {
    const artifactRecord = toPayloadSource<RunArtifactPayload>(artifact);
    if (artifactRecord?.artifactType === "worktree_sandbox" || artifactRecord?.kind === "work") {
      const sandbox = normalizeWorktreeSandbox(artifactRecord);
      if (sandbox) {
        return applyWorktreeCleanupEvents(sandbox, events);
      }
    }
  }
  return null;
}

function toTraceEventEnvelopePayload(value: unknown): TraceEventEnvelopePayload {
  const payload = toPayloadSource<TraceEventEnvelopePayload>(value);
  return payload
    ? {
        schema_version: payload.schema_version,
        schemaVersion: payload.schemaVersion,
        event_id: payload.event_id,
        eventId: payload.eventId,
        event_type: payload.event_type,
        eventType: payload.eventType,
        created_at: payload.created_at,
        createdAt: payload.createdAt,
        payload: payload.payload,
        artifact: payload.artifact,
        kind: payload.kind,
        status: payload.status,
      }
    : {};
}

export function normalizeTraceEvent(event: unknown): TraceEventView {
  const eventRecord = toTraceEventEnvelopePayload(event);
  const eventType = String(eventRecord.event_type || eventRecord.eventType || "run_event");
  const createdAt = normalizeEventTimestamp(eventRecord.created_at ?? eventRecord.createdAt);
  const eventPayload = coerceEventPayload(eventRecord.payload);
  const kind = normalizeRunKind(eventRecord.kind, inferRunEventKind(eventType));
  const status = String(eventRecord.status || inferRunEventStatus(eventType, eventPayload)).trim() || "completed";
  const eventId = String(eventRecord.event_id || eventRecord.eventId || `${eventType}-${createdAt}-${randomToken()}`);
  return {
    id: eventId,
    schemaVersion: coerceNonNegativeInteger(eventRecord.schema_version ?? eventRecord.schemaVersion),
    eventType,
    kind,
    status,
    createdAt,
    payload: eventPayload,
    artifact: normalizeTraceEventArtifact(eventType, eventPayload, eventRecord.artifact, {
      kind,
      status,
      source: "event",
      sourceId: eventId,
      createdAt,
    }),
  };
}

function toTracePartPayload(value: unknown): TracePartPayload | null {
  const payload = toPayloadSource<TracePartPayload>(value);
  return payload
    ? {
        part_id: payload.part_id,
        partId: payload.partId,
        part_type: payload.part_type,
        partType: payload.partType,
        schema_version: payload.schema_version,
        schemaVersion: payload.schemaVersion,
        kind: payload.kind,
        state: payload.state,
        status: payload.status,
        content: payload.content,
        tool_name: payload.tool_name,
        toolName: payload.toolName,
        metadata: payload.metadata,
        artifact: payload.artifact,
        created_at: payload.created_at,
        createdAt: payload.createdAt,
      }
    : null;
}

export function normalizeTracePart(part: unknown): TracePartView | null {
  const partRecord = toTracePartPayload(part);
  if (!partRecord) {
    return null;
  }
  const partId = String(partRecord.part_id || partRecord.partId || "").trim();
  const partType = String(partRecord.part_type || partRecord.partType || "part").trim() || "part";
  const createdAt = normalizeEventTimestamp(partRecord.created_at ?? partRecord.createdAt);
  const kind = normalizeRunKind(partRecord.kind, partType.startsWith("tool_") ? "tool" : "other");
  const state = String(partRecord.state || partRecord.status || "completed").trim() || "completed";
  return {
    partId,
    partType,
    schemaVersion: coerceNonNegativeInteger(partRecord.schema_version ?? partRecord.schemaVersion),
    kind,
    state,
    content: String(partRecord.content || ""),
    toolName: String(partRecord.tool_name || partRecord.toolName || "").trim(),
    metadata: normalizeTracePartMetadata(partRecord.metadata),
    artifact: normalizeRunArtifact(partRecord.artifact, {
      kind,
      status: state,
      source: "part",
      sourceId: partId,
      artifactType: partType,
      createdAt,
    }),
    createdAt,
  };
}

export function normalizeTraceFileChange(change: unknown): TraceFileChangeView | null {
  const changeRecord = toPayloadSource<TraceFileChangePayload>(change);
  if (!changeRecord) {
    return null;
  }
  const path = String(changeRecord.path || "").trim();
  if (!path) {
    return null;
  }
  const beforeContent = normalizeOptionalContent(changeRecord.before_content ?? changeRecord.beforeContent);
  const afterContent = normalizeOptionalContent(changeRecord.after_content ?? changeRecord.afterContent);
  const createdAt = normalizeEventTimestamp(changeRecord.created_at ?? changeRecord.createdAt);
  const snapshots = toPayloadSource<SnapshotAvailability>(changeRecord.snapshots_available || changeRecord.snapshotsAvailable) || {};
  const changeId = String(changeRecord.change_id || changeRecord.changeId || "").trim();
  const sourceId = String(changeRecord.source_id || changeRecord.sourceId || changeId).trim();
  const state = String(changeRecord.state || changeRecord.status || "completed").trim() || "completed";
  const label = String(changeRecord.label || path).trim() || path;
  return {
    changeId,
    sourceId,
    schemaVersion: coerceNonNegativeInteger(changeRecord.schema_version ?? changeRecord.schemaVersion),
    kind: normalizeRunKind(changeRecord.kind, "file"),
    state,
    status: state,
    path,
    label,
    action: String(changeRecord.action || "").trim(),
    toolName: String(changeRecord.tool_name || changeRecord.toolName || "").trim(),
    diffLen: coerceNonNegativeInteger(changeRecord.diff_len ?? changeRecord.diffLen),
    diff: String(changeRecord.diff || ""),
    diffPreview: String(changeRecord.diff_preview || changeRecord.diffPreview || ""),
    beforeContent,
    afterContent,
    snapshotsAvailable: {
      before: coerceBoolean(snapshots.before ?? beforeContent !== null),
      after: coerceBoolean(snapshots.after ?? afterContent !== null),
    },
    artifact: normalizeRunArtifact(changeRecord.artifact, {
      kind: "file",
      status: "completed",
      source: "file_change",
      sourceId,
      artifactType: "file_change",
      createdAt,
    }),
    revertSupported: coerceBoolean(changeRecord.revert_supported ?? changeRecord.revertSupported),
    createdAt,
  };
}
