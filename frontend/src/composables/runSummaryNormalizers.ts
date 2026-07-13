import {
  coerceBoolean,
  coerceNonNegativeInteger,
  coerceStringList,
  normalizeEventTimestamp,
} from "./chatClientCoercion";
import { toPayloadList, toPayloadSource } from "./payloadBoundary";

type EntryCount = [string, number];
type DiffSummaryActionsPayload = {
  [action: string]: unknown;
};
type DiffSummaryActionEntry = [string, unknown];
type RunSummaryCountMapPayload = {
  [key: string]: unknown;
};
type RunSummaryCountMapEntry = [string, unknown];

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

type RunSummaryBooleanStatusView = {
  attempted: boolean;
  passed: boolean;
  status: string;
  name?: string;
  summary: string;
};

type RunSummaryBooleanStatusPayload = {
  attempted?: unknown;
  passed?: unknown;
  status?: unknown;
  name?: unknown;
  summary?: unknown;
};

type RunSummaryReviewView = RunSummaryBooleanStatusView & {
  required: boolean;
  promptTypes: string[];
  findingCount: number;
};

type RunSummaryReviewPayload = RunSummaryBooleanStatusPayload & {
  required?: unknown;
  prompt_types?: unknown;
  promptTypes?: unknown;
  finding_count?: unknown;
  findingCount?: unknown;
};

export type RunSummaryToolView = {
  name: string;
  count: number;
};

type RunSummaryToolPayload = {
  name?: unknown;
  count?: unknown;
};

export type RunSummaryFileChangeView = {
  changeId: string;
  path: string;
  action: string;
  toolName: string;
  diffLen: number;
  diff: string;
  snapshotsAvailable: {
    before: boolean;
    after: boolean;
  };
};

type RunSummaryFileChangePayload = {
  change_id?: unknown;
  changeId?: unknown;
  path?: unknown;
  action?: unknown;
  tool_name?: unknown;
  toolName?: unknown;
  diff_len?: unknown;
  diffLen?: unknown;
  diff?: unknown;
  snapshots_available?: unknown;
  snapshotsAvailable?: unknown;
};

type RunSummaryFileChangeSnapshotsPayload = {
  before?: unknown;
  after?: unknown;
};

type RunSummaryArtifactCountsView = {
  total: number;
  tool: number;
  file: number;
  verification: number;
};

type RunSummaryArtifactCountsPayload = {
  total?: unknown;
  tool?: unknown;
  file?: unknown;
  verification?: unknown;
};

type RunSummaryCountsView = {
  events: number;
  parts: number;
  toolCalls: number;
  fileChanges: number;
};

type RunSummaryCountsPayload = {
  events?: unknown;
  parts?: unknown;
  tool_calls?: unknown;
  toolCalls?: unknown;
  file_changes?: unknown;
  fileChanges?: unknown;
};

export type RunSummaryWorkflowResultView = {
  workflowRunId: string | null;
  workflow: string | null;
  status: string;
  taskPreview: string;
  totalSteps: number;
  completedSteps: number;
  failedSteps: number;
  summary: string;
  createdAt: number;
};

type RunSummaryWorkflowResultPayload = {
  workflow_run_id?: unknown;
  workflowRunId?: unknown;
  workflow?: unknown;
  status?: unknown;
  task_preview?: unknown;
  taskPreview?: unknown;
  total_steps?: unknown;
  totalSteps?: unknown;
  completed_steps?: unknown;
  completedSteps?: unknown;
  failed_steps?: unknown;
  failedSteps?: unknown;
  summary?: unknown;
  created_at?: unknown;
  createdAt?: unknown;
};

type RunSummaryWorkflowPayload = {
  total?: unknown;
  by_workflow?: unknown;
  by_status?: unknown;
  results?: unknown;
};

export type RunSummaryWorkflowView = {
  total: number;
  byWorkflow: Record<string, number>;
  byStatus: Record<string, number>;
  results: RunSummaryWorkflowResultView[];
};

export type RunSummaryStructuredSubagentResultView = {
  taskId: string | null;
  promptType: string | null;
  status: string;
  summary: string;
  sectionCount: number;
  itemCount: number;
  findingCount: number;
  questionCount: number;
  residualRiskCount: number;
  createdAt: number;
};

type RunSummaryStructuredSubagentResultPayload = {
  task_id?: unknown;
  taskId?: unknown;
  prompt_type?: unknown;
  promptType?: unknown;
  status?: unknown;
  summary?: unknown;
  section_count?: unknown;
  sectionCount?: unknown;
  item_count?: unknown;
  itemCount?: unknown;
  finding_count?: unknown;
  findingCount?: unknown;
  question_count?: unknown;
  questionCount?: unknown;
  residual_risk_count?: unknown;
  residualRiskCount?: unknown;
  created_at?: unknown;
  createdAt?: unknown;
};

type RunSummaryStructuredSubagentsPayload = {
  total?: unknown;
  by_prompt_type?: unknown;
  by_status?: unknown;
  total_sections?: unknown;
  totalSections?: unknown;
  total_items?: unknown;
  totalItems?: unknown;
  total_findings?: unknown;
  totalFindings?: unknown;
  total_questions?: unknown;
  totalQuestions?: unknown;
  total_residual_risks?: unknown;
  totalResidualRisks?: unknown;
  results?: unknown;
};

export type RunSummaryStructuredSubagentsView = {
  total: number;
  byPromptType: Record<string, number>;
  byStatus: Record<string, number>;
  totalSections: number;
  totalItems: number;
  totalFindings: number;
  totalQuestions: number;
  totalResidualRisks: number;
  results: RunSummaryStructuredSubagentResultView[];
};

export type RunSummaryParallelDelegationTaskView = {
  taskId: string | null;
  promptType: string | null;
  status: string;
  summary: string;
  error: string;
  childSessionId: string | null;
  childRunId: string | null;
  fanoutIndex: number;
};

type RunSummaryParallelDelegationTaskPayload = {
  task_id?: unknown;
  taskId?: unknown;
  prompt_type?: unknown;
  promptType?: unknown;
  status?: unknown;
  summary?: unknown;
  error?: unknown;
  child_session_id?: unknown;
  childSessionId?: unknown;
  child_run_id?: unknown;
  childRunId?: unknown;
  fanout_index?: unknown;
  fanoutIndex?: unknown;
};

export type RunSummaryParallelDelegationGroupView = {
  groupId: string;
  status: string;
  totalTasks: number;
  maxParallel: number;
  completedCount: number;
  failedCount: number;
  cancelledCount: number;
  summary: string;
  createdAt: number;
  tasks: RunSummaryParallelDelegationTaskView[];
};

