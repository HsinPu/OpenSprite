import {
  normalizeTraceEventCounts,
  type RunArtifactView,
  type RunEventKind,
  type TraceEventView,
  type TraceFileChangeView,
  type TracePartView,
  type TraceEventCountsView,
  type WorktreeSandboxView,
} from "./runTraceNormalizers";
import type { DiffSummaryView, RunSummaryView } from "./runSummaryNormalizers";
import { coerceNonNegativeInteger } from "./chatClientCoercion";
import { toPayloadSource } from "./payloadBoundary";

const TERMINAL_RUN_STATUSES = ["completed", "failed", "cancelled"] as const;
type TerminalRunStatus = (typeof TERMINAL_RUN_STATUSES)[number];
const TERMINAL_RUN_STATUS_SET: ReadonlySet<string> = new Set<string>(TERMINAL_RUN_STATUSES);

const RUN_STATUS_EVENT_TYPES = ["run_started", "run_finished", "run_failed", "run_cancelled", "run_cancel_requested"] as const;
type RunStatusEventType = (typeof RUN_STATUS_EVENT_TYPES)[number];
const RUN_STATUS_EVENT_TYPE_SET: ReadonlySet<string> = new Set<string>(RUN_STATUS_EVENT_TYPES);

const RUN_SUMMARY_TRIGGER_EVENT_TYPES = ["run_finished", "run_failed"] as const;
type RunSummaryTriggerEventType = (typeof RUN_SUMMARY_TRIGGER_EVENT_TYPES)[number];
const RUN_SUMMARY_TRIGGER_EVENT_TYPE_SET: ReadonlySet<string> = new Set<string>(RUN_SUMMARY_TRIGGER_EVENT_TYPES);

function isRunStatusEventType(eventType: string): eventType is RunStatusEventType {
  return RUN_STATUS_EVENT_TYPE_SET.has(eventType);
}

function normalizeRunStatusEventType(eventType: string): RunStatusEventType | null {
  return isRunStatusEventType(eventType) ? eventType : null;
}

function fieldText(value: unknown): string {
  return String(value || "").trim();
}

function optionalNonNegativeInteger(value: unknown): number | null {
  if (value === undefined || value === null || value === "") {
    return null;
  }
  return coerceNonNegativeInteger(value);
}

export type RunLifecycleEventPayload = {
  status?: unknown;
  executed_tool_calls?: unknown;
  executedToolCalls?: unknown;
  context_compactions?: unknown;
  contextCompactions?: unknown;
  had_tool_error?: unknown;
  hadToolError?: unknown;
  prompt_type?: unknown;
  promptType?: unknown;
  task_id?: unknown;
  taskId?: unknown;
  summary?: unknown;
  message?: unknown;
  error?: unknown;
  total_tasks?: unknown;
  totalTasks?: unknown;
  task_preview?: unknown;
  taskPreview?: unknown;
  workflow?: unknown;
  label?: unknown;
  direct_workflow?: unknown;
  directWorkflow?: unknown;
  direct_start_step?: unknown;
  directStartStep?: unknown;
  direct_verify_action?: unknown;
  directVerifyAction?: unknown;
  direct_verify_path?: unknown;
  directVerifyPath?: unknown;
  reason?: unknown;
  completion_reason?: unknown;
  completionReason?: unknown;
};

type RunTimelineDetailPayload = {
  classification_reason?: unknown;
  tool_name?: unknown;
  toolName?: unknown;
  args_preview?: unknown;
  argsPreview?: unknown;
  action?: unknown;
  path?: unknown;
  ok?: unknown;
  result_preview?: unknown;
  resultPreview?: unknown;
  diff_preview?: unknown;
  diffPreview?: unknown;
  input_delta?: unknown;
  inputDelta?: unknown;
  content_delta?: unknown;
  contentDelta?: unknown;
  command?: unknown;
  process_session_id?: unknown;
  processSessionId?: unknown;
  exit_code?: unknown;
  exitCode?: unknown;
  planner_metadata?: unknown;
  plannerMetadata?: unknown;
  method?: unknown;
  continuation_type?: unknown;
  continuationType?: unknown;
  inherited_task_type?: unknown;
  inheritedTaskType?: unknown;
  is_follow_up?: unknown;
  isFollowUp?: unknown;
  should_inherit_active_task?: unknown;
  shouldInheritActiveTask?: unknown;
  should_replace_active_task?: unknown;
  shouldReplaceActiveTask?: unknown;
  should_seed_active_task?: unknown;
  shouldSeedActiveTask?: unknown;
  confidence?: unknown;
  resolved_objective?: unknown;
  resolvedObjective?: unknown;
  should_use_resolved_objective?: unknown;
  shouldUseResolvedObjective?: unknown;
  task_type?: unknown;
  taskType?: unknown;
  contract_sources?: unknown;
  contractSources?: unknown;
  required_tools?: unknown;
  requiredTools?: unknown;
  missing_evidence?: unknown;
  missingEvidence?: unknown;
  active_task_detail?: unknown;
  activeTaskDetail?: unknown;
};

