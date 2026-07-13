import { toPayloadSource } from "./payloadBoundary";
import {
  normalizeRunTimelinePayload,
  type RunTimelinePayload,
} from "./chatClientRunHelpers";

export type TaskEventPlannerMetadata = {
  reason?: unknown;
  planner_status?: unknown;
  plannerStatus?: unknown;
  required_tools?: unknown;
  requiredTools?: unknown;
};

export type TaskEventPayload = {
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
  reason?: unknown;
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
  status?: unknown;
};

export type RunEventPayloadInput = {
  classification_reason?: unknown;
  reason?: unknown;
  message?: unknown;
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
  had_tool_error?: unknown;
  hadToolError?: unknown;
  status?: unknown;
  error?: unknown;
};

export type RunPartDeltaPayload = {
  part_id?: unknown;
  partId?: unknown;
  part_type?: unknown;
  partType?: unknown;
  content_delta?: unknown;
  delta?: unknown;
  text?: unknown;
  content?: unknown;
  state?: unknown;
  status?: unknown;
  kind?: unknown;
  tool_name?: unknown;
  toolName?: unknown;
  metadata?: unknown;
};

export type CompletionGateWorkStatePayload = {
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
};

export type WorkPlanStatePayload = {
  objective?: unknown;
  kind?: unknown;
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
};

export type WorkProgressStatePayload = {
  work_progress?: unknown;
  status?: unknown;
  file_change_count?: unknown;
  fileChangeCount?: unknown;
  touched_paths?: unknown;
  touchedPaths?: unknown;
  verification_attempted?: unknown;
  verificationAttempted?: unknown;
  verification_passed?: unknown;
  verificationPassed?: unknown;
  next_action?: unknown;
  nextAction?: unknown;
  progress_signals?: unknown;
  progressSignals?: unknown;
};

export type WorkProgressEnvelopePayload = Pick<WorkProgressStatePayload, "work_progress">;

export type LiveRunEventPayloadSource =
  RunTimelinePayload
  & RunPartDeltaPayload
  & WorkPlanStatePayload
  & WorkProgressStatePayload
  & CompletionGateWorkStatePayload;

export function toTaskEventPlannerMetadata(value: unknown): TaskEventPlannerMetadata {
  const payload = toPayloadSource<TaskEventPlannerMetadata>(value);
  if (!payload) {
    return {};
  }
  return {
    reason: payload.reason,
    planner_status: payload.planner_status,
    plannerStatus: payload.plannerStatus,
    required_tools: payload.required_tools,
    requiredTools: payload.requiredTools,
  };
}

export function toTaskEventPayload(value: unknown): TaskEventPayload {
  const payload = toPayloadSource<TaskEventPayload>(value);
  if (!payload) {
    return {};
  }
  return {
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
    reason: payload.reason,
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
    status: payload.status,
  };
}

export function toRunEventPayloadInput(value: unknown): RunEventPayloadInput {
  const payload = toPayloadSource<RunEventPayloadInput>(value);
  if (!payload) {
    return {};
  }
  return {
    classification_reason: payload.classification_reason,
    reason: payload.reason,
    message: payload.message,
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
    had_tool_error: payload.had_tool_error,
    hadToolError: payload.hadToolError,
    status: payload.status,
    error: payload.error,
  };
}

export function toRunPartDeltaPayload(value: unknown): RunPartDeltaPayload {
  const payload = toPayloadSource<RunPartDeltaPayload>(value);
  if (!payload) {
    return {};
  }
  return {
    part_id: payload.part_id,
    partId: payload.partId,
    part_type: payload.part_type,
    partType: payload.partType,
    content_delta: payload.content_delta,
    delta: payload.delta,
    text: payload.text,
    content: payload.content,
    state: payload.state,
    status: payload.status,
    kind: payload.kind,
    tool_name: payload.tool_name,
    toolName: payload.toolName,
    metadata: payload.metadata,
  };
}