type RunSummaryParallelDelegationGroupPayload = {
  group_id?: unknown;
  groupId?: unknown;
  status?: unknown;
  total_tasks?: unknown;
  totalTasks?: unknown;
  max_parallel?: unknown;
  maxParallel?: unknown;
  completed_count?: unknown;
  completedCount?: unknown;
  failed_count?: unknown;
  failedCount?: unknown;
  cancelled_count?: unknown;
  cancelledCount?: unknown;
  summary?: unknown;
  created_at?: unknown;
  createdAt?: unknown;
  tasks?: unknown;
};

export type RunSummaryParallelDelegationView = {
  groupCount: number;
  taskCount: number;
  groups: RunSummaryParallelDelegationGroupView[];
};

type RunSummaryParallelDelegationPayload = {
  group_count?: unknown;
  groupCount?: unknown;
  task_count?: unknown;
  taskCount?: unknown;
  groups?: unknown;
};

type RunSummaryTaskScorecardSensorCountsView = {
  pass: number;
  warn: number;
  fail: number;
  notApplicable: number;
};

export type RunSummaryTaskScorecardView = {
  present: boolean;
  status: string;
  profile: string;
  taskType: string;
  sensorCounts: RunSummaryTaskScorecardSensorCountsView;
  failingSensors: string[];
  warningSensors: string[];
};

type RunSummaryTaskScorecardSensorCountsPayload = {
  pass?: unknown;
  warn?: unknown;
  fail?: unknown;
  not_applicable?: unknown;
  notApplicable?: unknown;
};

type RunSummaryTaskScorecardPayload = {
  present?: unknown;
  status?: unknown;
  profile?: unknown;
  task_type?: unknown;
  taskType?: unknown;
  sensor_counts?: unknown;
  sensorCounts?: unknown;
  failing_sensors?: unknown;
  failingSensors?: unknown;
  warning_sensors?: unknown;
  warningSensors?: unknown;
};

export type RunSummaryCompletionVerifierMetadataView = {
  method: string;
  role: string;
  repairAttempted: boolean;
  repairError: string;
};

type RunSummaryCompletionVerifierMetadataPayload = {
  method?: unknown;
  role?: unknown;
  repair_attempted?: unknown;
  repairAttempted?: unknown;
  repair_error?: unknown;
  repairError?: unknown;
};

export type RunSummaryCompletionVerifierView = {
  status: string;
  reason: string;
  confidence: number;
  issues: string[];
  nextAction: string;
  nextPrompt: string;
  activeTaskStatus: string;
  activeTaskDetail: string;
  followUpWorkflow: string;
  followUpStepId: string;
  followUpStepLabel: string;
  followUpPromptType: string;
  verificationAction: string;
  verificationPath: string;
  verificationPytestArgs: string[];
  verificationRequired: boolean;
  verificationAttempted: boolean;
  verificationPassed: boolean;
  reviewRequired: boolean;
  reviewAttempted: boolean;
  reviewPassed: boolean;
  reviewSummary: string;
  reviewPromptTypes: string[];
  reviewFindingCount: number;
  missingEvidence: string[];
  progressOnlyResponse: boolean;
  rawResponsePreview: string;
  metadata: RunSummaryCompletionVerifierMetadataView;
};

type RunSummaryCompletionVerifierPayload = {
  status?: unknown;
  reason?: unknown;
  confidence?: unknown;
  issues?: unknown;
  next_action?: unknown;
  nextAction?: unknown;
  next_prompt?: unknown;
  nextPrompt?: unknown;
  active_task_status?: unknown;
  activeTaskStatus?: unknown;
  active_task_detail?: unknown;
  activeTaskDetail?: unknown;
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
  verification_required?: unknown;
  verificationRequired?: unknown;
  verification_attempted?: unknown;
  verificationAttempted?: unknown;
  verification_passed?: unknown;
  verificationPassed?: unknown;
  review_required?: unknown;
  reviewRequired?: unknown;
  review_attempted?: unknown;
  reviewAttempted?: unknown;
  review_passed?: unknown;
  reviewPassed?: unknown;
  review_summary?: unknown;
  reviewSummary?: unknown;
  review_prompt_types?: unknown;
  reviewPromptTypes?: unknown;
  review_finding_count?: unknown;
  reviewFindingCount?: unknown;
  missing_evidence?: unknown;
  missingEvidence?: unknown;
  progress_only_response?: unknown;
  progressOnlyResponse?: unknown;
  raw_response_preview?: unknown;
  rawResponsePreview?: unknown;
  metadata?: unknown;
};

export type RunSummaryCompletionView = {
  schemaVersion: number;
  status: string;
  reason: string;
  shouldUpdateActiveTask: boolean;
  verificationRequired: boolean;
  verificationAttempted: boolean;
  verificationPassed: boolean;
  reviewRequired: boolean;
  reviewAttempted: boolean;
  reviewPassed: boolean;
  reviewSummary: string;
  reviewPromptTypes: string[];
  reviewFindingCount: number;
  fileChangeRequired: boolean;
  missingEvidence: string[];
  progressOnlyResponse: boolean;
  confidence: number;
  issues: string[];
  nextAction: string;
  nextPrompt: string;
  activeTaskStatus: string;
  activeTaskDetail: string;
  followUpWorkflow: string;
  followUpStepId: string;
  followUpStepLabel: string;
  followUpPromptType: string;
  verificationAction: string;
  verificationPath: string;
  verificationPytestArgs: string[];
  verifier: RunSummaryCompletionVerifierView;
};

type RunSummaryCompletionPayload = {
  schema_version?: unknown;
  schemaVersion?: unknown;
  status?: unknown;
  reason?: unknown;
  should_update_active_task?: unknown;
  shouldUpdateActiveTask?: unknown;
  verification_required?: unknown;
  verificationRequired?: unknown;
  verification_attempted?: unknown;
  verificationAttempted?: unknown;
  verification_passed?: unknown;
  verificationPassed?: unknown;
  review_required?: unknown;
  reviewRequired?: unknown;
  review_attempted?: unknown;
  reviewAttempted?: unknown;
  review_passed?: unknown;
  reviewPassed?: unknown;
  review_summary?: unknown;
  reviewSummary?: unknown;
  review_prompt_types?: unknown;
  reviewPromptTypes?: unknown;
  review_finding_count?: unknown;
  reviewFindingCount?: unknown;
  file_change_required?: unknown;
  fileChangeRequired?: unknown;
  missing_evidence?: unknown;
  missingEvidence?: unknown;
  progress_only_response?: unknown;
  progressOnlyResponse?: unknown;
  confidence?: unknown;
  issues?: unknown;
  next_action?: unknown;
  nextAction?: unknown;
  next_prompt?: unknown;
  nextPrompt?: unknown;
  active_task_status?: unknown;
  activeTaskStatus?: unknown;
  active_task_detail?: unknown;
  activeTaskDetail?: unknown;
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
  verifier?: unknown;
};