export type RunTimelinePayload = RunLifecycleEventPayload & RunTimelineDetailPayload;

export function normalizeRunTimelinePayload(value: unknown): RunTimelinePayload {
  const payload = toPayloadSource<RunTimelinePayload>(value) || {};
  return {
    ...normalizeRunLifecycleEventPayload(payload),
    classification_reason: payload.classification_reason,
    tool_name: payload.tool_name,
    toolName: payload.toolName,
    args_preview: payload.args_preview,
    argsPreview: payload.argsPreview,
    action: payload.action,
    path: payload.path,
    ok: payload.ok,
    result_preview: payload.result_preview,
    resultPreview: payload.resultPreview,
    diff_preview: payload.diff_preview,
    diffPreview: payload.diffPreview,
    input_delta: payload.input_delta,
    inputDelta: payload.inputDelta,
    content_delta: payload.content_delta,
    contentDelta: payload.contentDelta,
    command: payload.command,
    process_session_id: payload.process_session_id,
    processSessionId: payload.processSessionId,
    exit_code: payload.exit_code,
    exitCode: payload.exitCode,
    planner_metadata: payload.planner_metadata,
    plannerMetadata: payload.plannerMetadata,
    method: payload.method,
    continuation_type: payload.continuation_type,
    continuationType: payload.continuationType,
    inherited_task_type: payload.inherited_task_type,
    inheritedTaskType: payload.inheritedTaskType,
    is_follow_up: payload.is_follow_up,
    isFollowUp: payload.isFollowUp,
    should_inherit_active_task: payload.should_inherit_active_task,
    shouldInheritActiveTask: payload.shouldInheritActiveTask,
    should_replace_active_task: payload.should_replace_active_task,
    shouldReplaceActiveTask: payload.shouldReplaceActiveTask,
    should_seed_active_task: payload.should_seed_active_task,
    shouldSeedActiveTask: payload.shouldSeedActiveTask,
    confidence: payload.confidence,
    resolved_objective: payload.resolved_objective,
    resolvedObjective: payload.resolvedObjective,
    should_use_resolved_objective: payload.should_use_resolved_objective,
    shouldUseResolvedObjective: payload.shouldUseResolvedObjective,
    task_type: payload.task_type,
    taskType: payload.taskType,
    contract_sources: payload.contract_sources,
    contractSources: payload.contractSources,
    required_tools: payload.required_tools,
    requiredTools: payload.requiredTools,
    missing_evidence: payload.missing_evidence,
    missingEvidence: payload.missingEvidence,
    active_task_detail: payload.active_task_detail,
    activeTaskDetail: payload.activeTaskDetail,
  };
}

export function normalizeRunLifecycleEventPayload(value: unknown): RunLifecycleEventPayload {
  const payload = toPayloadSource<RunLifecycleEventPayload>(value) || {};
  return {
    status: payload.status,
    executed_tool_calls: payload.executed_tool_calls,
    executedToolCalls: payload.executedToolCalls,
    context_compactions: payload.context_compactions,
    contextCompactions: payload.contextCompactions,
    had_tool_error: payload.had_tool_error,
    hadToolError: payload.hadToolError,
    prompt_type: payload.prompt_type,
    promptType: payload.promptType,
    task_id: payload.task_id,
    taskId: payload.taskId,
    summary: payload.summary,
    message: payload.message,
    error: payload.error,
    total_tasks: payload.total_tasks,
    totalTasks: payload.totalTasks,
    task_preview: payload.task_preview,
    taskPreview: payload.taskPreview,
    workflow: payload.workflow,
    label: payload.label,
    direct_workflow: payload.direct_workflow,
    directWorkflow: payload.directWorkflow,
    direct_start_step: payload.direct_start_step,
    directStartStep: payload.directStartStep,
    direct_verify_action: payload.direct_verify_action,
    directVerifyAction: payload.directVerifyAction,
    direct_verify_path: payload.direct_verify_path,
    directVerifyPath: payload.directVerifyPath,
    reason: payload.reason,
    completion_reason: payload.completion_reason,
    completionReason: payload.completionReason,
  };
}

