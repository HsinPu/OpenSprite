import { normalizeTraceEventCounts } from "./runTraceNormalizers";
import { channelFromSessionId, externalChatIdFromSessionId } from "./chatClientSessionIds";

function coerceNonNegativeInteger(value) {
  const number = Number(value);
  if (!Number.isFinite(number) || number < 0) {
    return 0;
  }
  return Math.trunc(number);
}

function normalizeEventTimestamp(value) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue) || numericValue <= 0) {
    return Date.now();
  }
  return numericValue > 1_000_000_000_000 ? numericValue : numericValue * 1000;
}

export function createRunViewState({ runId, sessionId, status = "running", createdAt, updatedAt = createdAt, finishedAt = null }) {
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
  };
}

export function normalizeBackgroundProcess(payload) {
  const processSessionId = String(payload?.process_session_id || payload?.processSessionId || "").trim();
  if (!processSessionId) {
    return null;
  }
  const ownerSessionId = String(payload?.owner_session_id || payload?.ownerSessionId || "").trim();
  const ownerChannel = String(payload?.owner_channel || payload?.ownerChannel || channelFromSessionId(ownerSessionId) || "").trim();
  const ownerExternalChatId = String(payload?.owner_external_chat_id || payload?.ownerExternalChatId || "").trim()
    || externalChatIdFromSessionId(ownerSessionId);
  const finishedAt = payload?.finished_at ?? payload?.finishedAt;
  const exitCode = payload?.exit_code ?? payload?.exitCode;
  return {
    processSessionId,
    ownerSessionId,
    ownerRunId: String(payload?.owner_run_id || payload?.ownerRunId || "").trim(),
    ownerChannel,
    ownerExternalChatId,
    pid: payload?.pid ?? null,
    command: String(payload?.command || "").trim(),
    cwd: String(payload?.cwd || "").trim(),
    state: String(payload?.state || "unknown").trim() || "unknown",
    terminationReason: String(payload?.termination_reason || payload?.terminationReason || "").trim(),
    exitCode: Number.isFinite(Number(exitCode)) ? Number(exitCode) : null,
    notifyMode: String(payload?.notify_mode || payload?.notifyMode || "").trim(),
    outputTail: String(payload?.output_tail || payload?.outputTail || "").trim(),
    outputPath: String(payload?.output_path || payload?.outputPath || "").trim(),
    metadata: payload?.metadata && typeof payload.metadata === "object" ? payload.metadata : {},
    startedAt: normalizeEventTimestamp(payload?.started_at ?? payload?.startedAt),
    updatedAt: normalizeEventTimestamp(payload?.updated_at ?? payload?.updatedAt),
    finishedAt: finishedAt ? normalizeEventTimestamp(finishedAt) : null,
  };
}

export function statusFromRunEvent(eventType, payload, eventStatus = "") {
  if (eventType === "run_started") {
    return "running";
  }
  if (eventType === "run_finished") {
    return payload.status || eventStatus || "completed";
  }
  if (eventType === "run_failed") {
    return payload.status || eventStatus || "failed";
  }
  if (eventType === "run_cancelled") {
    return payload.status || eventStatus || "cancelled";
  }
  if (eventType === "run_cancel_requested") {
    return payload.status || eventStatus || "cancelling";
  }
  return null;
}

export function formatRunFinishDetail(payload, copy) {
  const parts = [];
  if (Number.isFinite(Number(payload.executed_tool_calls))) {
    parts.push(copy.run.toolCalls(payload.executed_tool_calls));
  }
  if (Number.isFinite(Number(payload.context_compactions)) && Number(payload.context_compactions) > 0) {
    parts.push(copy.run.compactions(payload.context_compactions));
  }
  if (payload.had_tool_error) {
    parts.push(copy.run.toolWarning);
  }
  return parts.join(" · ");
}

export function formatSubagentDetail(payload) {
  return [payload.prompt_type || payload.promptType, payload.task_id || payload.taskId].filter(Boolean).join(" · ");
}

export function formatSubagentGroupDetail(payload) {
  const summary = String(payload.summary || payload.message || payload.error || "").trim();
  if (summary) {
    return summary;
  }
  const total = coerceNonNegativeInteger(payload.total_tasks ?? payload.totalTasks);
  return total > 0 ? `${total} task(s)` : "";
}

export function formatWorkflowDetail(payload) {
  return String(payload.summary || payload.error || payload.task_preview || payload.message || payload.workflow || "").trim();
}

export function formatWorkflowStepDetail(payload) {
  return String(payload.summary || payload.error || payload.task_preview || payload.label || "").trim();
}

export function formatAutoContinueDetail(payload) {
  const workflow = String(payload.direct_workflow || payload.directWorkflow || "").trim();
  const startStep = String(payload.direct_start_step || payload.directStartStep || "").trim();
  const verifyAction = String(payload.direct_verify_action || payload.directVerifyAction || "").trim();
  const verifyPath = String(payload.direct_verify_path || payload.directVerifyPath || "").trim();
  if (workflow && startStep) {
    return `workflow resume: ${workflow} -> ${startStep}`;
  }
  if (verifyAction) {
    return verifyPath ? `verification: ${verifyAction} (${verifyPath})` : `verification: ${verifyAction}`;
  }
  return String(payload.reason || payload.completion_reason || payload.completionReason || "").trim();
}