export type RunSummaryView = {
  schemaVersion: number;
  runId: string;
  sessionId: string;
  status: string;
  title: string;
  objective: string;
  duration: string;
  durationSeconds: number | null;
  result: string;
  finalAnswer: string;
  tools: RunSummaryToolView[];
  fileChanges: RunSummaryFileChangeView[];
  diffSummary: DiffSummaryView | null;
  verification: RunSummaryBooleanStatusView;
  review: RunSummaryReviewView;
  parallelDelegation: RunSummaryParallelDelegationView;
  structuredSubagents: RunSummaryStructuredSubagentsView;
  workflows: RunSummaryWorkflowView;
  taskScorecard: RunSummaryTaskScorecardView;
  completion: RunSummaryCompletionView;
  nextAction: string;
  warnings: string[];
  artifactCounts: RunSummaryArtifactCountsView;
  counts: RunSummaryCountsView;
};

export type RunSummaryPayload = {
  schema_version?: unknown;
  schemaVersion?: unknown;
  run_id?: unknown;
  runId?: unknown;
  session_id?: unknown;
  sessionId?: unknown;
  status?: unknown;
  title?: unknown;
  objective?: unknown;
  duration?: unknown;
  duration_seconds?: unknown;
  durationSeconds?: unknown;
  result?: unknown;
  final_answer?: unknown;
  finalAnswer?: unknown;
  tools?: unknown;
  file_changes?: unknown;
  fileChanges?: unknown;
  diff_summary?: unknown;
  diffSummary?: unknown;
  verification?: unknown;
  review?: unknown;
  parallel_delegation?: unknown;
  parallelDelegation?: unknown;
  structured_subagents?: unknown;
  structuredSubagents?: unknown;
  workflows?: unknown;
  task_scorecard?: unknown;
  taskScorecard?: unknown;
  completion?: unknown;
  next_action?: unknown;
  nextAction?: unknown;
  warnings?: unknown;
  artifact_counts?: unknown;
  artifactCounts?: unknown;
  counts?: unknown;
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

function toRunSummaryWorkflowResultPayload(value: unknown): RunSummaryWorkflowResultPayload | null {
  const payload = toPayloadSource<RunSummaryWorkflowResultPayload>(value);
  return payload
    ? {
        workflow_run_id: payload.workflow_run_id,
        workflowRunId: payload.workflowRunId,
        workflow: payload.workflow,
        status: payload.status,
        task_preview: payload.task_preview,
        taskPreview: payload.taskPreview,
        total_steps: payload.total_steps,
        totalSteps: payload.totalSteps,
        completed_steps: payload.completed_steps,
        completedSteps: payload.completedSteps,
        failed_steps: payload.failed_steps,
        failedSteps: payload.failedSteps,
        summary: payload.summary,
        created_at: payload.created_at,
        createdAt: payload.createdAt,
      }
    : null;
}

function normalizeRunSummaryWorkflowResult(value: unknown): RunSummaryWorkflowResultView | null {
  const result = toRunSummaryWorkflowResultPayload(value);
  if (!result) {
    return null;
  }
  return {
    workflowRunId: String(result.workflow_run_id || result.workflowRunId || "").trim() || null,
    workflow: String(result.workflow || "").trim() || null,
    status: String(result.status || "unknown").trim() || "unknown",
    taskPreview: String(result.task_preview || result.taskPreview || "").trim(),
    totalSteps: coerceNonNegativeInteger(result.total_steps ?? result.totalSteps),
    completedSteps: coerceNonNegativeInteger(result.completed_steps ?? result.completedSteps),
    failedSteps: coerceNonNegativeInteger(result.failed_steps ?? result.failedSteps),
    summary: String(result.summary || "").trim(),
    createdAt: normalizeEventTimestamp(result.created_at ?? result.createdAt),
  };
}

function toRunSummaryCountMapEntries(value: unknown): RunSummaryCountMapEntry[] {
  const payload = toPayloadSource<RunSummaryCountMapPayload>(value);
  return payload ? Object.entries(payload) : [];
}

function normalizeRunSummaryCountMap(payload: unknown): Record<string, number> {
  return Object.fromEntries(
    toRunSummaryCountMapEntries(payload)
      .map(([key, value]): EntryCount => [String(key || "").trim(), coerceNonNegativeInteger(value)])
      .filter(([key]) => key),
  );
}

function toRunSummaryWorkflowPayload(value: unknown): RunSummaryWorkflowPayload | null {
  const payload = toPayloadSource<RunSummaryWorkflowPayload>(value);
  return payload
    ? {
        total: payload.total,
        by_workflow: payload.by_workflow,
        by_status: payload.by_status,
        results: payload.results,
      }
    : null;
}

function normalizeWorkflowSummary(payload: unknown): RunSummaryWorkflowView {
  const workflowSummary = toRunSummaryWorkflowPayload(payload);
  if (!workflowSummary) {
    return { total: 0, byWorkflow: {}, byStatus: {}, results: [] };
  }
  const results = toPayloadList(workflowSummary.results)
    .map(normalizeRunSummaryWorkflowResult)
    .filter((result): result is RunSummaryWorkflowResultView => Boolean(result));
  return {
    total: coerceNonNegativeInteger(workflowSummary.total),
    byWorkflow: normalizeRunSummaryCountMap(workflowSummary.by_workflow),
    byStatus: normalizeRunSummaryCountMap(workflowSummary.by_status),
    results,
  };
}

function toRunSummaryStructuredSubagentResultPayload(value: unknown): RunSummaryStructuredSubagentResultPayload | null {
  const payload = toPayloadSource<RunSummaryStructuredSubagentResultPayload>(value);
  return payload
    ? {
        task_id: payload.task_id,
        taskId: payload.taskId,
        prompt_type: payload.prompt_type,
        promptType: payload.promptType,
        status: payload.status,
        summary: payload.summary,
        section_count: payload.section_count,
        sectionCount: payload.sectionCount,
        item_count: payload.item_count,
        itemCount: payload.itemCount,
        finding_count: payload.finding_count,
        findingCount: payload.findingCount,
        question_count: payload.question_count,
        questionCount: payload.questionCount,
        residual_risk_count: payload.residual_risk_count,
        residualRiskCount: payload.residualRiskCount,
        created_at: payload.created_at,
        createdAt: payload.createdAt,
      }
    : null;
}

function normalizeRunSummaryStructuredSubagentResult(value: unknown): RunSummaryStructuredSubagentResultView | null {
  const result = toRunSummaryStructuredSubagentResultPayload(value);
  if (!result) {
    return null;
  }
  return {
    taskId: String(result.task_id || result.taskId || "").trim() || null,
    promptType: String(result.prompt_type || result.promptType || "").trim() || null,
    status: String(result.status || "inconclusive").trim() || "inconclusive",
    summary: String(result.summary || "").trim(),
    sectionCount: coerceNonNegativeInteger(result.section_count ?? result.sectionCount),
    itemCount: coerceNonNegativeInteger(result.item_count ?? result.itemCount),
    findingCount: coerceNonNegativeInteger(result.finding_count ?? result.findingCount),
    questionCount: coerceNonNegativeInteger(result.question_count ?? result.questionCount),
    residualRiskCount: coerceNonNegativeInteger(result.residual_risk_count ?? result.residualRiskCount),
    createdAt: normalizeEventTimestamp(result.created_at ?? result.createdAt),
  };
}

function toRunSummaryStructuredSubagentsPayload(value: unknown): RunSummaryStructuredSubagentsPayload | null {
  const payload = toPayloadSource<RunSummaryStructuredSubagentsPayload>(value);
  return payload
    ? {
        total: payload.total,
        by_prompt_type: payload.by_prompt_type,
        by_status: payload.by_status,
        total_sections: payload.total_sections,
        totalSections: payload.totalSections,
        total_items: payload.total_items,
        totalItems: payload.totalItems,
        total_findings: payload.total_findings,
        totalFindings: payload.totalFindings,
        total_questions: payload.total_questions,
        totalQuestions: payload.totalQuestions,
        total_residual_risks: payload.total_residual_risks,
        totalResidualRisks: payload.totalResidualRisks,
        results: payload.results,
      }
    : null;
}

function normalizeStructuredSubagentsSummary(payload: unknown): RunSummaryStructuredSubagentsView {
  const subagentSummary = toRunSummaryStructuredSubagentsPayload(payload);
  if (!subagentSummary) {
    return {
      total: 0,
      byPromptType: {},
      byStatus: {},
      totalSections: 0,
      totalItems: 0,
      totalFindings: 0,
      totalQuestions: 0,
      totalResidualRisks: 0,
      results: [],
    };
  }
  const results = toPayloadList(subagentSummary.results)
    .map(normalizeRunSummaryStructuredSubagentResult)
    .filter((result): result is RunSummaryStructuredSubagentResultView => Boolean(result));
  return {
    total: coerceNonNegativeInteger(subagentSummary.total),
    byPromptType: normalizeRunSummaryCountMap(subagentSummary.by_prompt_type),
    byStatus: normalizeRunSummaryCountMap(subagentSummary.by_status),
    totalSections: coerceNonNegativeInteger(subagentSummary.total_sections ?? subagentSummary.totalSections),
    totalItems: coerceNonNegativeInteger(subagentSummary.total_items ?? subagentSummary.totalItems),
    totalFindings: coerceNonNegativeInteger(subagentSummary.total_findings ?? subagentSummary.totalFindings),
    totalQuestions: coerceNonNegativeInteger(subagentSummary.total_questions ?? subagentSummary.totalQuestions),
    totalResidualRisks: coerceNonNegativeInteger(subagentSummary.total_residual_risks ?? subagentSummary.totalResidualRisks),
    results,
  };
}

function toRunSummaryParallelDelegationTaskPayload(value: unknown): RunSummaryParallelDelegationTaskPayload | null {
  const payload = toPayloadSource<RunSummaryParallelDelegationTaskPayload>(value);
  return payload
    ? {
        task_id: payload.task_id,
        taskId: payload.taskId,
        prompt_type: payload.prompt_type,
        promptType: payload.promptType,
        status: payload.status,
        summary: payload.summary,
        error: payload.error,
        child_session_id: payload.child_session_id,
        childSessionId: payload.childSessionId,
        child_run_id: payload.child_run_id,
        childRunId: payload.childRunId,
        fanout_index: payload.fanout_index,
        fanoutIndex: payload.fanoutIndex,
      }
    : null;
}

function normalizeRunSummaryParallelDelegationTask(value: unknown): RunSummaryParallelDelegationTaskView | null {
  const task = toRunSummaryParallelDelegationTaskPayload(value);
  if (!task) {
    return null;
  }
  return {
    taskId: String(task.task_id || task.taskId || "").trim() || null,
    promptType: String(task.prompt_type || task.promptType || "").trim() || null,
    status: String(task.status || "unknown").trim() || "unknown",
    summary: String(task.summary || "").trim(),
    error: String(task.error || "").trim(),
    childSessionId: String(task.child_session_id || task.childSessionId || "").trim() || null,
    childRunId: String(task.child_run_id || task.childRunId || "").trim() || null,
    fanoutIndex: coerceNonNegativeInteger(task.fanout_index ?? task.fanoutIndex),
  };
}

function toRunSummaryParallelDelegationGroupPayload(value: unknown): RunSummaryParallelDelegationGroupPayload | null {
  const payload = toPayloadSource<RunSummaryParallelDelegationGroupPayload>(value);
  return payload
    ? {
        group_id: payload.group_id,
        groupId: payload.groupId,
        status: payload.status,
        total_tasks: payload.total_tasks,
        totalTasks: payload.totalTasks,
        max_parallel: payload.max_parallel,
        maxParallel: payload.maxParallel,
        completed_count: payload.completed_count,
        completedCount: payload.completedCount,
        failed_count: payload.failed_count,
        failedCount: payload.failedCount,
        cancelled_count: payload.cancelled_count,
        cancelledCount: payload.cancelledCount,
        summary: payload.summary,
        created_at: payload.created_at,
        createdAt: payload.createdAt,
        tasks: payload.tasks,
      }
    : null;
}

function normalizeRunSummaryParallelDelegationGroup(value: unknown): RunSummaryParallelDelegationGroupView | null {
  const group = toRunSummaryParallelDelegationGroupPayload(value);
  if (!group) {
    return null;
  }
  const groupId = String(group.group_id || group.groupId || "").trim();
  if (!groupId) {
    return null;
  }
  const tasks = toPayloadList(group.tasks)
    .map(normalizeRunSummaryParallelDelegationTask)
    .filter((task): task is RunSummaryParallelDelegationTaskView => Boolean(task));
  return {
    groupId,
    status: String(group.status || "unknown").trim() || "unknown",
    totalTasks: coerceNonNegativeInteger(group.total_tasks ?? group.totalTasks),
    maxParallel: coerceNonNegativeInteger(group.max_parallel ?? group.maxParallel),
    completedCount: coerceNonNegativeInteger(group.completed_count ?? group.completedCount),
    failedCount: coerceNonNegativeInteger(group.failed_count ?? group.failedCount),
    cancelledCount: coerceNonNegativeInteger(group.cancelled_count ?? group.cancelledCount),
    summary: String(group.summary || "").trim(),
    createdAt: normalizeEventTimestamp(group.created_at ?? group.createdAt),
    tasks,
  };
}

function toRunSummaryParallelDelegationPayload(value: unknown): RunSummaryParallelDelegationPayload | null {
  const payload = toPayloadSource<RunSummaryParallelDelegationPayload>(value);
  return payload
    ? {
        group_count: payload.group_count,
        groupCount: payload.groupCount,
        task_count: payload.task_count,
        taskCount: payload.taskCount,
        groups: payload.groups,
      }
    : null;
}

function normalizeParallelDelegationSummary(payload: unknown): RunSummaryParallelDelegationView {
  const delegationSummary = toRunSummaryParallelDelegationPayload(payload);
  if (!delegationSummary) {
    return { groupCount: 0, taskCount: 0, groups: [] };
  }
  const groups = toPayloadList(delegationSummary.groups)
    .map(normalizeRunSummaryParallelDelegationGroup)
    .filter((group): group is RunSummaryParallelDelegationGroupView => Boolean(group));
  return {
    groupCount: coerceNonNegativeInteger(delegationSummary.group_count ?? delegationSummary.groupCount ?? groups.length),
    taskCount: coerceNonNegativeInteger(delegationSummary.task_count ?? delegationSummary.taskCount ?? groups.reduce((total, group) => total + (group.totalTasks || group.tasks.length), 0)),
    groups,
  };
}

function toRunSummaryTaskScorecardPayload(value: unknown): RunSummaryTaskScorecardPayload | null {
  const payload = toPayloadSource<RunSummaryTaskScorecardPayload>(value);
  return payload
    ? {
        present: payload.present,
        status: payload.status,
        profile: payload.profile,
        task_type: payload.task_type,
        taskType: payload.taskType,
        sensor_counts: payload.sensor_counts,
        sensorCounts: payload.sensorCounts,
        failing_sensors: payload.failing_sensors,
        failingSensors: payload.failingSensors,
        warning_sensors: payload.warning_sensors,
        warningSensors: payload.warningSensors,
      }
    : null;
}

function toRunSummaryTaskScorecardSensorCountsPayload(
  value: unknown,
): RunSummaryTaskScorecardSensorCountsPayload | null {
  const payload = toPayloadSource<RunSummaryTaskScorecardSensorCountsPayload>(value);
  return payload
    ? {
        pass: payload.pass,
        warn: payload.warn,
        fail: payload.fail,
        not_applicable: payload.not_applicable,
        notApplicable: payload.notApplicable,
      }
    : null;
}

function normalizeTaskScorecardSensorCounts(payload: unknown): RunSummaryTaskScorecardSensorCountsView {
  const sensorCounts = toRunSummaryTaskScorecardSensorCountsPayload(payload) || {};
  return {
    pass: coerceNonNegativeInteger(sensorCounts.pass),
    warn: coerceNonNegativeInteger(sensorCounts.warn),
    fail: coerceNonNegativeInteger(sensorCounts.fail),
    notApplicable: coerceNonNegativeInteger(sensorCounts.not_applicable ?? sensorCounts.notApplicable),
  };
}

function normalizeTaskScorecardSummary(payload: unknown): RunSummaryTaskScorecardView {
  const scorecard = toRunSummaryTaskScorecardPayload(payload);
  if (!scorecard) {
    return {
      present: false,
      status: "missing",
      profile: "",
      taskType: "",
      sensorCounts: normalizeTaskScorecardSensorCounts(null),
      failingSensors: [],
      warningSensors: [],
    };
  }
  const sensorCounts = toRunSummaryTaskScorecardSensorCountsPayload(scorecard.sensor_counts)
    || toRunSummaryTaskScorecardSensorCountsPayload(scorecard.sensorCounts);
  return {
    present: coerceBoolean(scorecard.present),
    status: String(scorecard.status || "missing").trim() || "missing",
    profile: String(scorecard.profile || "").trim(),
    taskType: String(scorecard.task_type || scorecard.taskType || "").trim(),
    sensorCounts: normalizeTaskScorecardSensorCounts(sensorCounts),
    failingSensors: coerceStringList(scorecard.failing_sensors || scorecard.failingSensors),
    warningSensors: coerceStringList(scorecard.warning_sensors || scorecard.warningSensors),
  };
}

function toRunSummaryCompletionVerifierMetadataPayload(value: unknown): RunSummaryCompletionVerifierMetadataPayload {
  const payload = toPayloadSource<RunSummaryCompletionVerifierMetadataPayload>(value);
  return payload
    ? {
        method: payload.method,
        role: payload.role,
        repair_attempted: payload.repair_attempted,
        repairAttempted: payload.repairAttempted,
        repair_error: payload.repair_error,
        repairError: payload.repairError,
      }
    : {};
}

function normalizeCompletionVerifierMetadata(payload: unknown): RunSummaryCompletionVerifierMetadataView {
  const metadata = toRunSummaryCompletionVerifierMetadataPayload(payload);
  return {
    method: String(metadata.method || "").trim(),
    role: String(metadata.role || "").trim(),
    repairAttempted: coerceBoolean(metadata.repair_attempted ?? metadata.repairAttempted),
    repairError: String(metadata.repair_error || metadata.repairError || "").trim(),
  };
}

function toRunSummaryCompletionVerifierPayload(value: unknown): RunSummaryCompletionVerifierPayload {
  const payload = toPayloadSource<RunSummaryCompletionVerifierPayload>(value);
  return payload
    ? {
        status: payload.status,
        reason: payload.reason,
        confidence: payload.confidence,
        issues: payload.issues,
        next_action: payload.next_action,
        nextAction: payload.nextAction,
        next_prompt: payload.next_prompt,
        nextPrompt: payload.nextPrompt,
        active_task_status: payload.active_task_status,
        activeTaskStatus: payload.activeTaskStatus,
        active_task_detail: payload.active_task_detail,
        activeTaskDetail: payload.activeTaskDetail,
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
        verification_required: payload.verification_required,
        verificationRequired: payload.verificationRequired,
        verification_attempted: payload.verification_attempted,
        verificationAttempted: payload.verificationAttempted,
        verification_passed: payload.verification_passed,
        verificationPassed: payload.verificationPassed,
        review_required: payload.review_required,
        reviewRequired: payload.reviewRequired,
        review_attempted: payload.review_attempted,
        reviewAttempted: payload.reviewAttempted,
        review_passed: payload.review_passed,
        reviewPassed: payload.reviewPassed,
        review_summary: payload.review_summary,
        reviewSummary: payload.reviewSummary,
        review_prompt_types: payload.review_prompt_types,
        reviewPromptTypes: payload.reviewPromptTypes,
        review_finding_count: payload.review_finding_count,
        reviewFindingCount: payload.reviewFindingCount,
        missing_evidence: payload.missing_evidence,
        missingEvidence: payload.missingEvidence,
        progress_only_response: payload.progress_only_response,
        progressOnlyResponse: payload.progressOnlyResponse,
        raw_response_preview: payload.raw_response_preview,
        rawResponsePreview: payload.rawResponsePreview,
        metadata: payload.metadata,
      }
    : {};
}

function normalizeCompletionVerifier(payload: unknown): RunSummaryCompletionVerifierView {
  const verifier = toRunSummaryCompletionVerifierPayload(payload);
  return {
    status: String(verifier.status || "unknown").trim() || "unknown",
    reason: String(verifier.reason || "").trim(),
    confidence: Number.isFinite(Number(verifier.confidence)) ? Number(verifier.confidence) : 0,
    issues: coerceStringList(verifier.issues),
    nextAction: String(verifier.next_action || verifier.nextAction || "").trim(),
    nextPrompt: String(verifier.next_prompt || verifier.nextPrompt || "").trim(),
    activeTaskStatus: String(verifier.active_task_status || verifier.activeTaskStatus || "").trim(),
    activeTaskDetail: String(verifier.active_task_detail || verifier.activeTaskDetail || "").trim(),
    followUpWorkflow: String(verifier.follow_up_workflow || verifier.followUpWorkflow || "").trim(),
    followUpStepId: String(verifier.follow_up_step_id || verifier.followUpStepId || "").trim(),
    followUpStepLabel: String(verifier.follow_up_step_label || verifier.followUpStepLabel || "").trim(),
    followUpPromptType: String(verifier.follow_up_prompt_type || verifier.followUpPromptType || "").trim(),
    verificationAction: String(verifier.verification_action || verifier.verificationAction || "").trim(),
    verificationPath: String(verifier.verification_path || verifier.verificationPath || "").trim(),
    verificationPytestArgs: coerceStringList(verifier.verification_pytest_args || verifier.verificationPytestArgs),
    verificationRequired: coerceBoolean(verifier.verification_required ?? verifier.verificationRequired),
    verificationAttempted: coerceBoolean(verifier.verification_attempted ?? verifier.verificationAttempted),
    verificationPassed: coerceBoolean(verifier.verification_passed ?? verifier.verificationPassed),
    reviewRequired: coerceBoolean(verifier.review_required ?? verifier.reviewRequired),
    reviewAttempted: coerceBoolean(verifier.review_attempted ?? verifier.reviewAttempted),
    reviewPassed: coerceBoolean(verifier.review_passed ?? verifier.reviewPassed),
    reviewSummary: String(verifier.review_summary || verifier.reviewSummary || "").trim(),
    reviewPromptTypes: coerceStringList(verifier.review_prompt_types || verifier.reviewPromptTypes),
    reviewFindingCount: coerceNonNegativeInteger(verifier.review_finding_count ?? verifier.reviewFindingCount),
    missingEvidence: coerceStringList(verifier.missing_evidence || verifier.missingEvidence),
    progressOnlyResponse: coerceBoolean(verifier.progress_only_response ?? verifier.progressOnlyResponse),
    rawResponsePreview: String(verifier.raw_response_preview || verifier.rawResponsePreview || "").trim(),
    metadata: normalizeCompletionVerifierMetadata(verifier.metadata),
  };
}

function toRunSummaryCompletionPayload(value: unknown): RunSummaryCompletionPayload {
  const payload = toPayloadSource<RunSummaryCompletionPayload>(value);
  return payload
    ? {
        schema_version: payload.schema_version,
        schemaVersion: payload.schemaVersion,
        status: payload.status,
        reason: payload.reason,
        should_update_active_task: payload.should_update_active_task,
        shouldUpdateActiveTask: payload.shouldUpdateActiveTask,
        verification_required: payload.verification_required,
        verificationRequired: payload.verificationRequired,
        verification_attempted: payload.verification_attempted,
        verificationAttempted: payload.verificationAttempted,
        verification_passed: payload.verification_passed,
        verificationPassed: payload.verificationPassed,
        review_required: payload.review_required,
        reviewRequired: payload.reviewRequired,
        review_attempted: payload.review_attempted,
        reviewAttempted: payload.reviewAttempted,
        review_passed: payload.review_passed,
        reviewPassed: payload.reviewPassed,
        review_summary: payload.review_summary,
        reviewSummary: payload.reviewSummary,
        review_prompt_types: payload.review_prompt_types,
        reviewPromptTypes: payload.reviewPromptTypes,
        review_finding_count: payload.review_finding_count,
        reviewFindingCount: payload.reviewFindingCount,
        file_change_required: payload.file_change_required,
        fileChangeRequired: payload.fileChangeRequired,
        missing_evidence: payload.missing_evidence,
        missingEvidence: payload.missingEvidence,
        progress_only_response: payload.progress_only_response,
        progressOnlyResponse: payload.progressOnlyResponse,
        confidence: payload.confidence,
        issues: payload.issues,
        next_action: payload.next_action,
        nextAction: payload.nextAction,
        next_prompt: payload.next_prompt,
        nextPrompt: payload.nextPrompt,
        active_task_status: payload.active_task_status,
        activeTaskStatus: payload.activeTaskStatus,
        active_task_detail: payload.active_task_detail,
        activeTaskDetail: payload.activeTaskDetail,
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
        verifier: payload.verifier,
      }
    : {};
}

function normalizeCompletionSummary(payload: unknown): RunSummaryCompletionView {
  const completion = toRunSummaryCompletionPayload(payload);
  return {
    schemaVersion: coerceNonNegativeInteger(completion.schema_version ?? completion.schemaVersion),
    status: String(completion.status || "unknown").trim() || "unknown",
    reason: String(completion.reason || "").trim(),
    shouldUpdateActiveTask: coerceBoolean(completion.should_update_active_task ?? completion.shouldUpdateActiveTask),
    verificationRequired: coerceBoolean(completion.verification_required ?? completion.verificationRequired),
    verificationAttempted: coerceBoolean(completion.verification_attempted ?? completion.verificationAttempted),
    verificationPassed: coerceBoolean(completion.verification_passed ?? completion.verificationPassed),
    reviewRequired: coerceBoolean(completion.review_required ?? completion.reviewRequired),
    reviewAttempted: coerceBoolean(completion.review_attempted ?? completion.reviewAttempted),
    reviewPassed: coerceBoolean(completion.review_passed ?? completion.reviewPassed),
    reviewSummary: String(completion.review_summary || completion.reviewSummary || "").trim(),
    reviewPromptTypes: coerceStringList(completion.review_prompt_types || completion.reviewPromptTypes),
    reviewFindingCount: coerceNonNegativeInteger(completion.review_finding_count ?? completion.reviewFindingCount),
    fileChangeRequired: coerceBoolean(completion.file_change_required ?? completion.fileChangeRequired),
    missingEvidence: coerceStringList(completion.missing_evidence || completion.missingEvidence),
    progressOnlyResponse: coerceBoolean(completion.progress_only_response ?? completion.progressOnlyResponse),
    confidence: Number.isFinite(Number(completion.confidence)) ? Number(completion.confidence) : 0,
    issues: coerceStringList(completion.issues),
    nextAction: String(completion.next_action || completion.nextAction || "").trim(),
    nextPrompt: String(completion.next_prompt || completion.nextPrompt || "").trim(),
    activeTaskStatus: String(completion.active_task_status || completion.activeTaskStatus || "").trim(),
    activeTaskDetail: String(completion.active_task_detail || completion.activeTaskDetail || "").trim(),
    followUpWorkflow: String(completion.follow_up_workflow || completion.followUpWorkflow || "").trim(),
    followUpStepId: String(completion.follow_up_step_id || completion.followUpStepId || "").trim(),
    followUpStepLabel: String(completion.follow_up_step_label || completion.followUpStepLabel || "").trim(),
    followUpPromptType: String(completion.follow_up_prompt_type || completion.followUpPromptType || "").trim(),
    verificationAction: String(completion.verification_action || completion.verificationAction || "").trim(),
    verificationPath: String(completion.verification_path || completion.verificationPath || "").trim(),
    verificationPytestArgs: coerceStringList(completion.verification_pytest_args || completion.verificationPytestArgs),
    verifier: normalizeCompletionVerifier(completion.verifier),
  };
}

function toRunSummaryToolPayload(value: unknown): RunSummaryToolPayload | null {
  const payload = toPayloadSource<RunSummaryToolPayload>(value);
  return payload
    ? {
        name: payload.name,
        count: payload.count,
      }
    : null;
}

function normalizeRunSummaryTool(value: unknown): RunSummaryToolView | null {
  const tool = toRunSummaryToolPayload(value);
  if (!tool) {
    return null;
  }
  const name = String(tool.name || "").trim();
  if (!name) {
    return null;
  }
  return {
    name,
    count: coerceNonNegativeInteger(tool.count),
  };
}

function toRunSummaryFileChangePayload(value: unknown): RunSummaryFileChangePayload | null {
  const payload = toPayloadSource<RunSummaryFileChangePayload>(value);
  return payload
    ? {
        change_id: payload.change_id,
        changeId: payload.changeId,
        path: payload.path,
        action: payload.action,
        tool_name: payload.tool_name,
        toolName: payload.toolName,
        diff_len: payload.diff_len,
        diffLen: payload.diffLen,
        diff: payload.diff,
        snapshots_available: payload.snapshots_available,
        snapshotsAvailable: payload.snapshotsAvailable,
      }
    : null;
}

function toRunSummaryFileChangeSnapshotsPayload(value: unknown): RunSummaryFileChangeSnapshotsPayload | null {
  const payload = toPayloadSource<RunSummaryFileChangeSnapshotsPayload>(value);
  return payload
    ? {
        before: payload.before,
        after: payload.after,
      }
    : null;
}

function normalizeRunSummaryFileChange(value: unknown): RunSummaryFileChangeView | null {
  const change = toRunSummaryFileChangePayload(value);
  if (!change) {
    return null;
  }
  const path = String(change.path || "").trim();
  if (!path) {
    return null;
  }
  const snapshots = toRunSummaryFileChangeSnapshotsPayload(change.snapshots_available)
    || toRunSummaryFileChangeSnapshotsPayload(change.snapshotsAvailable)
    || {};
  return {
    changeId: String(change.change_id || change.changeId || "").trim(),
    path,
    action: String(change.action || "").trim(),
    toolName: String(change.tool_name || change.toolName || "").trim(),
    diffLen: coerceNonNegativeInteger(change.diff_len ?? change.diffLen),
    diff: String(change.diff || ""),
    snapshotsAvailable: {
      before: coerceBoolean(snapshots.before),
      after: coerceBoolean(snapshots.after),
    },
  };
}

function toRunSummaryBooleanStatusPayload(value: unknown): RunSummaryBooleanStatusPayload {
  const payload = toPayloadSource<RunSummaryBooleanStatusPayload>(value);
  return payload
    ? {
        attempted: payload.attempted,
        passed: payload.passed,
        status: payload.status,
        name: payload.name,
        summary: payload.summary,
      }
    : {};
}

function normalizeRunSummaryBooleanStatus(
  value: unknown,
  defaultStatus: string,
): RunSummaryBooleanStatusView {
  const status = toRunSummaryBooleanStatusPayload(value);
  return {
    attempted: coerceBoolean(status.attempted),
    passed: coerceBoolean(status.passed),
    status: String(status.status || defaultStatus).trim() || defaultStatus,
    name: String(status.name || "").trim(),
    summary: String(status.summary || "").trim(),
  };
}

function toRunSummaryReviewPayload(value: unknown): RunSummaryReviewPayload {
  const payload = toPayloadSource<RunSummaryReviewPayload>(value);
  return {
    ...toRunSummaryBooleanStatusPayload(payload),
    required: payload?.required,
    prompt_types: payload?.prompt_types,
    promptTypes: payload?.promptTypes,
    finding_count: payload?.finding_count,
    findingCount: payload?.findingCount,
  };
}

function normalizeRunSummaryReview(value: unknown): RunSummaryReviewView {
  const review = toRunSummaryReviewPayload(value);
  return {
    ...normalizeRunSummaryBooleanStatus(review, "not_required"),
    required: coerceBoolean(review.required),
    promptTypes: coerceStringList(review.prompt_types || review.promptTypes),
    findingCount: coerceNonNegativeInteger(review.finding_count ?? review.findingCount),
  };
}

function toRunSummaryArtifactCountsPayload(value: unknown): RunSummaryArtifactCountsPayload {
  const payload = toPayloadSource<RunSummaryArtifactCountsPayload>(value);
  return payload
    ? {
        total: payload.total,
        tool: payload.tool,
        file: payload.file,
        verification: payload.verification,
      }
    : {};
}

function normalizeRunSummaryArtifactCounts(value: unknown): RunSummaryArtifactCountsView {
  const artifactCounts = toRunSummaryArtifactCountsPayload(value);
  return {
    total: coerceNonNegativeInteger(artifactCounts.total),
    tool: coerceNonNegativeInteger(artifactCounts.tool),
    file: coerceNonNegativeInteger(artifactCounts.file),
    verification: coerceNonNegativeInteger(artifactCounts.verification),
  };
}

function toRunSummaryCountsPayload(value: unknown): RunSummaryCountsPayload {
  const payload = toPayloadSource<RunSummaryCountsPayload>(value);
  return payload
    ? {
        events: payload.events,
        parts: payload.parts,
        tool_calls: payload.tool_calls,
        toolCalls: payload.toolCalls,
        file_changes: payload.file_changes,
        fileChanges: payload.fileChanges,
      }
    : {};
}

function normalizeRunSummaryCounts(value: unknown): RunSummaryCountsView {
  const counts = toRunSummaryCountsPayload(value);
  return {
    events: coerceNonNegativeInteger(counts.events),
    parts: coerceNonNegativeInteger(counts.parts),
    toolCalls: coerceNonNegativeInteger(counts.tool_calls ?? counts.toolCalls),
    fileChanges: coerceNonNegativeInteger(counts.file_changes ?? counts.fileChanges),
  };
}

function toRunSummaryPayload(value: unknown): RunSummaryPayload | null {
  const payload = toPayloadSource<RunSummaryPayload>(value);
  return payload
    ? {
        schema_version: payload.schema_version,
        schemaVersion: payload.schemaVersion,
        run_id: payload.run_id,
        runId: payload.runId,
        session_id: payload.session_id,
        sessionId: payload.sessionId,
        status: payload.status,
        title: payload.title,
        objective: payload.objective,
        duration: payload.duration,
        duration_seconds: payload.duration_seconds,
        durationSeconds: payload.durationSeconds,
        result: payload.result,
        final_answer: payload.final_answer,
        finalAnswer: payload.finalAnswer,
        tools: payload.tools,
        file_changes: payload.file_changes,
        fileChanges: payload.fileChanges,
        diff_summary: payload.diff_summary,
        diffSummary: payload.diffSummary,
        verification: payload.verification,
        review: payload.review,
        parallel_delegation: payload.parallel_delegation,
        parallelDelegation: payload.parallelDelegation,
        structured_subagents: payload.structured_subagents,
        structuredSubagents: payload.structuredSubagents,
        workflows: payload.workflows,
        task_scorecard: payload.task_scorecard,
        taskScorecard: payload.taskScorecard,
        completion: payload.completion,
        next_action: payload.next_action,
        nextAction: payload.nextAction,
        warnings: payload.warnings,
        artifact_counts: payload.artifact_counts,
        artifactCounts: payload.artifactCounts,
        counts: payload.counts,
      }
    : null;
}

export function normalizeRunSummary(payload: unknown): RunSummaryView | null {
  const summary = toRunSummaryPayload(payload);
  if (!summary) {
    return null;
  }

  const parallelDelegation = normalizeParallelDelegationSummary(summary.parallel_delegation || summary.parallelDelegation);
  const structuredSubagents = normalizeStructuredSubagentsSummary(summary.structured_subagents || summary.structuredSubagents);
  const workflows = normalizeWorkflowSummary(summary.workflows);
  const taskScorecard = normalizeTaskScorecardSummary(
    summary.task_scorecard || summary.taskScorecard,
  );
  const tools = toPayloadList(summary.tools);
  const fileChanges = toPayloadList(summary.file_changes || summary.fileChanges);
  return {
    schemaVersion: coerceNonNegativeInteger(summary.schema_version ?? summary.schemaVersion),
    runId: String(summary.run_id || summary.runId || "").trim(),
    sessionId: String(summary.session_id || summary.sessionId || "").trim(),
    status: String(summary.status || "completed").trim() || "completed",
    title: String(summary.title || "").trim(),
    objective: String(summary.objective || "").trim(),
    duration: String(summary.duration || "").trim(),
    durationSeconds: Number.isFinite(Number(summary.duration_seconds ?? summary.durationSeconds))
      ? Number(summary.duration_seconds ?? summary.durationSeconds)
      : null,
    result: String(summary.result || "").trim(),
    finalAnswer: String(summary.final_answer || summary.finalAnswer || "").trim(),
    tools: tools
      .map(normalizeRunSummaryTool)
      .filter((tool): tool is RunSummaryToolView => Boolean(tool)),
    fileChanges: fileChanges
      .map(normalizeRunSummaryFileChange)
      .filter((change): change is RunSummaryFileChangeView => Boolean(change)),
    diffSummary: normalizeDiffSummary(summary.diff_summary || summary.diffSummary),
    verification: normalizeRunSummaryBooleanStatus(summary.verification, "not_attempted"),
    review: normalizeRunSummaryReview(summary.review),
    parallelDelegation,
    structuredSubagents,
    workflows,
    taskScorecard,
    completion: normalizeCompletionSummary(summary.completion),
    nextAction: String(summary.next_action || summary.nextAction || "").trim(),
    warnings: coerceStringList(summary.warnings),
    artifactCounts: normalizeRunSummaryArtifactCounts(summary.artifact_counts || summary.artifactCounts),
    counts: normalizeRunSummaryCounts(summary.counts),
  };
}