export type RunEventCounts = TraceEventCountsView;
export type RunTimelineTone = "running" | "neutral" | "warning" | "success" | "error";
export type RunStatusEventPayloadView = {
  status: string;
};
export type RunFinishDetailView = {
  executedToolCalls: number | null;
  contextCompactions: number;
  hadToolError: boolean;
};
export type SubagentDetailView = {
  promptType: string;
  taskId: string;
  summary: string;
  message: string;
  error: string;
  totalTasks: number;
};
export type WorkflowDetailView = {
  summary: string;
  error: string;
  taskPreview: string;
  message: string;
  workflow: string;
  label: string;
};
export type AutoContinueDetailView = {
  workflow: string;
  startStep: string;
  verifyAction: string;
  verifyPath: string;
  reason: string;
};
export type RunTimelineEventView = {
  id: string;
  eventType: string;
  kind: RunEventKind;
  status: string;
  createdAt: number;
  payload: RunTimelinePayload;
  artifact: RunArtifactView | null;
  label: string;
  detail: string;
  tone: RunTimelineTone;
};

interface RunCopy {
  run: {
    statusLabels: Record<string, string>;
    toolCalls: (value: number) => string;
    compactions: (value: number) => string;
    toolWarning: string;
  };
}

interface RunViewStateInput {
  runId: string;
  sessionId: string;
  status?: string;
  createdAt: number;
  updatedAt?: number;
  finishedAt?: number | null;
}

export interface RunViewState {
  runId: string;
  sessionId: string;
  status: string;
  createdAt: number;
  updatedAt: number;
  finishedAt: number | null;
  events: RunTimelineEventView[];
  rawEvents: TraceEventView[];
  eventCounts: RunEventCounts;
  parts: TracePartView[];
  artifacts: RunArtifactView[];
  fileChanges: TraceFileChangeView[];
  diffSummary: DiffSummaryView | null;
  worktreeSandbox: WorktreeSandboxView | null;
  summary: RunSummaryView | null;
  summaryLoading: boolean;
  summaryError: string;
  summaryNotFoundAttempts: number;
  traceLoaded: boolean;
  traceLoading: boolean;
  traceError: string;
  cancelPending: boolean;
}

export function createRunViewState({
  runId,
  sessionId,
  status = "running",
  createdAt,
  updatedAt = createdAt,
  finishedAt = null,
}: RunViewStateInput): RunViewState {
  return {
    runId,
    sessionId,
    status,
    createdAt,
    updatedAt,
    finishedAt,
    events: [],
    rawEvents: [],
    eventCounts: normalizeTraceEventCounts(null, []),
    parts: [],
    artifacts: [],
    fileChanges: [],
    diffSummary: null,
    worktreeSandbox: null,
    summary: null,
    summaryLoading: false,
    summaryError: "",
    summaryNotFoundAttempts: 0,
    traceLoaded: false,
    traceLoading: false,
    traceError: "",
    cancelPending: false,
  };
}

export function shortRunId(runId: unknown): string {
  const normalized = String(runId || "run").replace(/^run[_-]?/, "");
  return normalized.length > 8 ? normalized.slice(0, 8) : normalized;
}

export function runStatusLabel(status: string, copy: RunCopy): string {
  return copy.run.statusLabels[status] || copy.run.statusLabels.running;
}

export function sessionStatusLabel(session: { status?: { status?: string } } | null | undefined, copy: RunCopy): string {
  const status = String(session?.status?.status || "idle").trim() || "idle";
  return copy.run.statusLabels[status] || status;
}

export function runTone(status: string, fallbackTone: RunTimelineTone = "running"): RunTimelineTone {
  const terminalStatus = isTerminalRunStatus(status) ? status : null;
  if (terminalStatus === "completed") {
    return fallbackTone === "warning" ? "warning" : "success";
  }
  if (terminalStatus === "failed") {
    return "error";
  }
  if (terminalStatus === "cancelled") {
    return "warning";
  }
  return fallbackTone;
}

export function isTerminalRunStatus(status: string): status is TerminalRunStatus {
  return TERMINAL_RUN_STATUS_SET.has(status);
}

export function isRunSummaryTriggerEventType(eventType: string): eventType is RunSummaryTriggerEventType {
  return RUN_SUMMARY_TRIGGER_EVENT_TYPE_SET.has(eventType);
}