export function toCompletionGateWorkStatePayload(value: unknown): CompletionGateWorkStatePayload {
  const payload = toPayloadSource<CompletionGateWorkStatePayload>(value);
  if (!payload) {
    return {};
  }
  return {
    follow_up_workflow: payload.follow_up_workflow,
    followUpWorkflow: payload.followUpWorkflow,
    follow_up_step_id: payload.follow_up_step_id,
    followUpStepId: payload.followUpStepId,
    follow_up_step_label: payload.follow_up_step_label,
    followUpStepLabel: payload.followUpStepLabel,
    follow_up_prompt_type: payload.follow_up_prompt_type,
    followUpPromptType: payload.followUpPromptType,
    verification_action: payload.verification_action,
    verificationAction: payload.verificationAction,
    verification_path: payload.verification_path,
    verificationPath: payload.verificationPath,
    verification_pytest_args: payload.verification_pytest_args,
    verificationPytestArgs: payload.verificationPytestArgs,
    active_task_detail: payload.active_task_detail,
    activeTaskDetail: payload.activeTaskDetail,
  };
}

export function toWorkPlanStatePayload(value: unknown): WorkPlanStatePayload {
  const payload = toPayloadSource<WorkPlanStatePayload>(value);
  if (!payload) {
    return {};
  }
  return {
    objective: payload.objective,
    kind: payload.kind,
    steps: payload.steps,
    constraints: payload.constraints,
    done_criteria: payload.done_criteria,
    doneCriteria: payload.doneCriteria,
    long_running: payload.long_running,
    longRunning: payload.longRunning,
    coding_task: payload.coding_task,
    codingTask: payload.codingTask,
    expects_code_change: payload.expects_code_change,
    expectsCodeChange: payload.expectsCodeChange,
    expects_verification: payload.expects_verification,
    expectsVerification: payload.expectsVerification,
  };
}

export function toWorkProgressStatePayload(value: unknown): WorkProgressStatePayload | null {
  const payload = toPayloadSource<WorkProgressStatePayload>(value);
  if (!payload) {
    return null;
  }
  return {
    work_progress: payload.work_progress,
    status: payload.status,
    file_change_count: payload.file_change_count,
    fileChangeCount: payload.fileChangeCount,
    touched_paths: payload.touched_paths,
    touchedPaths: payload.touchedPaths,
    verification_attempted: payload.verification_attempted,
    verificationAttempted: payload.verificationAttempted,
    verification_passed: payload.verification_passed,
    verificationPassed: payload.verificationPassed,
    next_action: payload.next_action,
    nextAction: payload.nextAction,
    progress_signals: payload.progress_signals,
    progressSignals: payload.progressSignals,
  };
}

export function toNestedWorkProgressPayload(payload: WorkProgressEnvelopePayload): WorkProgressStatePayload | null {
  const progress = toWorkProgressStatePayload(payload.work_progress);
  if (!progress) {
    return null;
  }
  return {
    status: progress.status,
    file_change_count: progress.file_change_count,
    fileChangeCount: progress.fileChangeCount,
    touched_paths: progress.touched_paths,
    touchedPaths: progress.touchedPaths,
    verification_attempted: progress.verification_attempted,
    verificationAttempted: progress.verificationAttempted,
    verification_passed: progress.verification_passed,
    verificationPassed: progress.verificationPassed,
    next_action: progress.next_action,
    nextAction: progress.nextAction,
    progress_signals: progress.progress_signals,
    progressSignals: progress.progressSignals,
  };
}

export function toLiveRunEventPayloadSource(value: unknown): LiveRunEventPayloadSource {
  return {
    ...normalizeRunTimelinePayload(value),
    ...toRunPartDeltaPayload(value),
    ...toWorkPlanStatePayload(value),
    ...(toWorkProgressStatePayload(value) || {}),
    ...toCompletionGateWorkStatePayload(value),
  };
}
