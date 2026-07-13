import { randomToken } from "./chatClientTokens";
import {
  coerceBoolean,
  coerceNonNegativeInteger,
  coerceStringList,
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
type NamedItemPayload = { name?: unknown };
type ToolSelectionDecisionPayload = {
  selected_tools?: unknown;
  selectedTools?: unknown;
  missing_required_tools?: unknown;
  missingRequiredTools?: unknown;
};
type CompletionDecisionPayload = {
  status?: unknown;
  reason?: unknown;
};
type WorkProgressDecisionPayload = {
  next_action?: unknown;
  nextAction?: unknown;
};
type TaskTypeDecisionPayload = {
  task_type?: unknown;
  taskType?: unknown;
};
type TraceHealthDecisionPayload = { status?: unknown };
type DecisionEventPayload = {
  tool_selection?: unknown;
  toolSelection?: unknown;
  blocked_required_tools?: unknown;
  blockedRequiredTools?: unknown;
  required_tools?: unknown;
  requiredTools?: unknown;
  task_type?: unknown;
  taskType?: unknown;
  requirements?: unknown;
  acceptance_criteria?: unknown;
  acceptanceCriteria?: unknown;
  contract_sources?: unknown;
  contractSources?: unknown;
  missing_evidence?: unknown;
  missingEvidence?: unknown;
  next_action?: unknown;
  nextAction?: unknown;
  confidence?: unknown;
  auto_continue_attempts?: unknown;
  autoContinueAttempts?: unknown;
  attempt?: unknown;
  attempts?: unknown;
  completion?: unknown;
  work_progress?: unknown;
  workProgress?: unknown;
  task_artifact_count?: unknown;
  taskArtifactCount?: unknown;
  task?: unknown;
  contract?: unknown;
  trace_health?: unknown;
  traceHealth?: unknown;
  sensors?: unknown;
};
export type TraceEventPayload = DecisionEventPayload & {
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

export const RUN_EVENT_KINDS = ["run", "llm", "tool", "verification", "work", "completion", "file", "process", "text", "system", "other"] as const;
export type RunEventKind = (typeof RUN_EVENT_KINDS)[number];
export const DECISION_DETAIL_TONES = ["neutral", "info", "success", "warning", "error"] as const;
export type DecisionDetailTone = (typeof DECISION_DETAIL_TONES)[number];
export const DECISION_DETAIL_LABEL_KEYS = [
  "requiredTools",
  "selectedTools",
  "missingRequiredTools",
  "taskType",
  "requirements",
  "criteria",
  "sources",
  "status",
  "reason",
  "nextAction",
  "confidence",
  "missingEvidence",
  "attempts",
  "artifacts",
  "traceHealth",
  "sensors",
] as const;
export type DecisionDetailLabelKey = (typeof DECISION_DETAIL_LABEL_KEYS)[number];
export const DECISION_TIMELINE_PHASES = ["tools", "contract", "completion", "checkpoint"] as const;
export type DecisionTimelinePhase = (typeof DECISION_TIMELINE_PHASES)[number];
export const DECISION_TIMELINE_STATUSES = ["success", "failed", "blocked", "warning", "info"] as const;
export type DecisionTimelineStatus = (typeof DECISION_TIMELINE_STATUSES)[number];
export const DECISION_TIMELINE_TITLE_KEYS = ["toolSelection", "taskContract", "completionGate", "autoContinue", "checkpoint", "scorecard"] as const;
export type DecisionTimelineTitleKey = (typeof DECISION_TIMELINE_TITLE_KEYS)[number];

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

export type DecisionDetailView = {
  labelKey: DecisionDetailLabelKey;
  value: string;
  tone: DecisionDetailTone;
};

export type DecisionTimelineItem = {
  id: string;
  eventIds: string[];
  phase: DecisionTimelinePhase;
  status: DecisionTimelineStatus;
  titleKey: DecisionTimelineTitleKey;
  title: string;
  summary: string;
  reason: string;
  createdAt: number;
  details: DecisionDetailView[];
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

export type DelegatedTaskMetadata = {
  [key: string]: unknown;
};
type DelegatedTaskMetadataPayload = {
  [key: string]: unknown;
};

export interface DelegatedTaskView {
  taskId: string;
  promptType: string | null;
  status: string;
  selected: boolean;
  summary: string;
  error: string;
  childSessionId: string | null;
  lastChildRunId: string | null;
  metadata: DelegatedTaskMetadata;
  createdAt: number;
  updatedAt: number;
}
type DelegatedTaskPayload = {
  task_id?: unknown;
  taskId?: unknown;
  prompt_type?: unknown;
  promptType?: unknown;
  status?: unknown;
  selected?: unknown;
  summary?: unknown;
  error?: unknown;
  child_session_id?: unknown;
  childSessionId?: unknown;
  last_child_run_id?: unknown;
  lastChildRunId?: unknown;
  metadata?: unknown;
  created_at?: unknown;
  createdAt?: unknown;
  updated_at?: unknown;
  updatedAt?: unknown;
};

type WorkStatePayload = {
  session_id?: unknown;
  sessionId?: unknown;
  objective?: unknown;
  kind?: unknown;
  status?: unknown;
  steps?: unknown;
  constraints?: unknown;
  done_criteria?: unknown;
  doneCriteria?: unknown;
  long_running?: unknown;
  longRunning?: unknown;
  coding_task?: unknown;
  codingTask?: unknown;
  expects_code_change?: unknown;
  expectsCodeChange?: unknown;
  expects_verification?: unknown;
  expectsVerification?: unknown;
  current_step?: unknown;
  currentStep?: unknown;
  next_step?: unknown;
  nextStep?: unknown;
  completed_steps?: unknown;
  completedSteps?: unknown;
  pending_steps?: unknown;
  pendingSteps?: unknown;
  blockers?: unknown;
  verification_targets?: unknown;
  verificationTargets?: unknown;
  resume_hint?: unknown;
  resumeHint?: unknown;
  last_progress_signals?: unknown;
  lastProgressSignals?: unknown;
  file_change_count?: unknown;
  fileChangeCount?: unknown;
  touched_paths?: unknown;
  touchedPaths?: unknown;
  verification_attempted?: unknown;
  verificationAttempted?: unknown;
  verification_passed?: unknown;
  verificationPassed?: unknown;
  follow_up_workflow?: unknown;
  followUpWorkflow?: unknown;
  follow_up_step_id?: unknown;
  followUpStepId?: unknown;
  follow_up_step_label?: unknown;
  followUpStepLabel?: unknown;
  follow_up_prompt_type?: unknown;
  followUpPromptType?: unknown;
  verification_action?: unknown;
  verificationAction?: unknown;
  verification_path?: unknown;
  verificationPath?: unknown;
  verification_pytest_args?: unknown;
  verificationPytestArgs?: unknown;
  active_task_detail?: unknown;
  activeTaskDetail?: unknown;
  last_next_action?: unknown;
  lastNextAction?: unknown;
  delegated_tasks?: unknown;
  delegatedTasks?: unknown;
  active_delegate_task_id?: unknown;
  activeDelegateTaskId?: unknown;
  active_delegate_prompt_type?: unknown;
  activeDelegatePromptType?: unknown;
  updated_at?: unknown;
  updatedAt?: unknown;
};

export interface WorkStateView {
  sessionId: string | null;
  objective: string;
  kind: string;
  status: string;
  steps: string[];
  constraints: string[];
  doneCriteria: string[];
  longRunning: boolean;
  codingTask: boolean;
  expectsCodeChange: boolean;
  expectsVerification: boolean;
  currentStep: string;
  nextStep: string;
  completedSteps: string[];
  pendingSteps: string[];
  blockers: string[];
  verificationTargets: string[];
  resumeHint: string;
  lastProgressSignals: string[];
  fileChangeCount: number;
  touchedPaths: string[];
  verificationAttempted: boolean;
  verificationPassed: boolean;
  followUpWorkflow: string | null;
  followUpStepId: string | null;
  followUpStepLabel: string | null;
  followUpPromptType: string | null;
  verificationAction: string | null;
  verificationPath: string | null;
  verificationPytestArgs: string[];
  activeTaskDetail: string;
  lastNextAction: string;
  delegatedTasks: DelegatedTaskView[];
  activeDelegateTaskId: string | null;
  activeDelegatePromptType: string | null;
  updatedAt: number;
}

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

type DecisionEventContext = {
  id?: unknown;
  eventId?: unknown;
  event_id?: unknown;
  eventType: string;
  event_type?: unknown;
  createdAt: number;
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

export function normalizeDelegatedTaskMetadata(value: unknown): DelegatedTaskMetadata {
  return toPayloadSource<DelegatedTaskMetadataPayload>(value) || {};
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

function compactJoin(values: unknown[], separator = " · "): string {
  return values.map((value) => String(value || "").trim()).filter(Boolean).join(separator);
}

function countItems(value: unknown): number {
  return Array.isArray(value) ? value.length : 0;
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

function formatShortList(value: unknown, maxItems = 3): string {
  const items = coerceStringList(value);
  if (!items.length) {
    return "";
  }
  const visible = items.slice(0, maxItems).join(", ");
  const remaining = items.length - maxItems;
  return remaining > 0 ? `${visible} +${remaining}` : visible;
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
  if (normalized.startsWith("run_") || normalized.startsWith("auto_continue.")) {
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
  if (normalized.startsWith("task_contract.") || normalized.startsWith("task_checkpoint.") || normalized.startsWith("task_scorecard.")) {
    return "work";
  }
  if (normalized.startsWith("work_") || normalized.startsWith("task_")) {
    return "work";
  }
  if (normalized === "file_changed") {
    return "file";
  }
  if (normalized === "completion_gate.evaluated") {
    return "completion";
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
  if (normalized === "run_started" || normalized.endsWith("_started") || normalized === "llm_status" || normalized === "auto_continue.scheduled") {
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

function namedItems(value: unknown): unknown[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => {
    const record = toPayloadSource<NamedItemPayload>(item);
    return record ? record.name || item : item;
  });
}

function normalizeDecisionStatus(status: unknown): DecisionTimelineStatus {
  const normalized = coerceText(status).toLowerCase();
  if (["completed", "complete", "passed", "pass", "success", "ok", "ready"].includes(normalized)) {
    return "success";
  }
  if (["failed", "fail", "error"].includes(normalized)) {
    return "failed";
  }
  if (["blocked", "denied", "cancelled", "canceled"].includes(normalized)) {
    return "blocked";
  }
  if (["running", "scheduled", "incomplete", "waiting", "waiting_user", "cancelling"].includes(normalized)) {
    return "warning";
  }
  return "info";
}

function decisionDetail(labelKey: DecisionDetailLabelKey, value: unknown, tone: DecisionDetailTone = "neutral"): DecisionDetailView | null {
  const normalized = value === null || value === undefined ? "" : String(value).trim();
  if (!normalized) {
    return null;
  }
  return { labelKey, value: normalized, tone };
}

function compactDetails(items: Array<DecisionDetailView | null>): DecisionDetailView[] {
  return items.filter((item): item is DecisionDetailView => Boolean(item));
}

function decisionId(event: DecisionEventContext, index: number): string {
  return `decision:${event.id || event.eventId || event.event_id || event.eventType || event.event_type || "event"}:${index}`;
}

function decisionEventId(event: DecisionEventContext): string[] {
  const eventId = event?.id || event?.eventId || event?.event_id;
  return eventId ? [String(eventId)] : [];
}

function toolSelectionDecision(payload: TraceEventPayload, event: DecisionEventContext, index: number): DecisionTimelineItem {
  const toolSelection = toPayloadSource<ToolSelectionDecisionPayload>(payload.tool_selection || payload.toolSelection) || {};
  const selectedTools = toolSelection.selected_tools || toolSelection.selectedTools || [];
  const missingRequired = payload.blocked_required_tools || payload.blockedRequiredTools || toolSelection.missing_required_tools || toolSelection.missingRequiredTools || [];
  return {
    id: decisionId(event, index),
    eventIds: decisionEventId(event),
    phase: "tools",
    status: countItems(missingRequired) > 0 ? "warning" : "success",
    titleKey: "toolSelection",
    title: "Tool selection",
    summary: compactJoin([
      `${countItems(payload.required_tools || payload.requiredTools)} required`,
      `${countItems(selectedTools)} selected`,
      countItems(missingRequired) ? `${countItems(missingRequired)} missing` : "",
    ]),
    reason: "",
    createdAt: event.createdAt,
    details: compactDetails([
      decisionDetail("requiredTools", formatShortList(payload.required_tools || payload.requiredTools, 6)),
      decisionDetail("selectedTools", formatShortList(selectedTools, 6)),
      decisionDetail("missingRequiredTools", formatShortList(namedItems(missingRequired), 6), countItems(missingRequired) ? "warning" : "neutral"),
    ]),
  };
}

function taskContractDecision(payload: TraceEventPayload, event: DecisionEventContext, index: number): DecisionTimelineItem {
  return {
    id: decisionId(event, index),
    eventIds: decisionEventId(event),
    phase: "contract",
    status: "success",
    titleKey: "taskContract",
    title: "Task contract",
    summary: compactJoin([
      payload.task_type || payload.taskType,
      `${countItems(payload.requirements)} requirements`,
      `${countItems(payload.acceptance_criteria || payload.acceptanceCriteria)} criteria`,
    ]),
    reason: "",
    createdAt: event.createdAt,
    details: compactDetails([
      decisionDetail("taskType", payload.task_type || payload.taskType),
      decisionDetail("requirements", countItems(payload.requirements)),
      decisionDetail("criteria", countItems(payload.acceptance_criteria || payload.acceptanceCriteria)),
      decisionDetail("sources", formatShortList(payload.contract_sources || payload.contractSources, 5)),
    ]),
  };
}

function completionGateDecision(payload: TraceEventPayload, event: DecisionEventContext, index: number): DecisionTimelineItem {
  const missingEvidence = payload.missing_evidence || payload.missingEvidence;
  const nextAction = payload.next_action || payload.nextAction;
  return {
    id: decisionId(event, index),
    eventIds: decisionEventId(event),
    phase: "completion",
    status: normalizeDecisionStatus(payload.status || (payload.ok === false ? "failed" : "completed")),
    titleKey: "completionGate",
    title: "Completion gate",
    summary: compactJoin([payload.status, payload.reason, nextAction, countItems(missingEvidence) ? `${countItems(missingEvidence)} missing` : ""]),
    reason: coerceText(payload.reason),
    createdAt: event.createdAt,
    details: compactDetails([
      decisionDetail("status", payload.status),
      decisionDetail("reason", payload.reason),
      decisionDetail("nextAction", nextAction),
      decisionDetail("confidence", payload.confidence),
      decisionDetail("missingEvidence", formatShortList(missingEvidence, 4), countItems(missingEvidence) ? "warning" : "neutral"),
      decisionDetail("attempts", payload.auto_continue_attempts ?? payload.autoContinueAttempts),
    ]),
  };
}

function autoContinueDecision(eventType: string, payload: TraceEventPayload, event: DecisionEventContext, index: number): DecisionTimelineItem {
  const action = eventType.replace("auto_continue.", "");
  return {
    id: decisionId(event, index),
    eventIds: decisionEventId(event),
    phase: "completion",
    status: action === "scheduled" ? "warning" : action === "skipped" ? "blocked" : "success",
    titleKey: "autoContinue",
    title: "Auto-continue",
    summary: compactJoin([action, payload.reason]),
    reason: coerceText(payload.reason),
    createdAt: event.createdAt,
    details: compactDetails([
      decisionDetail("status", action),
      decisionDetail("reason", payload.reason),
      decisionDetail("attempts", payload.attempt ?? payload.attempts ?? payload.auto_continue_attempts ?? payload.autoContinueAttempts),
    ]),
  };
}

function checkpointDecision(payload: TraceEventPayload, event: DecisionEventContext, index: number): DecisionTimelineItem {
  const completion = toPayloadSource<CompletionDecisionPayload>(payload.completion) || {};
  const progress = toPayloadSource<WorkProgressDecisionPayload>(payload.work_progress || payload.workProgress) || {};
  return {
    id: decisionId(event, index),
    eventIds: decisionEventId(event),
    phase: "checkpoint",
    status: "success",
    titleKey: "checkpoint",
    title: "Checkpoint recorded",
    summary: compactJoin([payload.next_action || payload.nextAction || progress.next_action || progress.nextAction, completion.status]),
    reason: coerceText(completion.reason),
    createdAt: event.createdAt,
    details: compactDetails([
      decisionDetail("nextAction", payload.next_action || payload.nextAction || progress.next_action || progress.nextAction),
      decisionDetail("status", completion.status),
      decisionDetail("reason", completion.reason),
      decisionDetail("artifacts", payload.task_artifact_count ?? payload.taskArtifactCount),
      decisionDetail("attempts", payload.auto_continue_attempts ?? payload.autoContinueAttempts),
    ]),
  };
}

function scorecardDecision(payload: TraceEventPayload, event: DecisionEventContext, index: number): DecisionTimelineItem {
  const task = toPayloadSource<TaskTypeDecisionPayload>(payload.task) || {};
  const contract = toPayloadSource<TaskTypeDecisionPayload>(payload.contract) || {};
  const completion = toPayloadSource<CompletionDecisionPayload>(payload.completion) || {};
  const traceHealth = toPayloadSource<TraceHealthDecisionPayload>(payload.trace_health || payload.traceHealth) || {};
  const sensors = Array.isArray(payload.sensors) ? payload.sensors : [];
  return {
    id: decisionId(event, index),
    eventIds: decisionEventId(event),
    phase: "checkpoint",
    status: traceHealth.status === "fail" ? "failed" : traceHealth.status === "warn" ? "warning" : "success",
    titleKey: "scorecard",
    title: "Task scorecard",
    summary: compactJoin([task.task_type || task.taskType || contract.task_type || contract.taskType, completion.status, traceHealth.status]),
    reason: coerceText(completion.reason),
    createdAt: event.createdAt,
    details: compactDetails([
      decisionDetail("taskType", task.task_type || task.taskType || contract.task_type || contract.taskType),
      decisionDetail("status", completion.status),
      decisionDetail("reason", completion.reason),
      decisionDetail("traceHealth", traceHealth.status),
      decisionDetail("sensors", sensors.length),
    ]),
  };
}

export function deriveDecisionTimelineItems(events: unknown = []): DecisionTimelineItem[] {
  if (!Array.isArray(events)) {
    return [];
  }
  const items: DecisionTimelineItem[] = [];
  for (const event of events) {
    const eventRecord = toTraceEventEnvelopePayload(event);
    const eventType = coerceText(eventRecord.eventType || eventRecord.event_type);
    const payload = coerceEventPayload(eventRecord.payload);
    const eventWithTimestamp: DecisionEventContext = {
      ...eventRecord,
      eventType,
      createdAt: normalizeEventTimestamp(eventRecord.createdAt ?? eventRecord.created_at),
    };
    let item: DecisionTimelineItem | null = null;
    if (eventType === "tool_selection.resolved") {
      item = toolSelectionDecision(payload, eventWithTimestamp, items.length);
    } else if (eventType === "task_contract.created" || eventType === "task_contract.planning_started" || eventType === "task_contract.planned" || eventType === "task_contract.validated" || eventType === "task_contract.validation_failed") {
      item = taskContractDecision(payload, eventWithTimestamp, items.length);
    } else if (eventType === "completion_gate.evaluated") {
      item = completionGateDecision(payload, eventWithTimestamp, items.length);
    } else if (eventType.startsWith("auto_continue.")) {
      item = autoContinueDecision(eventType, payload, eventWithTimestamp, items.length);
    } else if (eventType === "task_checkpoint.recorded") {
      item = checkpointDecision(payload, eventWithTimestamp, items.length);
    } else if (eventType === "task_scorecard.recorded") {
      item = scorecardDecision(payload, eventWithTimestamp, items.length);
    }
    if (item) {
      items.push(item);
    }
  }
  return items;
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

export function findWorktreeSandbox(parts: unknown[] = [], artifacts: unknown[] = []): WorktreeSandboxView | null {
  for (const part of parts) {
    const partRecord = toTracePartPayload(part);
    if (partRecord?.partType === "worktree_sandbox") {
      return normalizeWorktreeSandbox(partRecord.metadata);
    }
  }
  for (const artifact of artifacts) {
    const artifactRecord = toPayloadSource<RunArtifactPayload>(artifact);
    if (artifactRecord?.artifactType === "worktree_sandbox" || artifactRecord?.kind === "work") {
      return normalizeWorktreeSandbox(artifactRecord);
    }
  }
  return null;
}

function normalizeDelegatedTask(payload: unknown): DelegatedTaskView | null {
  const record = toPayloadSource<DelegatedTaskPayload>(payload);
  if (!record) {
    return null;
  }
  const taskId = String(record.task_id || record.taskId || "").trim();
  if (!taskId) {
    return null;
  }
  return {
    taskId,
    promptType: String(record.prompt_type || record.promptType || "").trim() || null,
    status: String(record.status || "unknown").trim() || "unknown",
    selected: coerceBoolean(record.selected),
    summary: String(record.summary || "").trim(),
    error: String(record.error || "").trim(),
    childSessionId: String(record.child_session_id || record.childSessionId || "").trim() || null,
    lastChildRunId: String(record.last_child_run_id || record.lastChildRunId || "").trim() || null,
    metadata: normalizeDelegatedTaskMetadata(record.metadata),
    createdAt: normalizeEventTimestamp(record.created_at ?? record.createdAt),
    updatedAt: normalizeEventTimestamp(record.updated_at ?? record.updatedAt),
  };
}

export function normalizeWorkState(payload: unknown): WorkStateView | null {
  const record = toPayloadSource<WorkStatePayload>(payload);
  if (!record) {
    return null;
  }
  const objective = String(record.objective || "").trim();
  if (!objective) {
    return null;
  }
  const rawDelegatedTasks = record.delegated_tasks || record.delegatedTasks;
  const delegatedTasks = Array.isArray(rawDelegatedTasks)
    ? rawDelegatedTasks.map(normalizeDelegatedTask).filter((task): task is DelegatedTaskView => Boolean(task))
    : [];
  const selectedDelegatedTask = delegatedTasks.find((task) => task.selected) || null;
  return {
    sessionId: String(record.session_id || record.sessionId || "").trim() || null,
    objective,
    kind: String(record.kind || "task").trim() || "task",
    status: String(record.status || "active").trim() || "active",
    steps: coerceStringList(record.steps),
    constraints: coerceStringList(record.constraints),
    doneCriteria: coerceStringList(record.done_criteria || record.doneCriteria),
    longRunning: coerceBoolean(record.long_running ?? record.longRunning),
    codingTask: coerceBoolean(record.coding_task ?? record.codingTask),
    expectsCodeChange: coerceBoolean(record.expects_code_change ?? record.expectsCodeChange),
    expectsVerification: coerceBoolean(record.expects_verification ?? record.expectsVerification),
    currentStep: String(record.current_step || record.currentStep || "not set").trim() || "not set",
    nextStep: String(record.next_step || record.nextStep || "not set").trim() || "not set",
    completedSteps: coerceStringList(record.completed_steps || record.completedSteps),
    pendingSteps: coerceStringList(record.pending_steps || record.pendingSteps),
    blockers: coerceStringList(record.blockers),
    verificationTargets: coerceStringList(record.verification_targets || record.verificationTargets),
    resumeHint: String(record.resume_hint || record.resumeHint || "").trim(),
    lastProgressSignals: coerceStringList(record.last_progress_signals || record.lastProgressSignals),
    fileChangeCount: coerceNonNegativeInteger(record.file_change_count ?? record.fileChangeCount),
    touchedPaths: coerceStringList(record.touched_paths || record.touchedPaths),
    verificationAttempted: coerceBoolean(record.verification_attempted ?? record.verificationAttempted),
    verificationPassed: coerceBoolean(record.verification_passed ?? record.verificationPassed),
    followUpWorkflow: String(record.follow_up_workflow || record.followUpWorkflow || "").trim() || null,
    followUpStepId: String(record.follow_up_step_id || record.followUpStepId || "").trim() || null,
    followUpStepLabel: String(record.follow_up_step_label || record.followUpStepLabel || "").trim() || null,
    followUpPromptType: String(record.follow_up_prompt_type || record.followUpPromptType || "").trim() || null,
    verificationAction: String(record.verification_action || record.verificationAction || "").trim() || null,
    verificationPath: String(record.verification_path || record.verificationPath || "").trim() || null,
    verificationPytestArgs: coerceStringList(record.verification_pytest_args || record.verificationPytestArgs),
    activeTaskDetail: String(record.active_task_detail || record.activeTaskDetail || "").trim(),
    lastNextAction: String(record.last_next_action || record.lastNextAction || "").trim(),
    delegatedTasks,
    activeDelegateTaskId: String(record.active_delegate_task_id || record.activeDelegateTaskId || "").trim() || selectedDelegatedTask?.taskId || null,
    activeDelegatePromptType: String(record.active_delegate_prompt_type || record.activeDelegatePromptType || "").trim() || selectedDelegatedTask?.promptType || null,
    updatedAt: normalizeEventTimestamp(record.updated_at ?? record.updatedAt),
  };
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