export function normalizeRunStatusEventPayload(
  payload: RunLifecycleEventPayload,
  eventStatus = "",
): RunStatusEventPayloadView {
  return {
    status: String(payload.status || eventStatus),
  };
}

export function statusFromRunEvent(eventType: string, payload: RunLifecycleEventPayload, eventStatus = ""): string | null {
  const normalizedEventType = normalizeRunStatusEventType(eventType);
  if (!normalizedEventType) {
    return null;
  }
  const statusPayload = normalizeRunStatusEventPayload(payload, eventStatus);
  if (normalizedEventType === "run_started") {
    return "running";
  }
  if (normalizedEventType === "run_finished") {
    return statusPayload.status || "completed";
  }
  if (normalizedEventType === "run_failed") {
    return statusPayload.status || "failed";
  }
  if (normalizedEventType === "run_cancelled") {
    return statusPayload.status || "cancelled";
  }
  if (normalizedEventType === "run_cancel_requested") {
    return statusPayload.status || "cancelling";
  }
  return null;
}

export function normalizeRunFinishDetail(payload: RunLifecycleEventPayload): RunFinishDetailView {
  return {
    executedToolCalls: optionalNonNegativeInteger(payload.executed_tool_calls ?? payload.executedToolCalls),
    contextCompactions: coerceNonNegativeInteger(payload.context_compactions ?? payload.contextCompactions),
    hadToolError: Boolean(payload.had_tool_error ?? payload.hadToolError),
  };
}

export function formatRunFinishDetail(detail: RunFinishDetailView, copy: RunCopy): string {
  const parts: string[] = [];
  if (detail.executedToolCalls !== null) {
    parts.push(copy.run.toolCalls(detail.executedToolCalls));
  }
  if (detail.contextCompactions > 0) {
    parts.push(copy.run.compactions(detail.contextCompactions));
  }
  if (detail.hadToolError) {
    parts.push(copy.run.toolWarning);
  }
  return parts.join(" · ");
}

export function normalizeSubagentDetail(payload: RunLifecycleEventPayload): SubagentDetailView {
  return {
    promptType: fieldText(payload.prompt_type || payload.promptType),
    taskId: fieldText(payload.task_id || payload.taskId),
    summary: fieldText(payload.summary),
    message: fieldText(payload.message),
    error: fieldText(payload.error),
    totalTasks: coerceNonNegativeInteger(payload.total_tasks ?? payload.totalTasks),
  };
}

export function formatSubagentDetail(detail: SubagentDetailView): string {
  return [detail.promptType, detail.taskId].filter(Boolean).join(" · ");
}

export function formatSubagentGroupDetail(detail: SubagentDetailView): string {
  const summary = detail.summary || detail.message || detail.error;
  if (summary) {
    return summary;
  }
  return detail.totalTasks > 0 ? `${detail.totalTasks} task(s)` : "";
}

export function normalizeWorkflowDetail(payload: RunLifecycleEventPayload): WorkflowDetailView {
  return {
    summary: fieldText(payload.summary),
    error: fieldText(payload.error),
    taskPreview: fieldText(payload.task_preview || payload.taskPreview),
    message: fieldText(payload.message),
    workflow: fieldText(payload.workflow),
    label: fieldText(payload.label),
  };
}

export function formatWorkflowDetail(detail: WorkflowDetailView): string {
  return detail.summary || detail.error || detail.taskPreview || detail.message || detail.workflow;
}

export function formatWorkflowStepDetail(detail: WorkflowDetailView): string {
  return detail.summary || detail.error || detail.taskPreview || detail.label;
}

export function normalizeAutoContinueDetail(payload: RunLifecycleEventPayload): AutoContinueDetailView {
  return {
    workflow: fieldText(payload.direct_workflow || payload.directWorkflow),
    startStep: fieldText(payload.direct_start_step || payload.directStartStep),
    verifyAction: fieldText(payload.direct_verify_action || payload.directVerifyAction),
    verifyPath: fieldText(payload.direct_verify_path || payload.directVerifyPath),
    reason: fieldText(payload.reason || payload.completion_reason || payload.completionReason),
  };
}

export function formatAutoContinueDetail(detail: AutoContinueDetailView): string {
  if (detail.workflow && detail.startStep) {
    return `workflow resume: ${detail.workflow} -> ${detail.startStep}`;
  }
  if (detail.verifyAction) {
    return detail.verifyPath ? `verification: ${detail.verifyAction} (${detail.verifyPath})` : `verification: ${detail.verifyAction}`;
  }
  return detail.reason;
}
