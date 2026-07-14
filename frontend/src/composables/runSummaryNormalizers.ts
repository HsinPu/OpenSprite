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
  parallelDelegation: RunSummaryParallelDelegationView;
  structuredSubagents: RunSummaryStructuredSubagentsView;
  workflows: RunSummaryWorkflowView;
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
  parallel_delegation?: unknown;
  parallelDelegation?: unknown;
  structured_subagents?: unknown;
  structuredSubagents?: unknown;
  workflows?: unknown;
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
        parallel_delegation: payload.parallel_delegation,
        parallelDelegation: payload.parallelDelegation,
        structured_subagents: payload.structured_subagents,
        structuredSubagents: payload.structuredSubagents,
        workflows: payload.workflows,
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
    parallelDelegation,
    structuredSubagents,
    workflows,
    warnings: coerceStringList(summary.warnings),
    artifactCounts: normalizeRunSummaryArtifactCounts(summary.artifact_counts || summary.artifactCounts),
    counts: normalizeRunSummaryCounts(summary.counts),
  };
}
