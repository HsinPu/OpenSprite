import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "../lib/reactiveCompat";
import { getDisplayCopy } from "../i18n/copy";
import { useBrowserSettingsActions } from "./useBrowserSettingsActions";
import { useChannelSettingsActions } from "./useChannelSettingsActions";
import {
  coerceBoolean,
  coerceNonNegativeInteger,
  coerceStringList,
  coerceText as textField,
  normalizeEventTimestamp,
  previewText,
} from "./chatClientCoercion";
import {
  toCommandCatalogItemPayload,
  toCommandCatalogPayload,
  toSettingsErrorPayload,
  type CommandCatalogPayload,
} from "./chatClientApiPayloads";
import {
  normalizeSessionHistoryMetrics,
  toHistoryRunPayloadList,
  toSessionClearPayload,
  toSessionHistoryPayload,
  type HistoryEntryContentPayload,
  type HistoryEntryPayload,
  type HistoryMessagePayload,
  type HistoryRunPayload,
  type HistorySessionPayload,
  type HistorySessionStatusPayload,
  type SessionClearPayload,
  type SessionHistoryChannelTotals,
  type SessionHistoryPayload,
} from "./chatClientHistoryPayloads";
import {
  toCronJobsPayload,
} from "./chatClientCronPayloads";
import {
  toLiveRunEventPayloadSource,
  toRunPartDeltaPayload,
  type LiveRunEventPayloadSource,
  type RunEventPayloadInput,
  type RunPartDeltaPayload,
} from "./chatClientEventPayloads";
import {
  parseLiveSocketMessage,
  type LiveAssistantMessagePayload,
  type LiveRunEventPayload,
  type LiveSessionIdentityPayload,
  type LiveSessionStatusPayload,
  type LiveSocketErrorPayload,
} from "./chatClientLiveSocket";
import {
  toLiveEntryMetadata,
  toOutgoingMessageInputPayload,
  type OutgoingMessageMetadata,
} from "./chatClientMessagePayloads";
import { useLogSettingsActions } from "./useLogSettingsActions";
import { useMcpSettingsActions } from "./useMcpSettingsActions";
import { useModelSettingsActions } from "./useModelSettingsActions";
import { useNetworkSettingsActions } from "./useNetworkSettingsActions";
import { useProviderAuthActions } from "./useProviderAuthActions";
import { useProviderSettingsActions } from "./useProviderSettingsActions";
import { resetProviderConnectForm } from "./providerConnectForm";
import { useScheduleSettingsActions } from "./useScheduleSettingsActions";
import { useSearchSettingsActions } from "./useSearchSettingsActions";
import { useUpdateSettingsActions } from "./useUpdateSettingsActions";
import { createSettingsSectionLoader, normalizeSettingsSectionId, type SettingsSectionId } from "./settingsSectionLoaders";
import {
  buildHttpApiUrl,
  requestSettingsJson as requestSettingsJsonFromApi,
} from "./settingsApi";
import {
  buildRunFileChangeRevertPath,
  buildRunSummaryPath,
  buildRunTracePath,
  buildRunsPath,
  buildSessionDeletePath,
  buildSessionsClearPath,
  buildWorktreeCleanupPath,
} from "./chatClientPaths";
import {
  DEFAULT_COLOR_SCHEME,
  DEFAULT_LANGUAGE,
  SUPPORTED_COLOR_SCHEMES,
  SUPPORTED_LANGUAGES,
  getResolvedColorScheme,
  normalizeChoice,
  readStoredBoolean,
  readStoredChoice,
  readStoredValue,
  type ColorSchemePreference,
  type LanguagePreference,
  writeStoredValue,
} from "./chatClientPreferences";
import {
  channelFromSessionId,
  externalChatIdFromSessionId,
  generateExternalChatId,
  generateOverlayProfileId,
  isExternalChannelSessionId,
} from "./chatClientSessionIds";
import {
  createSession,
  type ChatMessage,
  type ChatSession,
  type ChatSessionStatus,
  type LiveEntry,
  type LiveEntryContentItem,
  type SessionChannelFilter,
  isLocalDraftSession,
  makeLiveEntry,
  makeMessage,
  normalizeChatMessageRole,
  normalizeSessionChannelFilter,
  readStoredDraftSessions,
  summarizeTitle,
  writeStoredDraftSessions,
} from "./chatClientSessions";
import { randomToken } from "./chatClientTokens";
import {
  createRunViewState,
  formatRunFinishDetail,
  formatSubagentDetail,
  formatSubagentGroupDetail,
  formatWorkflowDetail,
  formatWorkflowStepDetail,
  isRunSummaryTriggerEventType,
  isTerminalRunStatus,
  normalizeRunFinishDetail,
  normalizeRunTimelinePayload,
  normalizeSubagentDetail,
  normalizeWorkflowDetail,
  type RunTimelinePayload,
  type RunTimelineEventView,
  type RunTimelineTone,
  type RunViewState,
  runStatusLabel,
  runTone,
  sessionStatusLabel,
  shortRunId,
  statusFromRunEvent,
} from "./chatClientRunHelpers";
import {
  beginRequestGeneration,
  captureRunTraceWatermark,
  createSessionHistoryRefreshQueue,
  createSessionSnapshotFence,
  enqueueSessionHistoryRefresh,
  fileChangesRepresentSameOccurrence,
  isCurrentRequestGeneration,
  mergeFreshSessionSnapshot,
  mergeMonotonicRunStatus,
  mergeRunTraceSnapshot,
  takePendingSessionHistoryRefresh,
  type SessionHistoryRefreshRequest,
  type SessionSnapshotFence,
} from "./chatClientStateMerges";
import {
  toRunFileChangeRevertPayload,
  toRunsPayload,
  toRunTracePayload,
  toWorktreeCleanupPayload,
  type RunFileChangeRevertPayload,
  type RunFileChangeRevertRecord,
  type RunsPayload,
  type RunTracePayload,
  type WorktreeCleanupRecord,
  type WorktreeCleanupPayload,
} from "./chatClientRunPayloads";
import {
  normalizeRunSummary,
  type RunSummaryFileChangeView,
  type RunSummaryView,
} from "./runSummaryNormalizers";
import {
  applyWorktreeCleanupEvent,
  compactRunEvents,
  findWorktreeSandbox,
  inferRunEventKind,
  inferRunEventStatus,
  normalizeRunArtifact,
  normalizeRunArtifactMetadata,
  normalizeRunKind,
  normalizeTraceEventArtifact,
  normalizeTracePart,
  normalizeTracePartMetadata,
  preserveKnownRemovedWorktreeSandbox,
  type BackgroundProcessEventPayload,
  type RunArtifactMetadata,
  type RunArtifactView,
  type RunEventKind,
  type TraceEventView,
  type TraceFileChangeView,
  type TracePartMetadata,
  type TracePartView,
  updateLiveTraceEventCounts,
} from "./runTraceNormalizers";
import { DEFAULT_CRON_TIMEZONE, normalizeCronJobMode, type CronJobAction, type CronJobMode } from "./scheduleDefaults";
import { createSettingsForm, createSettingsState, type CronJobView } from "./useSettingsState";

type DisplayCopy = ReturnType<typeof getDisplayCopy>;
type RunEventDescription = { label: string; detail: string; tone: RunTimelineTone };
type RunEventPayloadView = {
  message: string;
  toolName: string;
  argsPreview: string;
  action: string;
  path: string;
  verificationOk: boolean;
  resultPreview: string;
  diffPreview: string;
  inputDelta: string;
  contentDelta: string;
  command: string;
  processSessionId: string;
  backgroundExitCodeText: string;
  backgroundSucceeded: boolean;
  hadToolError: boolean;
  status: string;
  error: string;
};
type CurrentRunSummaryView = {
  shortId: string;
  statusLabel: string;
  title: string;
  tone: RunTimelineTone;
};
type ReconnectNotice = string | ((seconds: number) => string);

type EnsureSessionOptions = { allowDeleted?: boolean };
type LoadRunsOptions = { force?: boolean };
type MergeHistorySessionOptions = {
  preserveDetails?: boolean;
  changedSinceRequest?: boolean;
};
type MergeHistorySessionsOptions = {
  preserveActiveSession?: boolean;
  pruneMissingHistorySessions?: boolean;
  sessionRevisionWatermark?: ReadonlyMap<string, number>;
};
type LoadSessionHistoryOptions = {
  quiet?: boolean;
  pruneMissingHistorySessions?: boolean;
};
type ScrollOptions = { force?: boolean };
type SessionIdentity = {
  sessionId?: unknown;
  externalChatId?: unknown;
  transportExternalChatId?: unknown;
};
type DeletedSessionIdentity = {
  sessionId?: unknown;
  externalChatId?: unknown;
  transportExternalChatId?: unknown;
};
type DisconnectSocketOptions = { manual?: boolean };
type SendMessageOptions = { clearComposer?: boolean };
type ComposerSubmitEvent = { preventDefault: () => void };
type ComposerKeyboardEvent = ComposerSubmitEvent & {
  key: string;
  shiftKey: boolean;
  isComposing?: boolean;
};
type OutgoingMessagePayload = {
  text: string;
  metadata: OutgoingMessageMetadata;
};

type CronJobPayload = {
  session_id: string;
  kind: CronJobMode;
  name: string;
  message: string;
  deliver: boolean;
  every_seconds?: number;
  cron_expr?: string;
  tz?: string;
  at?: string;
};

export type ConnectionState = "disconnected" | "connecting" | "connected";
export interface CommandCatalogItem {
  name: string;
  command: string;
  usage: string;
  description: string;
  category: string;
  subcommands: string[];
}
export type NoticeTone = "info" | "success" | "warning" | "error";
export type NoticeState = {
  text: string;
  tone: NoticeTone;
};
export interface ToastNotice extends NoticeState {
  id: string;
}
type CommandCatalogState = {
  commands: CommandCatalogItem[];
  loading: boolean;
  error: string;
};
type SessionHistoryState = {
  total: number;
  limit: number;
  channelTotals: SessionHistoryChannelTotals;
};
type ChatClientState = {
  wsUrl: string;
  accessToken: string;
  displayName: string;
  showRunHistory: boolean;
  showRunTimeline: boolean;
  showRunSummary: boolean;
  showRunTrace: boolean;
  language: LanguagePreference;
  colorScheme: ColorSchemePreference;
  activeExternalChatId: string;
  sessions: ChatSession[];
  connectionState: ConnectionState;
  authRequired: boolean;
  authError: string;
  notice: NoticeState;
  commandCatalog: CommandCatalogState;
  sessionHistory: SessionHistoryState;
};
type NormalizedSessionHistoryPayload = {
  sessions: ChatSession[];
  total: number;
  limit: number;
  channelTotals: SessionHistoryChannelTotals;
};
type SessionClearResult = { deleted: number };
type LiveSessionIdentity = {
  sessionId: string;
  channel: string;
  transportExternalChatId: string;
};
type LiveRunEventView = TraceEventView & {
  runId: string;
  payload: LiveRunEventPayloadSource;
};
type RunTraceFallbackArtifactSource = {
  artifact: RunArtifactView | null;
};
type LiveAssistantMessageView = LiveSessionIdentity & {
  externalChatId: string;
  text: string;
};
type RunPartDeltaView = {
  existingIndex: number;
  existing: TracePartView | null;
  partId: string;
  partType: string;
  delta: string;
  state: string;
  kind: RunEventKind;
  toolName: string;
  metadata: TracePartMetadata;
  createdAt: number;
};

function normalizeSessionClearPayload(payload: SessionClearPayload | null): SessionClearResult {
  return {
    deleted: coerceNonNegativeInteger(payload?.deleted ?? payload?.deleted_count ?? payload?.deletedCount),
  };
}

function normalizeRunFileChangeRevertPayload(payload: RunFileChangeRevertPayload | null): RunFileChangeRevertPayload {
  return payload || {
    revert: null,
    applied: false,
    reason: "",
  };
}

function normalizeWorktreeCleanupPayload(payload: WorktreeCleanupPayload | null): WorktreeCleanupPayload {
  return payload || {
    ok: false,
    cleanup: null,
    reason: "",
    status: "",
  };
}

function normalizeRunSummaryFileChanges(summary: RunSummaryView | null | undefined): RunSummaryFileChangeView[] {
  return Array.isArray(summary?.fileChanges) ? summary.fileChanges : [];
}

function normalizeRunTracePayload(payload: RunTracePayload | null): RunTracePayload {
  return payload || {
    rawEvents: [],
    fileChanges: [],
    parts: [],
    artifacts: [],
    eventCounts: {
      total: 0,
      returned: 0,
      compacted: 0,
      textTotal: 0,
      textReturned: 0,
      maxEvents: 0,
      maxTextEvents: 0,
    },
    diffSummary: null,
  };
}

function collectRunTraceFallbackArtifacts(...sources: RunTraceFallbackArtifactSource[][]): RunArtifactView[] {
  return sources.flatMap((source) =>
    source
      .map((item) => item.artifact)
      .filter((artifact): artifact is RunArtifactView => artifact !== null),
  );
}

function normalizeLiveSocketErrorMessage(payload: LiveSocketErrorPayload, fallback: string): string {
  return String(payload.error || fallback);
}

function normalizeHistorySessionStatus(status: HistorySessionStatusPayload): ChatSessionStatus {
  return {
    status: textField(status.status) || "idle",
    updatedAt: normalizeEventTimestamp(status.updated_at ?? status.updatedAt),
    metadata: {},
  };
}

function normalizeLiveSessionStatus(payload: LiveSessionStatusPayload): ChatSessionStatus {
  return {
    status: textField(payload.status) || "idle",
    updatedAt: normalizeEventTimestamp(payload.updated_at ?? payload.updatedAt),
    metadata: {},
  };
}

function normalizeLiveRunEvent(payload: LiveRunEventPayload): LiveRunEventView {
  const eventType = textField(payload.event_type || payload.eventType) || "run_event";
  const eventPayload = toLiveRunEventPayloadSource(payload.payload);
  const eventKind = normalizeRunKind(payload.kind, inferRunEventKind(eventType));
  const eventStatus = textField(payload.status || inferRunEventStatus(eventType, eventPayload));
  const createdAt = normalizeEventTimestamp(payload.created_at ?? payload.createdAt);
  const runId = textField(payload.run_id || payload.runId) || `run-${Date.now().toString(36)}-${randomToken()}`;
  return {
    runId,
    id: `${runId}-raw-${eventType}-${createdAt}-${randomToken()}`,
    schemaVersion: 0,
    eventType,
    payload: eventPayload,
    kind: eventKind,
    status: eventStatus,
    createdAt,
    artifact: normalizeTraceEventArtifact(eventType, eventPayload, payload.artifact, {
      kind: eventKind,
      status: eventStatus,
      source: "event",
      sourceId: `${eventType}-${createdAt}`,
      createdAt,
    }),
  };
}

function traceEventFromLiveRunEvent(event: LiveRunEventView): TraceEventView {
  return {
    id: event.id,
    schemaVersion: event.schemaVersion,
    eventType: event.eventType,
    kind: event.kind,
    status: event.status,
    createdAt: event.createdAt,
    payload: event.payload,
    artifact: event.artifact,
  };
}

function normalizeLiveAssistantMessage(
  payload: LiveAssistantMessagePayload,
  fallbackExternalChatId: string | null | undefined,
): LiveAssistantMessageView {
  const identity = normalizeLiveSessionIdentity(payload);
  return {
    ...identity,
    externalChatId: identity.transportExternalChatId || fallbackExternalChatId || generateExternalChatId(),
    text: String(payload.text || ""),
  };
}

function settingsErrorStatus(error: unknown): number | null {
  const record = toSettingsErrorPayload(error);
  const status = Number(record?.status);
  return Number.isFinite(status) ? status : null;
}

function settingsErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  const record = toSettingsErrorPayload(error);
  const message = String(record?.message || "").trim();
  return message || fallback;
}

function normalizeRunEventPayload(payload: RunEventPayloadInput): RunEventPayloadView {
  const backgroundExitCode = payload.exit_code ?? payload.exitCode;
  return {
    message: textField(payload.message),
    toolName: textField(payload.tool_name || payload.toolName),
    argsPreview: textField(payload.args_preview || payload.argsPreview),
    action: textField(payload.action),
    path: textField(payload.path),
    verificationOk: payload.ok !== false,
    resultPreview: textField(payload.result_preview || payload.resultPreview),
    diffPreview: textField(payload.diff_preview || payload.diffPreview || payload.action),
    inputDelta: textField(payload.input_delta || payload.inputDelta),
    contentDelta: textField(payload.content_delta || payload.contentDelta),
    command: textField(payload.command),
    processSessionId: textField(payload.process_session_id || payload.processSessionId),
    backgroundExitCodeText: backgroundExitCode !== undefined && backgroundExitCode !== null ? String(backgroundExitCode) : "",
    backgroundSucceeded: Number(backgroundExitCode ?? 0) === 0,
    hadToolError: Boolean(payload.had_tool_error ?? payload.hadToolError),
    status: textField(payload.status),
    error: textField(payload.error),
  };
}

function normalizeLiveSessionIdentity(payload: LiveSessionIdentityPayload): LiveSessionIdentity {
  const sessionId = textField(payload.session_id || payload.sessionId);
  return {
    sessionId,
    channel: textField(payload.channel || channelFromSessionId(sessionId) || "web") || "web",
    transportExternalChatId: textField(payload.external_chat_id || payload.externalChatId)
      || externalChatIdFromSessionId(sessionId),
  };
}

function liveSessionId(payload: LiveSessionIdentityPayload): string {
  return normalizeLiveSessionIdentity(payload).sessionId;
}

function liveChannel(payload: LiveSessionIdentityPayload, sessionId?: string): string {
  const identity = normalizeLiveSessionIdentity(payload);
  const resolvedSessionId = sessionId ?? identity.sessionId;
  if (resolvedSessionId === identity.sessionId) {
    return identity.channel;
  }
  return textField(payload.channel || channelFromSessionId(resolvedSessionId) || "web") || "web";
}

function liveTransportExternalChatId(payload: LiveSessionIdentityPayload, sessionId?: string): string {
  const identity = normalizeLiveSessionIdentity(payload);
  const resolvedSessionId = sessionId ?? identity.sessionId;
  if (resolvedSessionId === identity.sessionId) {
    return identity.transportExternalChatId;
  }
  return textField(payload.external_chat_id || payload.externalChatId)
    || externalChatIdFromSessionId(resolvedSessionId);
}

const STORAGE_KEYS = {
  wsUrl: "opensprite:web:wsUrl",
  accessToken: "opensprite:web:accessToken",
  displayName: "opensprite:web:displayName",
  activeExternalChatId: "opensprite:web:activeExternalChatId",
  showRunHistory: "opensprite:web:showRunHistory",
  showRunTimeline: "opensprite:web:showRunTimeline",
  showRunSummary: "opensprite:web:showRunSummary",
  showRunTrace: "opensprite:web:showRunTrace",
  showHiddenSessions: "opensprite:web:showHiddenSessions",
  language: "opensprite:web:language",
  colorScheme: "opensprite:web:colorScheme",
  sidebarCollapsed: "opensprite:web:sidebarCollapsed",
  traceInspectorCollapsed: "opensprite:web:traceInspectorCollapsed",
  overlayProfileId: "opensprite:web:overlayProfileId",
  localDraftSessions: "opensprite:web:localDraftSessions",
};

const LANGUAGE_ATTRIBUTES: Record<LanguagePreference, string> = {
  "zh-TW": "zh-Hant-TW",
  en: "en",
};

const MAX_RUN_EVENTS = 80;
const MAX_RUN_ARTIFACTS = 200;
const MAX_TIMELINE_EVENTS = 8;
const RUN_HISTORY_LIMIT = 10;
const RUN_SUMMARY_FETCH_DELAY_MS = 500;
const RUN_SUMMARY_NOT_FOUND_RETRY_DELAY_MS = 1200;
const RUN_SUMMARY_NOT_FOUND_RETRY_LIMIT = 3;
const RUN_BACKFILL_COOLDOWN_MS = 2000;
const GATEWAY_RECONNECT_DELAY_MS = 30000;
const SESSION_HISTORY_REFRESH_INTERVAL_MS = 30000;
const LOCAL_DRAFT_SESSION_LIMIT = 10;
const DELETED_SESSION_TOMBSTONE_MS = 5 * 60 * 1000;
const TERMINAL_PART_STATES = ["completed", "failed", "cancelled", "error"] as const;
type TerminalPartState = (typeof TERMINAL_PART_STATES)[number];
const TERMINAL_PART_STATE_SET: ReadonlySet<string> = new Set<string>(TERMINAL_PART_STATES);

function isTerminalPartState(state: string): state is TerminalPartState {
  return TERMINAL_PART_STATE_SET.has(state);
}

const TIMELINE_EVENT_TYPES = [
  "run_started",
  "llm_status",
  "tool_started",
  "file_changed",
  "verification_started",
  "verification_result",
  "subagent.started",
  "subagent.group.started",
  "subagent.group.completed",
  "subagent.group.failed",
  "subagent.group.cancelled",
  "subagent.completed",
  "subagent.failed",
  "subagent.cancelled",
  "workflow.started",
  "workflow.step.started",
  "workflow.step.completed",
  "workflow.step.failed",
  "workflow.completed",
  "workflow.failed",
  "execution.stopped",
  "background_process.started",
  "background_process.completed",
  "background_process.lost",
  "run_finished",
  "run_failed",
  "run_cancelled",
  "run_cancel_requested",
] as const;
type TimelineEventType = (typeof TIMELINE_EVENT_TYPES)[number];
const TIMELINE_EVENT_TYPE_SET: ReadonlySet<string> = new Set<string>(TIMELINE_EVENT_TYPES);

function isTimelineEventType(eventType: string): eventType is TimelineEventType {
  return TIMELINE_EVENT_TYPE_SET.has(eventType);
}

function normalizeTimelineEventType(eventType: string): TimelineEventType | null {
  return isTimelineEventType(eventType) ? eventType : null;
}

function resolveDefaultWsUrl(): string {
  if (window.location.protocol === "http:" || window.location.protocol === "https:") {
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${wsProtocol}//${window.location.host}/ws`;
  }
  return "ws://127.0.0.1:8765/ws";
}

const DEFAULT_WS_URL = resolveDefaultWsUrl();

function runAfterCurrentMicrotask(callback: () => void): void {
  void Promise.resolve().then(callback);
}

function normalizeCommandCatalog(payload: CommandCatalogPayload | null): CommandCatalogItem[] {
  const commands = Array.isArray(payload?.commands) ? payload.commands : [];
  return commands.map((item) => {
    const commandItem = toCommandCatalogItemPayload(item);
    if (!commandItem || !commandItem.name || !commandItem.command.startsWith("/")) {
      return null;
    }
    return commandItem;
  }).filter((item): item is CommandCatalogItem => Boolean(item));
}

function buildRunCancelUrl(wsUrl: string, runId: string, sessionId: string): string {
  const url = buildHttpApiUrl(wsUrl, `/api/runs/${encodeURIComponent(runId)}/cancel`);
  url.searchParams.set("session_id", sessionId);
  return url.toString();
}

function getActiveRun(session: ChatSession | null | undefined): RunViewState | null {
  if (!session?.runs?.length) {
    return null;
  }
  return session.runs.find((run) => run.runId === session.activeRunId) || session.runs[0];
}

function shouldLoadRunSummary({ showRunSummary }: { showRunSummary: boolean }, run: RunViewState | null | undefined): boolean {
  return Boolean(
    showRunSummary
    && run
    && isTerminalRunStatus(run.status)
    && !run.summary
    && !run.summaryLoading
    && !run.summaryError
    && coerceNonNegativeInteger(run.summaryNotFoundAttempts) < RUN_SUMMARY_NOT_FOUND_RETRY_LIMIT,
  );
}

function shouldLoadRunTrace(run: RunViewState | null | undefined): boolean {
  if (!run || run.traceLoading) {
    return false;
  }
  const summaryFileChanges = normalizeRunSummaryFileChanges(run.summary);
  const hasNeededFileChanges = (run.fileChanges || []).length > 0 || !summaryFileChanges.length;
  return !(run.traceLoaded && hasNeededFileChanges);
}

function describeRunEvent(eventType: string, payload: RunTimelinePayload, copy: DisplayCopy): RunEventDescription | null {
  if (!normalizeTimelineEventType(eventType)) {
    return null;
  }
  const eventDetail = normalizeRunEventPayload(payload);
  const lifecyclePayload = payload;

  if (eventType === "run_started") {
    return { label: copy.run.runStarted, detail: copy.run.preparingRequest, tone: "running" };
  }

  if (eventType === "llm_status") {
    const message = eventDetail.message || copy.run.thinking;
    return {
      label: message === "processing" ? copy.run.thinking : copy.run.llmStatus,
      detail: message === "processing" ? copy.run.preparingPrompt : message,
      tone: "running",
    };
  }

  if (eventType === "tool_started") {
    if (eventDetail.toolName === "verify") {
      return null;
    }
    return {
      label: `${copy.run.tool}: ${eventDetail.toolName || copy.run.unknownTool}`,
      detail: eventDetail.argsPreview || copy.run.executingTool,
      tone: "running",
    };
  }

  if (eventType === "verification_started") {
    return {
      label: `${copy.run.verifying}: ${eventDetail.action || copy.run.auto}`,
      detail: eventDetail.path ? `${copy.run.pathPrefix} ${eventDetail.path}` : copy.run.runningChecks,
      tone: "running",
    };
  }

  if (eventType === "verification_result") {
    return {
      label: eventDetail.verificationOk ? copy.run.verificationPassed : copy.run.verificationFailed,
      detail: eventDetail.resultPreview || copy.run.verificationCompleted,
      tone: eventDetail.verificationOk ? "success" : "error",
    };
  }

  if (eventType === "file_changed") {
    return {
      label: `${copy.run.fileChanged || "File changed"}: ${eventDetail.path || "?"}`,
      detail: eventDetail.diffPreview,
      tone: "running",
    };
  }

  if (eventType === "tool_input_delta") {
    return {
      label: `${copy.trace.filters.tool}: ${eventDetail.toolName || copy.run.unknownTool}`,
      detail: eventDetail.inputDelta,
      tone: "running",
    };
  }

  if (eventType === "reasoning_delta") {
    return {
      label: copy.trace.filters.llm,
      detail: eventDetail.contentDelta,
      tone: "running",
    };
  }

  if (eventType === "subagent.group.started") {
    const detail = normalizeSubagentDetail(lifecyclePayload);
    return {
      label: copy.run.parallelDelegationStarted,
      detail: formatSubagentGroupDetail(detail),
      tone: "running",
    };
  }

  if (eventType === "subagent.group.completed") {
    const detail = normalizeSubagentDetail(lifecyclePayload);
    return {
      label: copy.run.parallelDelegationCompleted,
      detail: formatSubagentGroupDetail(detail),
      tone: "success",
    };
  }

  if (eventType === "subagent.group.failed") {
    const detail = normalizeSubagentDetail(lifecyclePayload);
    return {
      label: copy.run.parallelDelegationFailed,
      detail: formatSubagentGroupDetail(detail),
      tone: "error",
    };
  }

  if (eventType === "subagent.group.cancelled") {
    const detail = normalizeSubagentDetail(lifecyclePayload);
    return {
      label: copy.run.parallelDelegationCancelled,
      detail: formatSubagentGroupDetail(detail),
      tone: "warning",
    };
  }

  if (eventType === "subagent.started") {
    const detail = normalizeSubagentDetail(lifecyclePayload);
    return {
      label: copy.run.subagentStarted,
      detail: detail.message || formatSubagentDetail(detail),
      tone: "running",
    };
  }

  if (eventType === "subagent.completed") {
    const detail = normalizeSubagentDetail(lifecyclePayload);
    return {
      label: copy.run.subagentCompleted,
      detail: detail.summary || formatSubagentDetail(detail),
      tone: "success",
    };
  }

  if (eventType === "subagent.failed") {
    const detail = normalizeSubagentDetail(lifecyclePayload);
    return {
      label: copy.run.subagentFailed,
      detail: detail.error || formatSubagentDetail(detail),
      tone: "error",
    };
  }

  if (eventType === "subagent.cancelled") {
    const detail = normalizeSubagentDetail(lifecyclePayload);
    return {
      label: copy.run.cancelled,
      detail: detail.error || formatSubagentDetail(detail),
      tone: "warning",
    };
  }

  if (eventType === "workflow.started") {
    const detail = normalizeWorkflowDetail(lifecyclePayload);
    return {
      label: copy.run.workflowStarted,
      detail: formatWorkflowDetail(detail),
      tone: "running",
    };
  }

  if (eventType === "workflow.step.started") {
    const detail = normalizeWorkflowDetail(lifecyclePayload);
    return {
      label: copy.run.workflowStepStarted,
      detail: formatWorkflowStepDetail(detail),
      tone: "running",
    };
  }

  if (eventType === "workflow.step.completed") {
    const detail = normalizeWorkflowDetail(lifecyclePayload);
    return {
      label: copy.run.workflowStepCompleted,
      detail: formatWorkflowStepDetail(detail),
      tone: "success",
    };
  }

  if (eventType === "workflow.step.failed") {
    const detail = normalizeWorkflowDetail(lifecyclePayload);
    return {
      label: copy.run.workflowStepFailed,
      detail: formatWorkflowStepDetail(detail),
      tone: "error",
    };
  }

  if (eventType === "workflow.completed") {
    const detail = normalizeWorkflowDetail(lifecyclePayload);
    return {
      label: copy.run.workflowCompleted,
      detail: formatWorkflowDetail(detail),
      tone: "success",
    };
  }

  if (eventType === "workflow.failed") {
    const detail = normalizeWorkflowDetail(lifecyclePayload);
    return {
      label: copy.run.workflowFailed,
      detail: formatWorkflowDetail(detail),
      tone: "error",
    };
  }

  if (eventType === "execution.stopped") {
    return {
      label: copy.run.statusLabels.stopped || copy.run.stopped,
      detail: eventDetail.message || eventDetail.error || copy.run.stopped,
      tone: "warning",
    };
  }

  if (eventType === "background_process.started") {
    return {
      label: copy.run.backgroundProcessStarted || "Background process started",
      detail: eventDetail.command || eventDetail.processSessionId,
      tone: "running",
    };
  }

  if (eventType === "background_process.completed") {
    return {
      label: eventDetail.backgroundSucceeded
        ? (copy.run.backgroundProcessCompleted || "Background process completed")
        : (copy.run.backgroundProcessFailed || "Background process failed"),
      detail: [
        eventDetail.command,
        eventDetail.backgroundExitCodeText ? `exit ${eventDetail.backgroundExitCodeText}` : "",
      ].filter(Boolean).join(" · "),
      tone: eventDetail.backgroundSucceeded ? "success" : "error",
    };
  }

  if (eventType === "background_process.lost") {
    return {
      label: copy.run.backgroundProcessLost || "Background process lost",
      detail: eventDetail.command || eventDetail.processSessionId || "runtime restart",
      tone: "warning",
    };
  }

  if (eventType === "run_finished") {
    if (eventDetail.status === "stopped") {
      return {
        label: copy.run.statusLabels.stopped || copy.run.stopped,
        detail: eventDetail.message || eventDetail.error || copy.run.stopped,
        tone: "warning",
      };
    }
    if (eventDetail.status === "failed") {
      return {
        label: copy.run.failed,
        detail: eventDetail.error || copy.run.failed,
        tone: "error",
      };
    }
    if (eventDetail.status === "cancelled") {
      return {
        label: copy.run.cancelled,
        detail: eventDetail.error || copy.run.cancelled,
        tone: "warning",
      };
    }
    const detail = normalizeRunFinishDetail(lifecyclePayload);
    return {
      label: eventDetail.hadToolError ? copy.run.completedWithWarnings : copy.run.completed,
      detail: formatRunFinishDetail(detail, copy) || copy.run.finalDelivered,
      tone: eventDetail.hadToolError ? "warning" : "success",
    };
  }

  if (eventType === "run_failed") {
    const cancelled = eventDetail.status === "cancelled";
    return {
      label: cancelled ? copy.run.cancelled : copy.run.failed,
      detail: eventDetail.error || (cancelled ? copy.run.cancelled : copy.run.failed),
      tone: cancelled ? "warning" : "error",
    };
  }

  if (eventType === "run_cancelled") {
    return {
      label: copy.run.cancelled,
      detail: eventDetail.error || copy.run.cancelled,
      tone: "warning",
    };
  }

  if (eventType === "run_cancel_requested") {
    return {
      label: copy.trace.cancelling,
      detail: eventDetail.status,
      tone: "warning",
    };
  }

  return null;
}

export function formatEventTime(timestamp: string | number | Date): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return "--:--";
  }
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  const seconds = String(date.getSeconds()).padStart(2, "0");
  return `${hours}:${minutes}:${seconds}`;
}

function formatReconnectNotice(notice: ReconnectNotice, delayMs: number): string {
  if (typeof notice === "function") {
    return notice(Math.max(1, Math.round(delayMs / 1000)));
  }
  return notice;
}

export function useChatClient() {
  const MESSAGE_STAGE_BOTTOM_THRESHOLD = 12;
  const storedExternalChatId = readStoredValue(STORAGE_KEYS.activeExternalChatId, "");
  const storedOverlayProfileId = readStoredValue(STORAGE_KEYS.overlayProfileId, "");
  const initialLanguage = readStoredChoice(STORAGE_KEYS.language, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES);
  const initialColorScheme = readStoredChoice(STORAGE_KEYS.colorScheme, DEFAULT_COLOR_SCHEME, SUPPORTED_COLOR_SCHEMES);
  const initialCopy = getDisplayCopy(initialLanguage);
  const initialSession = createSession(
    isExternalChannelSessionId(storedExternalChatId) ? generateExternalChatId() : storedExternalChatId || generateExternalChatId(),
  );
  const storedDraftSessions = readStoredDraftSessions(
    STORAGE_KEYS.localDraftSessions,
    normalizeEventTimestamp,
  );
  const initialSessionMatchesStoredDraft = storedDraftSessions.some((session) => session.externalChatId === initialSession.externalChatId);
  const initialSessionFromStoredExternalChatId = Boolean(storedExternalChatId && !isExternalChannelSessionId(storedExternalChatId))
    && !initialSessionMatchesStoredDraft;
  const initialSessionExternalChatId = initialSession.externalChatId;
  const initialDraftSessions = storedDraftSessions
    .filter((session) => session.externalChatId !== initialSession.externalChatId);
  const localDraftExternalChatIds = new Set(initialDraftSessions.map((session) => session.externalChatId));
  if (initialSessionMatchesStoredDraft) {
    localDraftExternalChatIds.add(initialSession.externalChatId);
  }

  const initialNotice: NoticeState = {
    text: initialCopy.notices.connectingGateway,
    tone: "info",
  };

  const state = reactive<ChatClientState>({
    wsUrl: readStoredValue(STORAGE_KEYS.wsUrl, DEFAULT_WS_URL),
    accessToken: readStoredValue(STORAGE_KEYS.accessToken, ""),
    displayName: readStoredValue(STORAGE_KEYS.displayName, "Local browser"),
    showRunHistory: readStoredBoolean(STORAGE_KEYS.showRunHistory, true),
    showRunTimeline: readStoredBoolean(STORAGE_KEYS.showRunTimeline, true),
    showRunSummary: readStoredBoolean(STORAGE_KEYS.showRunSummary, true),
    showRunTrace: readStoredBoolean(STORAGE_KEYS.showRunTrace, true),
    language: initialLanguage,
    colorScheme: initialColorScheme,
    activeExternalChatId: initialSession.externalChatId,
    sessions: [initialSession, ...initialDraftSessions],
    connectionState: "disconnected",
    authRequired: false,
    authError: "",
    notice: initialNotice,
    commandCatalog: {
      commands: [],
      loading: false,
      error: "",
    },
    sessionHistory: {
      total: 0,
      limit: 0,
      channelTotals: {},
    },
  });

  const overlayProfileId = ref(storedOverlayProfileId || generateOverlayProfileId());
  writeStoredValue(STORAGE_KEYS.overlayProfileId, overlayProfileId.value);

  const copy = computed(() => getDisplayCopy(state.language));
  const prompts = computed(() => copy.value.prompts);

  const messageText = ref("");
  let messageInput: HTMLTextAreaElement | null = null;
  let messageStage: HTMLElement | null = null;
  let messageStagePinnedToBottom = true;
  const toasts = ref<ToastNotice[]>([]);
  const sidebarOpen = ref(false);
  const sidebarCollapsed = ref(readStoredBoolean(STORAGE_KEYS.sidebarCollapsed, false));
  const traceInspectorCollapsed = ref(readStoredBoolean(STORAGE_KEYS.traceInspectorCollapsed, true));
  const sessionChannelFilter = ref<SessionChannelFilter>("all");
  const showHiddenSessions = ref(readStoredBoolean(STORAGE_KEYS.showHiddenSessions, false));
  const settingsOpen = ref(false);
  const settingsSection = ref<SettingsSectionId>("general");
  const settingsForm = reactive(createSettingsForm(state));
  const settingsState = reactive(createSettingsState());

  let activeSocket: WebSocket | null = null;
  let colorSchemeMediaQuery: MediaQueryList | null = null;
  let clientDisposed = false;
  let autoReconnectEnabled = true;
  let gatewayReconnectTimer: number | null = null;
  let sessionHistoryRefreshTimer: number | null = null;
  let sessionHistoryRefreshPromise: Promise<void> | null = null;
  let resolveSessionHistoryRefresh: (() => void) | null = null;
  let boundMessageStage: HTMLElement | null = null;
  const runSummaryTimers = new Map<string, number>();
  const runBackfillTimes = new Map<string, number>();
  const sessionLiveRevisions = new WeakMap<ChatSession, number>();
  const sessionSnapshotFences = new WeakMap<ChatSession, SessionSnapshotFence>();
  const sessionHistoryRefreshQueue = createSessionHistoryRefreshQueue();
  const runSummaryRequestGenerations = new WeakMap<RunViewState, number>();
  const runTraceRequestGenerations = new WeakMap<RunViewState, number>();
  let toastId = 0;
  const toastTimers = new Map<string, number>();
  const deletedSessionTombstones = new Map<string, number>();

  function applyDocumentPreferences(): void {
    if (typeof document === "undefined") {
      return;
    }
    document.documentElement.lang = LANGUAGE_ATTRIBUTES[state.language] || LANGUAGE_ATTRIBUTES[DEFAULT_LANGUAGE];
    document.documentElement.dataset.colorScheme = getResolvedColorScheme(state.colorScheme);
    document.documentElement.dataset.colorSchemePreference = state.colorScheme;
  }

  function handleSystemColorSchemeChange(): void {
    if (state.colorScheme === "system") {
      applyDocumentPreferences();
    }
  }

  function addColorSchemeListener(): void {
    if (typeof window === "undefined" || !window.matchMedia) {
      return;
    }
    colorSchemeMediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    if (colorSchemeMediaQuery.addEventListener) {
      colorSchemeMediaQuery.addEventListener("change", handleSystemColorSchemeChange);
      return;
    }
    colorSchemeMediaQuery.addListener?.(handleSystemColorSchemeChange);
  }

  function removeColorSchemeListener(): void {
    if (!colorSchemeMediaQuery) {
      return;
    }
    if (colorSchemeMediaQuery.removeEventListener) {
      colorSchemeMediaQuery.removeEventListener("change", handleSystemColorSchemeChange);
    } else {
      colorSchemeMediaQuery.removeListener?.(handleSystemColorSchemeChange);
    }
    colorSchemeMediaQuery = null;
  }

  const currentSession = computed(() => {
    return state.sessions.find((session) => session.externalChatId === state.activeExternalChatId) || null;
  });

  const sidebarSessions = computed(() => {
    const visibleSessions = showHiddenSessions.value
      ? state.sessions
      : state.sessions.filter((session) => !session.hiddenFromBrowserHistory);
    if (sessionChannelFilter.value === "web") {
      return visibleSessions.filter((session) => !session.channel || session.channel === "web");
    }
    return visibleSessions;
  });

  const sidebarSessionTotal = computed(() => {
    const key = sessionChannelFilter.value === "web" ? "web" : "all";
    const total = state.sessionHistory.channelTotals[key] ?? state.sessionHistory.total;
    if (total > 0) {
      return Math.max(sidebarSessions.value.length, total);
    }
    return sidebarSessions.value.length;
  });

  const webSessionCount = computed(() => state.sessions.filter((session) => !session.channel || session.channel === "web").length);

  const currentMessages = computed(() => currentSession.value?.messages || []);

  const currentEntries = computed(() => currentSession.value?.entries || []);

  const currentRuns = computed(() => currentSession.value?.runs || []);

  const currentRunsLoading = computed(() => Boolean(currentSession.value?.runsLoading));

  const currentRunsError = computed(() => currentSession.value?.runsError || "");

  const currentRun = computed(() => {
    return getActiveRun(currentSession.value);
  });

  const currentRunTimeline = computed(() => {
    const events = currentRun.value?.events || [];
    return events.slice(-MAX_TIMELINE_EVENTS);
  });

  const currentRunSummary = computed<CurrentRunSummaryView | null>(() => {
    const run = currentRun.value;
    const latestEvent = currentRunTimeline.value.at(-1);
    if (!run || !latestEvent) {
      return null;
    }
    return {
      shortId: shortRunId(run.runId),
      statusLabel: runStatusLabel(run.status, copy.value),
      title: String(latestEvent.label || ""),
      tone: runTone(run.status, latestEvent.tone),
    };
  });

  const settingsTitle = computed(() => copy.value.settingsTitles[settingsSection.value] || copy.value.settingsTitles.general);

  const sessionMeta = computed(() => {
    const session = currentSession.value;
    return `${getSessionTitle(session)} · ${getSessionDisplayId(session)} · ${sessionStatusLabel(session, copy.value)}`;
  });

  const runtimeHint = computed(() => currentSession.value?.externalChatId || copy.value.session.noActiveChat);

  const composerHint = computed(() => {
    const session = currentSession.value;
    if (session?.channel && session.channel !== "web") {
      return copy.value.composer.readOnlyChannel(session.channel);
    }
    return runtimeHint.value;
  });

  const commandHints = computed(() => {
    const raw = messageText.value.trimStart();
    if (!raw.startsWith("/")) {
      return [];
    }
    const token = raw.split(/\s+/, 1)[0];
    if (raw.length > token.length) {
      return [];
    }
    const query = token.toLowerCase();
    if (query.includes("@")) {
      return [];
    }
    const commands = state.commandCatalog.commands || [];
    return commands
      .filter((command) => command.command.toLowerCase().startsWith(query))
      .slice(0, 6);
  });

  const currentSessionReadOnly = computed(() => {
    const session = currentSession.value;
    return Boolean(session && session.channel !== "web");
  });

  const sendDisabled = computed(() => state.connectionState !== "connected" || currentSessionReadOnly.value);

  function setMessageInputRef(element: HTMLTextAreaElement | null): void {
    messageInput = element;
  }

  function isMessageStageNearBottom(stage: HTMLElement | null | undefined): boolean {
    if (!stage) {
      return true;
    }
    const distanceFromBottom = stage.scrollHeight - stage.scrollTop - stage.clientHeight;
    return distanceFromBottom <= MESSAGE_STAGE_BOTTOM_THRESHOLD;
  }

  function updateMessageStagePinnedState(stage: HTMLElement | null = messageStage): void {
    messageStagePinnedToBottom = isMessageStageNearBottom(stage);
  }

  function handleMessageStageScroll(event: Event): void {
    const stage = event.currentTarget instanceof HTMLElement ? event.currentTarget : messageStage;
    updateMessageStagePinnedState(stage);
  }

  function detachMessageStageScrollListener(element: HTMLElement | null): void {
    if (!element) {
      return;
    }
    element.removeEventListener("scroll", handleMessageStageScroll);
    if (boundMessageStage === element) {
      boundMessageStage = null;
    }
  }

  function attachMessageStageScrollListener(element: HTMLElement | null): void {
    if (!element) {
      return;
    }
    if (boundMessageStage && boundMessageStage !== element) {
      detachMessageStageScrollListener(boundMessageStage);
    }
    if (boundMessageStage !== element) {
      element.addEventListener("scroll", handleMessageStageScroll, { passive: true });
      boundMessageStage = element;
    }
    updateMessageStagePinnedState(element);
  }

  function setMessageStageRef(element: HTMLElement | null): void {
    if (messageStage && messageStage !== element) {
      detachMessageStageScrollListener(messageStage);
    }
    messageStage = element;
    if (element) {
      attachMessageStageScrollListener(element);
      scrollMessagesToBottom({ force: true });
    } else {
      messageStagePinnedToBottom = true;
    }
  }

  function setMessageText(value: string): void {
    messageText.value = value;
  }

  function saveRunPanelVisibilitySettings(
    showRunHistory: boolean,
    showRunTimeline: boolean,
    showRunSummary: boolean,
    showRunTrace: boolean,
  ): void {
    state.showRunHistory = Boolean(showRunHistory);
    state.showRunTimeline = Boolean(showRunTimeline);
    state.showRunSummary = Boolean(showRunSummary);
    state.showRunTrace = Boolean(showRunTrace);
    writeStoredValue(STORAGE_KEYS.showRunHistory, String(state.showRunHistory));
    writeStoredValue(STORAGE_KEYS.showRunTimeline, String(state.showRunTimeline));
    writeStoredValue(STORAGE_KEYS.showRunSummary, String(state.showRunSummary));
    writeStoredValue(STORAGE_KEYS.showRunTrace, String(state.showRunTrace));
    if (state.showRunSummary) {
      maybeLoadRunSummaryForSession(currentSession.value);
    } else {
      clearAllRunSummaryTimers();
      for (const session of state.sessions) {
        for (const run of session.runs || []) {
          run.summaryLoading = false;
        }
      }
    }
  }

  function clearAllRunSummaryTimers(): void {
    for (const timer of runSummaryTimers.values()) {
      clearTimeout(timer);
    }
    runSummaryTimers.clear();
  }

  function saveDisplaySettings(language: LanguagePreference, colorScheme: ColorSchemePreference): void {
    state.language = normalizeChoice(language, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES);
    state.colorScheme = normalizeChoice(colorScheme, DEFAULT_COLOR_SCHEME, SUPPORTED_COLOR_SCHEMES);
    writeStoredValue(STORAGE_KEYS.language, state.language);
    writeStoredValue(STORAGE_KEYS.colorScheme, state.colorScheme);
    applyDocumentPreferences();
  }

  function rebuildLocalizedRunEvents(): void {
    for (const session of state.sessions) {
      for (const run of session.runs || []) {
        run.events = (run.rawEvents || [])
          .map(normalizeLocalizedRawRunEvent)
          .filter((event): event is RunTimelineEventView => Boolean(event))
          .slice(-MAX_RUN_EVENTS);
      }
    }
  }

  watch(settingsOpen, (isOpen) => {
    document.body.classList.toggle("settings-open", isOpen);
  });

  watch(
    () => state.activeExternalChatId,
    () => {
      if (settingsOpen.value && settingsSection.value === "schedule") {
        loadCronJobs();
      }
    },
  );

  watch(
    () => [currentSession.value?.externalChatId, currentSession.value?.sessionId],
    () => {
      void loadCurrentSessionRuns();
      scrollMessagesToBottom({ force: true });
    },
    { immediate: true },
  );

  watch(
    () => [currentEntries.value.length, currentMessages.value.length],
    () => {
      scrollMessagesToBottom();
    },
  );

  watch(
    () => [currentSession.value?.externalChatId, currentRun.value?.runId, currentRun.value?.status],
    () => {
      maybeLoadRunSummaryForSession(currentSession.value);
      maybeLoadRunTraceForSession(currentSession.value);
    },
    { immediate: true },
  );

  watch(sidebarOpen, (isOpen) => {
    document.body.classList.toggle("sidebar-open", isOpen);
  });

  watch(
    () => [
      settingsForm.showRunHistory,
      settingsForm.showRunTimeline,
      settingsForm.showRunSummary,
      settingsForm.showRunTrace,
    ],
    ([showRunHistory, showRunTimeline, showRunSummary, showRunTrace]) => {
      saveRunPanelVisibilitySettings(showRunHistory, showRunTimeline, showRunSummary, showRunTrace);
    },
  );

  watch(
    () => [settingsForm.language, settingsForm.colorScheme] as const,
    ([language, colorScheme]) => {
      saveDisplaySettings(language, colorScheme);
    },
  );

  watch(
    () => [state.language, state.colorScheme],
    ([language], previousValues) => {
      const [previousLanguage] = previousValues || [];
      applyDocumentPreferences();
      if (previousLanguage && language !== previousLanguage) {
        rebuildLocalizedRunEvents();
      }
    },
    { immediate: true },
  );

  function sortSessions(): void {
    state.sessions.sort((left, right) => right.updatedAt - left.updatedAt);
  }

  function sessionLiveRevision(session: ChatSession): number {
    return sessionLiveRevisions.get(session) || 0;
  }

  function markSessionLiveMutation(session: ChatSession): void {
    sessionLiveRevisions.set(session, sessionLiveRevision(session) + 1);
  }

  function captureSessionRevisionWatermark(): Map<string, number> {
    return new Map(state.sessions.map((session) => [session.externalChatId, sessionLiveRevision(session)]));
  }

  function snapshotFenceForSession(session: ChatSession): SessionSnapshotFence {
    const existing = sessionSnapshotFences.get(session);
    if (existing) {
      return existing;
    }
    const created = createSessionSnapshotFence();
    sessionSnapshotFences.set(session, created);
    return created;
  }

  function getSessionDisplayId(session: ChatSession | null | undefined): string {
    if (!session) {
      return copy.value.session.noActiveChat;
    }
    if (session.channel && session.channel !== "web") {
      return session.sessionId || `${session.channel}:${session.transportExternalChatId || session.externalChatId}`;
    }
    return session.sessionId || session.externalChatId;
  }

  function getSessionApiId(session: ChatSession | null | undefined): string {
    return session?.sessionId || "";
  }

  function getSessionOwnerId(session: ChatSession | null | undefined): string {
    if (!session) {
      return "";
    }
    if (session.sessionId) {
      return session.sessionId;
    }
    if (session.channel && session.channel !== "web") {
      return "";
    }
    return session.externalChatId ? `web:${session.externalChatId}` : "";
  }

  function persistLocalDraftSessions(): void {
    writeStoredDraftSessions(state.sessions, STORAGE_KEYS.localDraftSessions, LOCAL_DRAFT_SESSION_LIMIT);
    localDraftExternalChatIds.clear();
    for (const session of state.sessions) {
      if (isLocalDraftSession(session)) {
        localDraftExternalChatIds.add(session.externalChatId);
      }
    }
  }

  function getSessionTitle(session: ChatSession | null | undefined): string {
    if (!session || session.title === "New chat") {
      return copy.value.session.newChat;
    }
    return session.title;
  }

  function ensureSession(externalChatId: string | null | undefined, sessionId = "", options: EnsureSessionOptions = {}): ChatSession | null {
    const allowDeleted = Boolean(options?.allowDeleted);
    const resolvedExternalChatId = externalChatId || generateExternalChatId();
    const normalizedSessionId = String(sessionId || "").trim();
    if (!allowDeleted && isDeletedSessionIdentity({
      externalChatId: resolvedExternalChatId,
      sessionId: normalizedSessionId,
      transportExternalChatId: resolvedExternalChatId,
    })) {
      return null;
    }
    let session = state.sessions.find((entry) => entry.externalChatId === resolvedExternalChatId);
    if (!allowDeleted && session && isDeletedSessionTombstoned(session)) {
      return null;
    }
    if (!session) {
      session = createSession(resolvedExternalChatId);
      session.messages = [
        makeMessage(
          "assistant",
          copy.value.session.liveGatewayThread,
          "OpenSprite",
        ),
      ];
      state.sessions.unshift(session);
    }
    if (normalizedSessionId) {
      session.sessionId = normalizedSessionId;
      session.channel = channelFromSessionId(normalizedSessionId);
    }
    session.transportExternalChatId = resolvedExternalChatId;
    session.updatedAt = Date.now();
    return session;
  }

  function applySessionStatus(payload: LiveSessionStatusPayload): void {
    const identity = normalizeLiveSessionIdentity(payload);
    const { sessionId, channel } = identity;
    if (!sessionId) {
      return;
    }
    const transportExternalChatId = identity.transportExternalChatId || generateExternalChatId();
    const externalChatId = channel === "web" ? transportExternalChatId : sessionId;
    if (!shouldAcceptLivePayload(payload, externalChatId)) {
      return;
    }
    const session = ensureSession(externalChatId, sessionId);
    if (!session) {
      return;
    }
    session.channel = channel;
    session.transportExternalChatId = transportExternalChatId;
    const nextStatus = normalizeLiveSessionStatus(payload);
    if (nextStatus.updatedAt >= Number(session.status.updatedAt || 0)) {
      session.status = nextStatus;
    }
    if (nextStatus.status !== "idle") {
      session.updatedAt = Math.max(Number(session.updatedAt || 0), nextStatus.updatedAt);
      sortSessions();
    }
    markSessionLiveMutation(session);
    persistLocalDraftSessions();
  }

  function viewExternalChatIdForPayload(payload: LiveSessionIdentityPayload): string {
    const {
      sessionId,
      channel,
      transportExternalChatId: normalizedTransportExternalChatId,
    } = normalizeLiveSessionIdentity(payload);
    const transportExternalChatId = normalizedTransportExternalChatId || generateExternalChatId();
    return channel === "web" ? transportExternalChatId : (sessionId || `${channel}:${transportExternalChatId}`);
  }

  function hasKnownSession(externalChatId: string, sessionId = ""): boolean {
    return state.sessions.some((session) => {
      return (externalChatId && session.externalChatId === externalChatId)
        || (sessionId && session.sessionId === sessionId);
    });
  }

  function shouldAcceptLivePayload(payload: LiveSessionIdentityPayload, externalChatId = ""): boolean {
    const { sessionId, channel, transportExternalChatId } = normalizeLiveSessionIdentity(payload);
    const resolvedExternalChatId = externalChatId
      || transportExternalChatId
      || externalChatIdFromSessionId(sessionId)
      || "";
    if (isDeletedSessionIdentity({
      externalChatId: resolvedExternalChatId,
      sessionId,
      transportExternalChatId,
    })) {
      return false;
    }
    if (channel !== "web") {
      return true;
    }
    return hasKnownSession(resolvedExternalChatId, sessionId);
  }

  function addMessage(externalChatId: string, message: ChatMessage): ChatSession | null {
    const session = ensureSession(externalChatId);
    if (!session) {
      return null;
    }
    session.messages.push(message);
    if (session.entries.length) {
      session.entries.push(makeLiveEntry(message));
    }
    session.updatedAt = Math.max(Number(session.updatedAt || 0), message.createdAt);
    if (message.role === "user" && session.title === "New chat") {
      session.title = summarizeTitle(message.text);
    }
    markSessionLiveMutation(session);
    sortSessions();
    persistLocalDraftSessions();
    return session;
  }

  function findOrCreateRun(session: ChatSession, runId: string, createdAt: number): RunViewState {
    let run = session.runs.find((entry) => entry.runId === runId);
    if (!run) {
      run = createRunViewState({
        runId,
        sessionId: session.sessionId || "",
        createdAt,
      });
      session.runs.unshift(run);
    }
    run.sessionId = run.sessionId || session.sessionId || "";
    session.activeRunId = runId;
    return run;
  }

  function upsertRunArtifact(run: RunViewState, artifact: unknown): RunArtifactView | null {
    const normalized = normalizeRunArtifact(artifact);
    if (!normalized) {
      return null;
    }
    const artifacts: RunArtifactView[] = run.artifacts || [];
    const existingIndex = artifacts.findIndex((entry) => entry.artifactId === normalized.artifactId);
    if (existingIndex >= 0) {
      artifacts[existingIndex] = { ...artifacts[existingIndex], ...normalized };
    } else {
      artifacts.push(normalized);
    }
    artifacts.sort((left, right) => Number(left.createdAt || 0) - Number(right.createdAt || 0));
    if (artifacts.length > MAX_RUN_ARTIFACTS) {
      artifacts.splice(0, artifacts.length - MAX_RUN_ARTIFACTS);
    }
    run.artifacts = artifacts;
    return normalized;
  }

  function applyToolArtifactToParts(run: RunViewState, artifact: RunArtifactView | null | undefined): void {
    const artifactToolCallId = String(artifact?.toolCallId || "").trim();
    const artifactStatus = String(artifact?.status || "").trim();
    if (!artifact || artifact.kind !== "tool" || !artifactToolCallId || !isTerminalPartState(artifactStatus)) {
      return;
    }
    run.parts = (run.parts || []).map((part) => {
      const metadata = normalizeTracePartMetadata(part.metadata);
      const partArtifact = part.artifact;
      const toolCallId = String(metadata.tool_call_id || metadata.toolCallId || partArtifact?.toolCallId || "").trim();
      if (String(part.partType || "") !== "tool_call" || toolCallId !== artifactToolCallId) {
        return part;
      }
      const artifactMetadata: RunArtifactMetadata = normalizeRunArtifactMetadata(artifact.metadata);
      const finishedAt = artifactMetadata.finished_at || metadata.finished_at;
      const nextMetadata: TracePartMetadata = { ...metadata, state: artifactStatus };
      if (finishedAt) {
        nextMetadata.finished_at = finishedAt;
      }
      return {
        ...part,
        state: artifactStatus,
        metadata: nextMetadata,
        artifact: partArtifact ? { ...partArtifact, status: artifactStatus } : part.artifact,
      };
    });
  }

  function applyRunEventArtifact(run: RunViewState, artifact: unknown): void {
    const normalized = upsertRunArtifact(run, artifact);
    applyToolArtifactToParts(run, normalized);
    const normalizedPath = String(normalized?.path || "").trim();
    const normalizedKind = String(normalized?.kind || "").trim();
    if (!normalized || normalizedKind !== "file" || !normalizedPath) {
      return;
    }
    const normalizedSourceId = String(normalized.sourceId || "").trim();
    const previewChangeId = normalized.sourceId || normalized.artifactId;
    const previewStatus = normalized.status || "completed";
    const preview: TraceFileChangeView = {
      changeId: previewChangeId,
      sourceId: normalized.sourceId || previewChangeId,
      schemaVersion: 0,
      kind: "file",
      state: previewStatus,
      status: previewStatus,
      path: normalizedPath,
      label: normalizedPath,
      action: normalized.action,
      toolName: normalized.toolName,
      diffLen: normalized.diffLen,
      diff: "",
      diffPreview: normalized.diffPreview,
      beforeContent: null,
      afterContent: null,
      snapshotsAvailable: normalized.snapshotsAvailable,
      artifact: normalized,
      revertSupported: false,
      createdAt: normalized.createdAt,
    };
    const existingIndex = run.fileChanges.findIndex((change) => {
      const existingId = String(change.changeId || change.sourceId || "").trim();
      if (normalizedSourceId && existingId === normalizedSourceId) {
        return true;
      }
      const isDurableChange = change.revertSupported || change.artifact?.source === "file_change";
      return isDurableChange && fileChangesRepresentSameOccurrence(change, preview);
    });
    if (existingIndex >= 0) {
      const existing = run.fileChanges[existingIndex];
      const isDurableChange = existing.revertSupported || existing.artifact?.source === "file_change";
      run.fileChanges[existingIndex] = isDurableChange
        ? {
            ...preview,
            ...existing,
            diffPreview: existing.diffPreview || preview.diffPreview,
            artifact: existing.artifact || preview.artifact,
            snapshotsAvailable: {
              before: existing.snapshotsAvailable.before || preview.snapshotsAvailable.before,
              after: existing.snapshotsAvailable.after || preview.snapshotsAvailable.after,
            },
          }
        : { ...existing, ...preview };
      return;
    }
    run.fileChanges.push(preview);
  }

  function handleRunEvent(payload: LiveRunEventPayload): void {
    const identity = normalizeLiveSessionIdentity(payload);
    const externalChatId = viewExternalChatIdForPayload(payload);
    if (!shouldAcceptLivePayload(payload, externalChatId)) {
      return;
    }
    const session = ensureSession(externalChatId, identity.sessionId);
    if (!session) {
      return;
    }
    const liveEvent = normalizeLiveRunEvent(payload);
    const run = findOrCreateRun(session, liveEvent.runId, liveEvent.createdAt);
    const nextStatus = statusFromRunEvent(
      liveEvent.eventType,
      liveEvent.payload,
      liveEvent.status,
    );
    const rawEvent = traceEventFromLiveRunEvent(liveEvent);
    run.rawEvents.push(rawEvent);
    run.rawEvents = compactRunEvents(run.rawEvents);
    updateLiveTraceEventCounts(run, rawEvent);
    if (run.worktreeSandbox) {
      run.worktreeSandbox = applyWorktreeCleanupEvent(run.worktreeSandbox, rawEvent);
    }

    run.status = mergeMonotonicRunStatus(run.status, nextStatus || "running");

    const description = describeRunEvent(liveEvent.eventType, liveEvent.payload, copy.value);
    if (description) {
      run.events.push({
        id: `${liveEvent.runId}-${liveEvent.eventType}-${liveEvent.createdAt}-${randomToken()}`,
        eventType: liveEvent.eventType,
        kind: liveEvent.kind,
        status: liveEvent.status || "completed",
        createdAt: liveEvent.createdAt,
        payload: liveEvent.payload,
        artifact: liveEvent.artifact,
        ...description,
      });
      if (run.events.length > MAX_RUN_EVENTS) {
        run.events.splice(0, run.events.length - MAX_RUN_EVENTS);
      }
    }

    if (liveEvent.eventType === "run_part_delta" || liveEvent.eventType === "message_part_delta") {
      applyRunPartDelta(run, toRunPartDeltaPayload(liveEvent.payload), liveEvent.createdAt);
    }

    applyRunEventArtifact(run, liveEvent.artifact);

    run.updatedAt = Math.max(Number(run.updatedAt || 0), liveEvent.createdAt);
    session.updatedAt = Math.max(Number(session.updatedAt || 0), liveEvent.createdAt);
    markSessionLiveMutation(session);
    session.runs.sort((left, right) => right.updatedAt - left.updatedAt);
    sortSessions();
    if (isTerminalRunStatus(run.status) || isRunSummaryTriggerEventType(liveEvent.eventType)) {
      scheduleRunSummaryFetch(session, run);
    }
  }

  function setNotice(text: string, tone: NoticeTone): void {
    state.notice.text = text;
    state.notice.tone = tone;
  }

  function showToast(text: unknown, tone: NoticeTone = "info"): void {
    const normalized = String(text || "").trim();
    if (!normalized) {
      return;
    }
    const id = `toast-${Date.now()}-${toastId += 1}`;
    toasts.value = [...toasts.value, { id, text: normalized, tone }].slice(-4);
    const timer = window.setTimeout(() => dismissToast(id), 4500);
    toastTimers.set(id, timer);
  }

  function dismissToast(id: string): void {
    const timer = toastTimers.get(id);
    if (timer) {
      clearTimeout(timer);
      toastTimers.delete(id);
    }
    toasts.value = toasts.value.filter((toast) => toast.id !== id);
  }

  function setSettingsSuccess(noticeKey: string, text: string): void {
    settingsState[noticeKey] = text;
    showToast(text, "success");
  }

  const {
    loadChannelSettings,
    beginChannelConnect,
    cancelChannelConnect,
    saveChannelConnection,
    disconnectChannel,
  } = useChannelSettingsActions({
    settingsState,
    requestSettingsJson,
    copy,
    setSettingsSuccess,
    cancelProviderConnect,
  });

  const {
    loadModelSettings,
    selectModel,
    saveMediaModel,
  } = useModelSettingsActions({
    settingsState,
    requestSettingsJson,
    copy,
    setSettingsSuccess,
    loadProviderSettings: () => loadProviderSettings(),
  });

  const {
    loadProviderAuthStatusById,
    connectOAuthProvider,
    clearProviderAuthPollTimers,
    startProviderAuthLoginById,
    logoutProviderAuthById,
  } = useProviderAuthActions({
    settingsState,
    requestSettingsJson,
    copy,
    setSettingsSuccess,
    loadModelSettings,
    refreshProviderState: async () => {
      await loadProviderSettings();
      await loadModelSettings();
    },
  });

  const {
    loadMcpSettings,
    beginMcpEdit,
    beginMcpCreate,
    cancelMcpEdit,
    saveMcpServer,
    removeMcpServer,
    reloadMcpSettings,
    toggleMcpAdvanced,
    toggleMcpJsonInput,
    toggleMcpToolGroup,
    applyMcpJson,
  } = useMcpSettingsActions({
    settingsState,
    requestSettingsJson,
    copy,
    setSettingsSuccess,
  });

  const { loadNetworkSettings, saveNetworkSettings } = useNetworkSettingsActions({
    settingsState,
    requestSettingsJson,
    copy,
    setSettingsSuccess,
  });

  const { loadSearchSettings, loadSearxngOptions, saveSearchSettings } = useSearchSettingsActions({
    settingsState,
    requestSettingsJson,
    copy,
    setSettingsSuccess,
  });

  const { loadBrowserSettings, saveBrowserSettings, runBrowserTest, runBrowserDoctor, runBrowserInstall } = useBrowserSettingsActions({
    settingsState,
    requestSettingsJson,
    copy,
    setSettingsSuccess,
  });

  const { loadLogSettings, saveLogSettings } = useLogSettingsActions({
    settingsState,
    requestSettingsJson,
    copy,
    setSettingsSuccess,
  });

  const { loadScheduleSettings, saveScheduleSettings } = useScheduleSettingsActions({
    settingsState,
    requestSettingsJson,
    copy,
    setSettingsSuccess,
  });

  const {
    loadProviderSettings,
    beginProviderConnect,
    saveProviderConnection,
    disconnectProvider,
    setProviderCredential,
    deleteCredential,
  } = useProviderSettingsActions({
    settingsState,
    requestSettingsJson,
    copy,
    setSettingsSuccess,
    cancelChannelConnect,
    cancelProviderConnect,
    loadModelSettings,
  });

  const { loadUpdateStatus, runUpdate } = useUpdateSettingsActions({
    settingsState,
    requestSettingsJson,
    copy,
  });

  const loadSettingsSection = createSettingsSectionLoader({
    loadUpdateStatus,
    loadChannelSettings,
    loadProviderSettings,
    loadProviderAuthStatusById,
    loadModelSettings,
    loadMcpSettings,
    loadScheduleSettings,
    loadCronJobs,
    loadNetworkSettings,
    loadSearchSettings,
    loadBrowserSettings,
    loadLogSettings,
  });

  function setActiveSession(externalChatId: string): void {
    state.activeExternalChatId = externalChatId;
    writeStoredValue(STORAGE_KEYS.activeExternalChatId, externalChatId);
    closeSidebar();
  }

  function getFirstWebSession(): ChatSession | null {
    return state.sessions.find((session) => !session.channel || session.channel === "web") || null;
  }

  function ensureActiveWebSession(): ChatSession | null {
    const session = currentSession.value;
    if (session && session.channel === "web") {
      return session;
    }
    let webSession = getFirstWebSession();
    if (!webSession) {
      webSession = createSession();
      state.sessions.unshift(webSession);
      persistLocalDraftSessions();
    }
    state.activeExternalChatId = webSession.externalChatId;
    writeStoredValue(STORAGE_KEYS.activeExternalChatId, webSession.externalChatId);
    return webSession;
  }

  function setSessionChannelFilter(value: SessionChannelFilter): void {
    sessionChannelFilter.value = normalizeSessionChannelFilter(value);
    if (sessionChannelFilter.value !== "web") {
      return;
    }
    const session = currentSession.value;
    if (!session || session.channel === "web") {
      return;
    }
    const firstWebSession = getFirstWebSession();
    if (firstWebSession) {
      setActiveSession(firstWebSession.externalChatId);
    }
  }

  function ensureActiveSessionVisibleInSidebar(): void {
    if (sidebarSessions.value.some((session) => session.externalChatId === state.activeExternalChatId)) {
      return;
    }
    let nextSession = sidebarSessions.value[0];
    if (!nextSession) {
      nextSession = createSession();
      state.sessions.unshift(nextSession);
      persistLocalDraftSessions();
    }
    state.activeExternalChatId = nextSession.externalChatId;
    writeStoredValue(STORAGE_KEYS.activeExternalChatId, nextSession.externalChatId);
  }

  async function setShowHiddenSessions(value: boolean): Promise<void> {
    showHiddenSessions.value = Boolean(value);
    writeStoredValue(STORAGE_KEYS.showHiddenSessions, String(showHiddenSessions.value));
    ensureActiveSessionVisibleInSidebar();
    await loadSessionHistory({ quiet: true });
    ensureActiveSessionVisibleInSidebar();
  }

  function selectRun(runId: string | null | undefined): void {
    const session = currentSession.value;
    const normalizedRunId = String(runId || "").trim();
    if (!session || !normalizedRunId || !session.runs.some((run) => run.runId === normalizedRunId)) {
      return;
    }
    session.activeRunId = normalizedRunId;
    maybeLoadRunSummaryForSession(session);
    maybeLoadRunTraceForSession(session);
  }

  function persistActiveSession(): void {
    if (state.activeExternalChatId) {
      writeStoredValue(STORAGE_KEYS.activeExternalChatId, state.activeExternalChatId);
    }
  }

  function normalizeSettingsSection(sectionName: unknown): SettingsSectionId {
    return normalizeSettingsSectionId(sectionName);
  }

  function deferSettingsWork(callback: () => void): void {
    const run = () => {
      if (!clientDisposed) {
        callback();
      }
    };
    if (typeof window !== "undefined" && typeof window.requestAnimationFrame === "function") {
      window.requestAnimationFrame(() => window.setTimeout(run, 0));
      return;
    }
    setTimeout(run, 0);
  }

  function selectSettingsSection(sectionName: SettingsSectionId): void {
    const nextSection = normalizeSettingsSection(sectionName);
    settingsSection.value = nextSection;
    deferSettingsWork(() => {
      if (settingsOpen.value && settingsSection.value === nextSection) {
        loadSettingsSection(nextSection);
      }
    });
  }

  function syncSettingsForm(): void {
    settingsForm.wsUrl = state.wsUrl;
    settingsForm.displayName = state.displayName;
    settingsForm.externalChatId = currentSession.value?.externalChatId || "";
    settingsForm.showRunHistory = state.showRunHistory;
    settingsForm.showRunTimeline = state.showRunTimeline;
    settingsForm.showRunSummary = state.showRunSummary;
    settingsForm.showRunTrace = state.showRunTrace;
    settingsForm.language = state.language;
    settingsForm.colorScheme = state.colorScheme;
  }

  function openSettings(sectionName: SettingsSectionId = "general"): void {
    const nextSection = normalizeSettingsSection(sectionName);
    settingsOpen.value = true;
    settingsSection.value = nextSection;
    deferSettingsWork(() => {
      if (!settingsOpen.value || settingsSection.value !== nextSection) {
        return;
      }
      syncSettingsForm();
      loadSettingsSection(nextSection);
    });
  }

  function closeSettings(): void {
    if (settingsOpen.value) {
      saveConnectionSettings();
    }
    cancelChannelConnect();
    cancelProviderConnect();
    settingsOpen.value = false;
  }

  function openSidebar(): void {
    sidebarOpen.value = true;
  }

  function closeSidebar(): void {
    sidebarOpen.value = false;
  }

  function toggleSidebar(): void {
    if (sidebarOpen.value) {
      closeSidebar();
      return;
    }
    openSidebar();
  }

  function toggleSidebarCollapsed(): void {
    sidebarCollapsed.value = !sidebarCollapsed.value;
    writeStoredValue(STORAGE_KEYS.sidebarCollapsed, String(sidebarCollapsed.value));
  }

  function toggleTraceInspectorCollapsed(): void {
    traceInspectorCollapsed.value = !traceInspectorCollapsed.value;
    writeStoredValue(STORAGE_KEYS.traceInspectorCollapsed, String(traceInspectorCollapsed.value));
  }

  function clearGatewayReconnectTimer(): void {
    if (gatewayReconnectTimer) {
      clearTimeout(gatewayReconnectTimer);
      gatewayReconnectTimer = null;
    }
  }

  function clearSessionHistoryRefreshTimer(): void {
    if (sessionHistoryRefreshTimer) {
      clearTimeout(sessionHistoryRefreshTimer);
      sessionHistoryRefreshTimer = null;
    }
  }

  function scheduleSessionHistoryRefresh(delayMs: number = SESSION_HISTORY_REFRESH_INTERVAL_MS): void {
    clearSessionHistoryRefreshTimer();
    if (clientDisposed || state.authRequired || state.connectionState !== "connected") {
      return;
    }
    sessionHistoryRefreshTimer = window.setTimeout(async () => {
      sessionHistoryRefreshTimer = null;
      if (clientDisposed || state.authRequired || state.connectionState !== "connected") {
        return;
      }
      try {
        await loadSessionHistory({ quiet: true });
      } finally {
        scheduleSessionHistoryRefresh();
      }
    }, delayMs);
  }

  function scheduleGatewayReconnect(reason: ReconnectNotice, tone: NoticeTone = "warning"): void {
    clearGatewayReconnectTimer();
    if (clientDisposed || !autoReconnectEnabled || state.authRequired || activeSocket || state.connectionState === "connecting") {
      return;
    }
    setNotice(formatReconnectNotice(reason, GATEWAY_RECONNECT_DELAY_MS), tone);
    gatewayReconnectTimer = window.setTimeout(() => {
      gatewayReconnectTimer = null;
      if (clientDisposed || !autoReconnectEnabled || state.authRequired || activeSocket || state.connectionState === "connecting") {
        return;
      }
      connectSocket();
    }, GATEWAY_RECONNECT_DELAY_MS);
  }

  function disconnectSocket(reason: string, tone: NoticeTone = "warning", { manual = true }: DisconnectSocketOptions = {}): void {
    if (manual) {
      autoReconnectEnabled = false;
    }
    clearGatewayReconnectTimer();
    clearSessionHistoryRefreshTimer();
    const socket = activeSocket;
    activeSocket = null;
    state.connectionState = "disconnected";
    if (socket && socket.readyState !== WebSocket.CLOSED) {
      socket.close(1000, "Client disconnect");
    }
    setNotice(reason, tone);
  }

  function buildSocketUrl(baseUrl: string, externalChatId: string, accessToken = ""): string {
    const url = new URL(baseUrl);
    url.searchParams.set("external_chat_id", externalChatId);
    if (accessToken) {
      url.searchParams.set("access_token", accessToken);
    }
    return url.toString();
  }

  function authorizedHeaders(headers?: HeadersInit): Headers {
    const authorized = new Headers(headers);
    const token = String(state.accessToken || "").trim();
    if (token) {
      authorized.set("Authorization", `Bearer ${token}`);
    }
    return authorized;
  }

  async function requestSettingsJson(pathname: string, options: RequestInit = {}): Promise<unknown> {
    try {
      const payload = await requestSettingsJsonFromApi(state.wsUrl, pathname, {
        ...options,
        headers: authorizedHeaders(options.headers),
      });
      state.authError = "";
      return payload;
    } catch (error: unknown) {
      if (settingsErrorStatus(error) === 401) {
        state.authRequired = true;
        state.authError = copy.value.auth.invalidToken;
        state.connectionState = "disconnected";
        autoReconnectEnabled = false;
        clearGatewayReconnectTimer();
        clearSessionHistoryRefreshTimer();
      }
      throw error;
    }
  }

  async function loadCommandCatalog(): Promise<void> {
    state.commandCatalog.loading = true;
    state.commandCatalog.error = "";
    try {
      const payload = toCommandCatalogPayload(await requestSettingsJson("/api/commands"));
      state.commandCatalog.commands = normalizeCommandCatalog(payload);
    } catch (error: unknown) {
      state.commandCatalog.error = settingsErrorMessage(error, "Command catalog unavailable");
    } finally {
      state.commandCatalog.loading = false;
    }
  }

  function applyRunPartDelta(run: RunViewState, payload: RunPartDeltaPayload, createdAt: number): void {
    const partDelta = normalizeRunPartDelta(run, payload, createdAt);
    if (!partDelta.delta && !partDelta.existing) {
      return;
    }

    const nextPart = normalizeTracePart({
      part_id: partDelta.partId,
      part_type: partDelta.partType,
      kind: partDelta.kind,
      state: partDelta.state,
      content: `${partDelta.existing?.content || ""}${partDelta.delta}`,
      tool_name: partDelta.toolName,
      metadata: partDelta.metadata,
      created_at: partDelta.createdAt,
    });
    if (!nextPart) {
      return;
    }
    if (partDelta.existingIndex >= 0) {
      run.parts[partDelta.existingIndex] = nextPart;
    } else {
      run.parts.push(nextPart);
    }
    if (run.parts.length > MAX_RUN_ARTIFACTS) {
      run.parts.splice(0, run.parts.length - MAX_RUN_ARTIFACTS);
    }
    applyRunEventArtifact(run, nextPart.artifact);
  }

  function normalizeRunPartDelta(run: RunViewState, payload: RunPartDeltaPayload, createdAt: number): RunPartDeltaView {
    const partType = String(payload.part_type || payload.partType || "assistant_message").trim() || "assistant_message";
    const partId = String(payload.part_id || payload.partId || `stream:${run.runId}:${partType}`).trim();
    const delta = String(payload.content_delta ?? payload.delta ?? payload.text ?? payload.content ?? "");
    const existingIndex = run.parts.findIndex((part) => part.partId === partId);
    const existing = existingIndex >= 0 ? run.parts[existingIndex] : null;
    const state = String(payload.state || payload.status || existing?.state || "running").trim() || "running";
    const metadata = normalizeTracePartMetadata(payload.metadata);
    const existingMetadata = normalizeTracePartMetadata(existing?.metadata);
    const existingCreatedAt = Number(existing?.createdAt);
    return {
      existingIndex,
      existing,
      partId,
      partType,
      delta,
      state,
      kind: normalizeRunKind(payload.kind || existing?.kind, "text"),
      toolName: textField(payload.tool_name || payload.toolName || existing?.toolName),
      metadata: { ...existingMetadata, ...metadata, streaming: !isTerminalPartState(state) },
      createdAt: Number.isFinite(existingCreatedAt) && existingCreatedAt > 0 ? existingCreatedAt : createdAt,
    };
  }

  function normalizeLocalizedRawRunEvent(event: TraceEventView): RunTimelineEventView | null {
    const eventType = String(event.eventType || "");
    const eventPayload = normalizeRunTimelinePayload(event.payload);
    const description = describeRunEvent(eventType, eventPayload, copy.value);
    return description
      ? {
          id: `${event.id}-localized`,
          eventType,
          kind: normalizeRunKind(event.kind, inferRunEventKind(eventType)),
          status: String(event.status || "completed"),
          createdAt: normalizeEventTimestamp(event.createdAt),
          payload: eventPayload,
          artifact: normalizeRunArtifact(event.artifact),
          ...description,
        }
      : null;
  }

  function localizeRawRunEvents(rawEvents: TraceEventView[]): RunTimelineEventView[] {
    return rawEvents
      .map(normalizeLocalizedRawRunEvent)
      .filter((event): event is RunTimelineEventView => Boolean(event))
      .slice(-MAX_RUN_EVENTS);
  }

  function runSummaryTimerKey(sessionId: string, runId: string): string {
    return `${sessionId}\u0000${runId}`;
  }

  function clearRunSummaryTimer(sessionId: string, runId: string): void {
    const key = runSummaryTimerKey(sessionId, runId);
    const timer = runSummaryTimers.get(key);
    if (timer) {
      clearTimeout(timer);
      runSummaryTimers.delete(key);
    }
  }

  async function loadRunSummary(
    session: ChatSession | null | undefined,
    run: RunViewState | null | undefined,
  ): Promise<void> {
    const sessionId = run?.sessionId || session?.sessionId || "";
    if (!state.showRunSummary || !sessionId || !run?.runId || clientDisposed) {
      return;
    }

    clearRunSummaryTimer(sessionId, run.runId);
    const requestGeneration = beginRequestGeneration(runSummaryRequestGenerations, run);
    run.summaryLoading = true;
    run.summaryError = "";
    try {
      const summary = normalizeRunSummary(await requestSettingsJson(buildRunSummaryPath(run.runId, sessionId)));
      if (clientDisposed || !isCurrentRequestGeneration(runSummaryRequestGenerations, run, requestGeneration)) {
        return;
      }
      if (summary) {
        run.summary = summary;
        run.status = mergeMonotonicRunStatus(run.status, summary.status);
        run.summaryNotFoundAttempts = 0;
        maybeLoadRunTraceForSession(session);
      }
    } catch (error: unknown) {
      if (clientDisposed || !isCurrentRequestGeneration(runSummaryRequestGenerations, run, requestGeneration)) {
        return;
      }
      if (settingsErrorStatus(error) === 404) {
        run.summaryNotFoundAttempts = coerceNonNegativeInteger(run.summaryNotFoundAttempts) + 1;
        run.summaryError = "";
        if (run.summaryNotFoundAttempts < RUN_SUMMARY_NOT_FOUND_RETRY_LIMIT) {
          scheduleRunSummaryRetry(session, run);
        }
        return;
      }
      run.summaryError = settingsErrorMessage(error, copy.value.notices.runSummaryLoadFailed);
    } finally {
      if (isCurrentRequestGeneration(runSummaryRequestGenerations, run, requestGeneration)) {
        run.summaryLoading = false;
      }
    }
  }

  function scheduleRunSummaryRetry(
    session: ChatSession | null | undefined,
    run: RunViewState | null | undefined,
  ) {
    const sessionId = run?.sessionId || session?.sessionId || "";
    if (!state.showRunSummary || !sessionId || !run?.runId || run.summary || clientDisposed) {
      return;
    }

    clearRunSummaryTimer(sessionId, run.runId);
    const key = runSummaryTimerKey(sessionId, run.runId);
    const timer = window.setTimeout(() => {
      runSummaryTimers.delete(key);
      void loadRunSummary(session, run);
    }, RUN_SUMMARY_NOT_FOUND_RETRY_DELAY_MS);
    runSummaryTimers.set(key, timer);
  }

  async function loadRunTrace(
    session: ChatSession | null | undefined,
    run: RunViewState | null | undefined,
  ): Promise<void> {
    const sessionId = run?.sessionId || session?.sessionId || "";
    if (!sessionId || !run?.runId || clientDisposed) {
      return;
    }

    run.traceLoading = true;
    run.traceError = "";
    const requestGeneration = beginRequestGeneration(runTraceRequestGenerations, run);
    const traceWatermark = captureRunTraceWatermark(run);
    try {
      const trace = normalizeRunTracePayload(
        toRunTracePayload(await requestSettingsJson(buildRunTracePath(run.runId, sessionId))),
      );
      if (clientDisposed || !isCurrentRequestGeneration(runTraceRequestGenerations, run, requestGeneration)) {
        return;
      }
      const { rawEvents, fileChanges, parts, artifacts } = trace;
      const snapshotArtifacts = artifacts.length
        ? artifacts.slice(-MAX_RUN_ARTIFACTS)
        : collectRunTraceFallbackArtifacts(rawEvents, parts, fileChanges).slice(-MAX_RUN_ARTIFACTS);
      const mergedTrace = mergeRunTraceSnapshot(
        { rawEvents, eventCounts: trace.eventCounts, parts, artifacts: snapshotArtifacts, fileChanges },
        run,
        traceWatermark,
      );
      run.rawEvents = compactRunEvents(mergedTrace.rawEvents);
      run.eventCounts = {
        ...mergedTrace.eventCounts,
        returned: run.rawEvents.length,
        compacted: Math.max(mergedTrace.eventCounts.compacted, mergedTrace.eventCounts.total - run.rawEvents.length),
      };
      run.events = localizeRawRunEvents(run.rawEvents);
      run.parts = mergedTrace.parts.slice(-MAX_RUN_ARTIFACTS);
      run.artifacts = mergedTrace.artifacts.slice(-MAX_RUN_ARTIFACTS);
      run.artifacts.forEach((artifact) => applyToolArtifactToParts(run, artifact));
      run.fileChanges = mergedTrace.fileChanges;
      run.diffSummary = trace.diffSummary;
      run.worktreeSandbox = preserveKnownRemovedWorktreeSandbox(
        run.worktreeSandbox,
        findWorktreeSandbox(run.parts, run.artifacts, run.rawEvents),
      );
      run.traceLoaded = true;
    } catch (error: unknown) {
      if (clientDisposed || !isCurrentRequestGeneration(runTraceRequestGenerations, run, requestGeneration)) {
        return;
      }
      run.traceError = settingsErrorMessage(error, copy.value.notices.runTraceLoadFailed);
    } finally {
      if (isCurrentRequestGeneration(runTraceRequestGenerations, run, requestGeneration)) {
        run.traceLoading = false;
      }
    }
  }

  function scheduleRunSummaryFetch(
    session: ChatSession | null | undefined,
    run: RunViewState | null | undefined,
  ) {
    const sessionId = run?.sessionId || session?.sessionId || "";
    if (!state.showRunSummary || !sessionId || !run?.runId) {
      return;
    }

    clearRunSummaryTimer(sessionId, run.runId);
    beginRequestGeneration(runSummaryRequestGenerations, run);
    run.summaryError = "";
    run.summaryLoading = true;
    const key = runSummaryTimerKey(sessionId, run.runId);
    const timer = window.setTimeout(() => {
      runSummaryTimers.delete(key);
      void loadRunSummary(session, run);
    }, RUN_SUMMARY_FETCH_DELAY_MS);
    runSummaryTimers.set(key, timer);
  }

  function maybeLoadRunSummaryForSession(session: ChatSession | null | undefined): void {
    const run = getActiveRun(session);
    if (!shouldLoadRunSummary(state, run)) {
      return;
    }
    scheduleRunSummaryFetch(session, run);
  }

  function maybeLoadRunTraceForSession(session: ChatSession | null | undefined): void {
    const run = getActiveRun(session);
    if (!shouldLoadRunTrace(run)) {
      return;
    }
    void loadRunTrace(session, run);
  }

  function getActiveCronSessionId(): string {
    const session = currentSession.value;
    if (session?.sessionId) {
      return session.sessionId;
    }
    if (session?.externalChatId) {
      return `web:${session.externalChatId}`;
    }
    return "";
  }

  function formatDateTimeLocal(timestampMs: unknown): string {
    const date = new Date(Number(timestampMs || 0));
    if (Number.isNaN(date.getTime())) {
      return "";
    }
    const offsetMs = date.getTimezoneOffset() * 60_000;
    return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16);
  }

  function resetCronJobForm(): void {
    settingsState.cronJobForm.showEditor = false;
    settingsState.cronJobForm.sessionId = "";
    settingsState.cronJobForm.jobId = "";
    settingsState.cronJobForm.mode = "cron";
    settingsState.cronJobForm.name = "";
    settingsState.cronJobForm.message = "";
    settingsState.cronJobForm.everySeconds = "3600";
    settingsState.cronJobForm.cronExpr = "0 9 * * *";
    settingsState.cronJobForm.at = "";
    settingsState.cronJobForm.timezone = settingsState.schedule.default_timezone || DEFAULT_CRON_TIMEZONE;
    settingsState.cronJobForm.deliver = true;
  }

  function buildCronJobPayload(): CronJobPayload {
    const form = settingsState.cronJobForm;
    const payload: CronJobPayload = {
      session_id: form.sessionId || getActiveCronSessionId(),
      kind: normalizeCronJobMode(form.mode),
      name: String(form.name || "").trim(),
      message: String(form.message || "").trim(),
      deliver: Boolean(form.deliver),
    };
    if (form.mode === "every") {
      payload.every_seconds = Number(form.everySeconds);
    } else if (form.mode === "cron") {
      payload.cron_expr = String(form.cronExpr || "").trim();
      payload.tz = String(form.timezone || settingsState.schedule.default_timezone || DEFAULT_CRON_TIMEZONE).trim();
    } else if (form.mode === "at") {
      payload.at = String(form.at || "").trim();
    }
    return payload;
  }

  function makeHistoryMessage(payload: HistoryMessagePayload, index: number): ChatMessage {
    const metadata = payload.metadata || {};
    const role = normalizeChatMessageRole(payload.role);
    return {
      id: `history-${normalizeEventTimestamp(payload.created_at)}-${index}-${randomToken()}`,
      role,
      text: String(payload.content || ""),
      meta: String(metadata.sender_name || metadata.sender_id || (role === "user" ? state.displayName : "OpenSprite")),
      createdAt: normalizeEventTimestamp(payload.created_at),
    };
  }

  function normalizeSessionEntryContent(entry: HistoryEntryContentPayload | null, index: number): LiveEntryContentItem | null {
    if (!entry) {
      return null;
    }
    const type = String(entry.type || "text").trim() || "text";
    const artifact = entry.artifact && typeof entry.artifact === "object" ? normalizeRunArtifact(entry.artifact) : null;
    return {
      id: String(entry.part_id || entry.partId || entry.artifact_id || entry.artifactId || `${type}-${index}`).trim(),
      type,
      status: String(entry.status || "").trim(),
      title: String(entry.title || artifact?.title || type).trim(),
      detail: String(entry.detail || entry.text || artifact?.detail || "").trim(),
      text: String(entry.text || ""),
      createdAt: normalizeEventTimestamp(entry.created_at ?? entry.createdAt),
      artifact,
    };
  }

  function normalizeHistoryEntryContent(content: Array<HistoryEntryContentPayload | null>): LiveEntryContentItem[] {
    return content
      .map(normalizeSessionEntryContent)
      .filter((item): item is LiveEntryContentItem => Boolean(item));
  }

  function makeHistoryEntry(payload: HistoryEntryPayload | null, index: number): LiveEntry | null {
    if (!payload) {
      return null;
    }
    const metadata = toLiveEntryMetadata(payload.metadata);
    const role = normalizeChatMessageRole(payload.role);
    const content = normalizeHistoryEntryContent(payload.content);
    return {
      id: String(payload.entry_id || payload.entryId || `entry-${index}-${randomToken()}`).trim(),
      type: String(payload.entry_type || payload.entryType || role).trim() || role,
      role,
      runId: String(payload.run_id || payload.runId || "").trim(),
      status: String(payload.status || "").trim(),
      text: String(payload.text || ""),
      content,
      meta: String(metadata.sender_name || metadata.sender_id || (role === "user" ? state.displayName : "OpenSprite")),
      createdAt: normalizeEventTimestamp(payload.created_at ?? payload.createdAt),
      updatedAt: normalizeEventTimestamp(payload.updated_at ?? payload.updatedAt),
      metadata,
    };
  }

  function normalizeHistoryRun(payload: HistoryRunPayload | null): RunViewState | null {
    if (!payload) {
      return null;
    }
    const runId = String(payload.run_id || payload.runId || "").trim();
    if (!runId) {
      return null;
    }
    const finishedAt = Number(payload.finished_at ?? payload.finishedAt);
    return createRunViewState({
      runId,
      sessionId: String(payload.session_id || payload.sessionId || "").trim(),
      status: String(payload.status || "running").trim() || "running",
      createdAt: normalizeEventTimestamp(payload.created_at ?? payload.createdAt),
      updatedAt: normalizeEventTimestamp(payload.updated_at ?? payload.updatedAt),
      finishedAt: Number.isFinite(finishedAt) && finishedAt > 0 ? normalizeEventTimestamp(finishedAt) : null,
    });
  }

  function isRunViewState(run: RunViewState | null): run is RunViewState {
    return Boolean(run);
  }

  function normalizeRunList(runs: Array<HistoryRunPayload | null>): RunViewState[] {
    return runs.map(normalizeHistoryRun).filter(isRunViewState);
  }

  function normalizeRunsPayload(payload: RunsPayload | null): RunViewState[] {
    return normalizeRunList(toHistoryRunPayloadList(payload?.runs));
  }

  function isLiveEntry(entry: LiveEntry | null): entry is LiveEntry {
    return Boolean(entry);
  }

  function normalizeHistoryMessages(messages: HistoryMessagePayload[]): ChatMessage[] {
    return messages.map(makeHistoryMessage).filter((message) => message.text.trim());
  }

  function normalizeHistoryEntries(entries: Array<HistoryEntryPayload | null>): LiveEntry[] {
    return entries.map(makeHistoryEntry).filter(isLiveEntry);
  }

  function normalizeHistoryRuns(runs: Array<HistoryRunPayload | null>): RunViewState[] {
    return normalizeRunList(runs);
  }

  function mergeSessionRuns(session: ChatSession, runs: RunViewState[]): void {
    const existingRuns = new Map<string, RunViewState>((session.runs || []).map((run) => [run.runId, run]));
    const mergedRuns: RunViewState[] = [];

    for (const run of runs) {
      const existing = existingRuns.get(run.runId);
      if (existing) {
        const existingUpdatedAt = Number(existing.updatedAt || 0);
        const incomingUpdatedAt = Number(run.updatedAt || 0);
        const incomingIsCurrent = incomingUpdatedAt >= existingUpdatedAt;
        existing.sessionId = existing.sessionId || run.sessionId;
        existing.createdAt = run.createdAt || existing.createdAt;
        if (incomingIsCurrent) {
          existing.status = mergeMonotonicRunStatus(existing.status, run.status);
          existing.finishedAt = run.finishedAt || existing.finishedAt;
        }
        existing.updatedAt = Math.max(existingUpdatedAt, incomingUpdatedAt);
        mergedRuns.push(existing);
        existingRuns.delete(run.runId);
      } else {
        mergedRuns.push(run);
      }
    }

    for (const run of existingRuns.values()) {
      if (run.status === "running" || run.summary || run.rawEvents?.length) {
        mergedRuns.push(run);
      }
    }

    session.runs = mergedRuns.sort((left, right) => Number(right.updatedAt || 0) - Number(left.updatedAt || 0));
    if (!session.runs.some((run) => run.runId === session.activeRunId)) {
      session.activeRunId = session.runs[0]?.runId || null;
    }
  }

  async function loadCurrentSessionRuns({ force = false }: LoadRunsOptions = {}): Promise<void> {
    const session = currentSession.value;
    if (!session?.sessionId || session.runsLoading || (session.runsLoaded && !force)) {
      return;
    }

    session.runsLoading = true;
    session.runsError = "";
    try {
      const payload = toRunsPayload(await requestSettingsJson(buildRunsPath(session.sessionId, RUN_HISTORY_LIMIT)));
      const runs = normalizeRunsPayload(payload);
      mergeSessionRuns(session, runs);
      session.runsLoaded = true;
      maybeLoadRunSummaryForSession(session);
      maybeLoadRunTraceForSession(session);
    } catch (error: unknown) {
      session.runsError = settingsErrorMessage(error, copy.value.notices.runHistoryLoadFailed);
    } finally {
      session.runsLoading = false;
    }
  }

  function shouldBackfillSessionRuns(session: ChatSession | null | undefined): boolean {
    if (!session?.sessionId) {
      return false;
    }
    const now = Date.now();
    const lastBackfillAt = runBackfillTimes.get(session.sessionId) || 0;
    if (session.runsLoaded && now - lastBackfillAt < RUN_BACKFILL_COOLDOWN_MS) {
      return false;
    }
    runBackfillTimes.set(session.sessionId, now);
    return true;
  }

  function normalizeHistorySession(payload: HistorySessionPayload | null): ChatSession | null {
    if (!payload) {
      return null;
    }
    const sessionId = String(payload.session_id || "").trim();
    const channel = String(payload.channel || channelFromSessionId(sessionId) || "web").trim() || "web";
    const transportExternalChatId = String(payload.external_chat_id || "").trim()
      || externalChatIdFromSessionId(sessionId)
      || generateExternalChatId();
    const externalChatId = channel === "web" ? transportExternalChatId : (sessionId || `${channel}:${transportExternalChatId}`);
    const session = createSession(externalChatId);
    session.channel = channel;
    session.hiddenFromBrowserHistory = Boolean(payload.hidden_from_browser_history ?? payload.hiddenFromBrowserHistory);
    session.transportExternalChatId = transportExternalChatId;
    session.sessionId = sessionId || null;
    session.title = String(payload.title || "").trim() || "New chat";
    session.updatedAt = normalizeEventTimestamp(payload.updated_at);
    session.messages = normalizeHistoryMessages(payload.messages || []);
    session.entries = normalizeHistoryEntries(payload.entries || []);
    session.runs = normalizeHistoryRuns(payload.runs || []);
    session.activeRunId = session.runs[0]?.runId || null;
    session.status = normalizeHistorySessionStatus(payload.status || {});
    return session;
  }

  function normalizeSessionHistorySessions(sessions: Array<HistorySessionPayload | null>): ChatSession[] {
    return sessions.map(normalizeHistorySession).filter(isChatSession);
  }

  function normalizeSessionHistoryPayload(payload: SessionHistoryPayload | null): NormalizedSessionHistoryPayload {
    const sessions = normalizeSessionHistorySessions(payload?.sessions || []);
    const metrics = normalizeSessionHistoryMetrics(payload, sessions.length);
    return {
      sessions,
      ...metrics,
    };
  }

  function isChatSession(session: ChatSession | null): session is ChatSession {
    return Boolean(session);
  }

  function mergeHistorySession(
    existing: ChatSession,
    incoming: ChatSession,
    { preserveDetails = false, changedSinceRequest = false }: MergeHistorySessionOptions = {},
  ): ChatSession {
    return mergeFreshSessionSnapshot(existing, incoming, {
      preserveDetails,
      changedSinceRequest,
      snapshotFence: snapshotFenceForSession(existing),
      mergeRuns: (target, snapshot) => mergeSessionRuns(target, snapshot.runs),
    });
  }

  function mergeHistorySessions(historySessions: ChatSession[], options: MergeHistorySessionsOptions = {}): void {
    const preserveActiveSession = Boolean(options?.preserveActiveSession);
    const pruneMissingHistorySessions = Boolean(options?.pruneMissingHistorySessions);
    const revisionWatermark = options?.sessionRevisionWatermark;
    const visibleHistorySessions = historySessions.filter((session) => !isDeletedSessionTombstoned(session));
    const historySessionIds = new Set(visibleHistorySessions.map((session) => session.sessionId).filter(isNonEmptyString));

    const existingSessionsByExternalChatId = new Map(state.sessions.map((session) => [session.externalChatId, session]));
    const sessionsByExternalChatId = new Map<string, ChatSession>();
    for (const historySession of visibleHistorySessions) {
      const existingSession = existingSessionsByExternalChatId.get(historySession.externalChatId);
      if (!existingSession) {
        sessionsByExternalChatId.set(historySession.externalChatId, historySession);
        continue;
      }
      sessionsByExternalChatId.set(
        historySession.externalChatId,
        mergeHistorySession(existingSession, historySession, {
          preserveDetails: preserveActiveSession && historySession.externalChatId === state.activeExternalChatId,
          changedSinceRequest: Boolean(revisionWatermark)
            && (revisionWatermark.get(historySession.externalChatId) === undefined
              || revisionWatermark.get(historySession.externalChatId) !== sessionLiveRevision(existingSession)),
        }),
      );
    }

    for (const session of state.sessions) {
      if (isDeletedSessionTombstoned(session)) {
        continue;
      }
      if (session.sessionId && historySessionIds.has(session.sessionId)) {
        continue;
      }
      const isBootstrapStoredDraft = initialSessionFromStoredExternalChatId
        && session.externalChatId === initialSessionExternalChatId
        && isLocalDraftSession(session);
      const isCurrentDraft = session.externalChatId === state.activeExternalChatId
        && isLocalDraftSession(session)
        && !isBootstrapStoredDraft;
      const isStoredDraft = isLocalDraftSession(session) && localDraftExternalChatIds.has(session.externalChatId);
      const shouldRetainActiveHistorySession = !pruneMissingHistorySessions
        && preserveActiveSession
        && session.sessionId
        && !session.hiddenFromBrowserHistory
        && session.externalChatId === state.activeExternalChatId;
      const shouldRetainLocalSession = session.sessionId
        ? shouldRetainActiveHistorySession
        : session.messages.length > 0
        || session.entries.length > 0
        || isStoredDraft
        || isCurrentDraft;
      if (!sessionsByExternalChatId.has(session.externalChatId) && shouldRetainLocalSession) {
        sessionsByExternalChatId.set(session.externalChatId, session);
      }
    }

    state.sessions = [...sessionsByExternalChatId.values()].sort((left, right) => right.updatedAt - left.updatedAt);
    if (!state.sessions.length) {
      state.sessions.push(createSession());
    }
    if (!state.sessions.some((session) => session.externalChatId === state.activeExternalChatId)) {
      state.activeExternalChatId = state.sessions[0]?.externalChatId || state.activeExternalChatId;
      writeStoredValue(STORAGE_KEYS.activeExternalChatId, state.activeExternalChatId);
    }
    persistLocalDraftSessions();
  }

  async function performSessionHistoryRefresh(request: SessionHistoryRefreshRequest): Promise<void> {
    const quiet = request.quiet;
    const sessionRevisionWatermark = quiet ? captureSessionRevisionWatermark() : undefined;
    try {
      const params = new URLSearchParams({ channel: "all", limit: "50", messages: "50" });
      if (request.includeHiddenSessions) {
        params.set("include_cli", "true");
      }
      const history = normalizeSessionHistoryPayload(
        toSessionHistoryPayload(await requestSettingsJson(`/api/sessions?${params.toString()}`)),
      );
      state.sessionHistory.total = history.total;
      state.sessionHistory.limit = history.limit;
      state.sessionHistory.channelTotals = history.channelTotals;
      mergeHistorySessions(history.sessions, {
        preserveActiveSession: quiet,
        pruneMissingHistorySessions: request.pruneMissingHistorySessions,
        sessionRevisionWatermark,
      });
      if (!quiet) {
        scrollMessagesToBottom({ force: true });
      }
    } catch {
      if (!quiet) {
        setNotice(copy.value.notices.historyLoadFailed, "warning");
      }
    }
  }

  async function drainSessionHistoryRefreshQueue(): Promise<void> {
    try {
      let request = takePendingSessionHistoryRefresh(sessionHistoryRefreshQueue);
      while (request) {
        await performSessionHistoryRefresh(request);
        request = takePendingSessionHistoryRefresh(sessionHistoryRefreshQueue);
      }
    } finally {
      const resolve = resolveSessionHistoryRefresh;
      sessionHistoryRefreshPromise = null;
      resolveSessionHistoryRefresh = null;
      resolve?.();
    }
  }

  async function loadSessionHistory(options: LoadSessionHistoryOptions = {}): Promise<void> {
    enqueueSessionHistoryRefresh(sessionHistoryRefreshQueue, {
      quiet: Boolean(options.quiet),
      pruneMissingHistorySessions: Boolean(options.pruneMissingHistorySessions),
      includeHiddenSessions: showHiddenSessions.value,
    });
    let refreshPromise = sessionHistoryRefreshPromise;
    if (!refreshPromise) {
      refreshPromise = new Promise<void>((resolve) => {
        resolveSessionHistoryRefresh = resolve;
      });
      sessionHistoryRefreshPromise = refreshPromise;
      void drainSessionHistoryRefreshQueue();
    }
    await refreshPromise;
  }

  async function loadCronJobs(): Promise<void> {
    settingsState.cronJobsLoading = true;
    settingsState.cronJobsError = "";
    try {
      const payload = toCronJobsPayload(await requestSettingsJson("/api/cron/jobs"));
      settingsState.cronJobs = payload?.jobs || [];
    } catch (error: unknown) {
      settingsState.cronJobsError = settingsErrorMessage(error, copy.value.notices.cronJobsLoadFailed);
    } finally {
      settingsState.cronJobsLoading = false;
    }
  }

  function cancelProviderConnect(): void {
    resetProviderConnectForm(settingsState.connectForm);
  }

  function beginCronJobEdit(job: CronJobView): void {
    const schedule = job.schedule;
    const payload = job.payload;
    settingsState.cronJobsNotice = "";
    settingsState.cronJobsError = "";
    settingsState.cronJobForm.showEditor = true;
    settingsState.cronJobForm.sessionId = job.session_id;
    settingsState.cronJobForm.jobId = job.id;
    settingsState.cronJobForm.mode = normalizeCronJobMode(schedule.kind);
    settingsState.cronJobForm.name = job.name;
    settingsState.cronJobForm.message = payload.message || "";
    const everyMs = Number(schedule.every_ms);
    settingsState.cronJobForm.everySeconds = Number.isFinite(everyMs) && everyMs > 0
      ? String(Math.max(1, Math.floor(everyMs / 1000)))
      : "3600";
    settingsState.cronJobForm.cronExpr = schedule.expr || "0 9 * * *";
    settingsState.cronJobForm.at = schedule.at_ms ? formatDateTimeLocal(schedule.at_ms) : "";
    settingsState.cronJobForm.timezone = schedule.tz || settingsState.schedule.default_timezone || DEFAULT_CRON_TIMEZONE;
    settingsState.cronJobForm.deliver = payload.deliver !== false;
  }

  function cancelCronJobEdit(): void {
    resetCronJobForm();
  }

  function beginCronJobCreate(): void {
    resetCronJobForm();
    settingsState.cronJobsNotice = "";
    settingsState.cronJobsError = "";
    settingsState.cronJobForm.showEditor = true;
  }

  async function saveCronJob(): Promise<void> {
    const payload = buildCronJobPayload();
    if (!payload.session_id) {
      settingsState.cronJobsError = copy.value.notices.sessionNotReady;
      return;
    }
    if (!payload.message) {
      settingsState.cronJobsError = copy.value.notices.cronJobMessageRequired;
      return;
    }

    const jobId = settingsState.cronJobForm.jobId;
    settingsState.cronJobsLoading = true;
    settingsState.cronJobsError = "";
    settingsState.cronJobsNotice = "";
    try {
      await requestSettingsJson(jobId ? `/api/cron/jobs/${encodeURIComponent(jobId)}` : "/api/cron/jobs", {
        method: jobId ? "PUT" : "POST",
        body: JSON.stringify(payload),
      });
      setSettingsSuccess("cronJobsNotice", jobId ? copy.value.notices.cronJobUpdated : copy.value.notices.cronJobCreated);
      resetCronJobForm();
      await loadCronJobs();
    } catch (error: unknown) {
      settingsState.cronJobsError = settingsErrorMessage(error, copy.value.notices.cronJobSaveFailed);
    } finally {
      settingsState.cronJobsLoading = false;
    }
  }

  async function runCronJobAction(job: CronJobView, action: CronJobAction): Promise<void> {
    const sessionId = String(job.session_id || getActiveCronSessionId()).trim();
    const jobId = String(job.id || "").trim();
    if (!sessionId) {
      settingsState.cronJobsError = copy.value.notices.sessionNotReady;
      return;
    }
    if (!jobId) {
      settingsState.cronJobsError = copy.value.notices.cronJobActionFailed;
      return;
    }

    settingsState.cronJobsLoading = true;
    settingsState.cronJobsError = "";
    settingsState.cronJobsNotice = "";
    try {
      if (action === "remove") {
        await requestSettingsJson(`/api/cron/jobs/${encodeURIComponent(jobId)}?session_id=${encodeURIComponent(sessionId)}`, {
          method: "DELETE",
        });
      } else {
        await requestSettingsJson(`/api/cron/jobs/${encodeURIComponent(jobId)}/${encodeURIComponent(action)}`, {
          method: "POST",
          body: JSON.stringify({ session_id: sessionId }),
        });
      }
      setSettingsSuccess("cronJobsNotice", copy.value.notices.cronJobActionDone);
      await loadCronJobs();
    } catch (error: unknown) {
      settingsState.cronJobsError = settingsErrorMessage(error, copy.value.notices.cronJobActionFailed);
    } finally {
      settingsState.cronJobsLoading = false;
    }
  }

  function handleSocketMessage(rawData: string): void {
    const result = parseLiveSocketMessage(rawData);
    if (result.kind === "invalid") {
      setNotice(copy.value.notices.parseError, "error");
      return;
    }
    if (result.kind === "unsupported") {
      return;
    }
    const { event } = result;
    if (event.type === "session") {
      const identity = normalizeLiveSessionIdentity(event.payload);
      const { sessionId, transportExternalChatId } = identity;
      const session = ensureSession(transportExternalChatId, sessionId);
      if (!session) {
        return;
      }
      if (!state.activeExternalChatId) {
        state.activeExternalChatId = session.externalChatId;
      }
      markSessionLiveMutation(session);
      persistActiveSession();
      setNotice(copy.value.notices.liveSessionReady(sessionId), "success");
      if (shouldBackfillSessionRuns(session)) {
        void loadCurrentSessionRuns({ force: true });
      }
      return;
    }

    if (event.type === "message") {
      const liveMessage = normalizeLiveAssistantMessage(
        event.payload,
        currentSession.value?.externalChatId,
      );
      if (!shouldAcceptLivePayload(event.payload, liveMessage.externalChatId)) {
        return;
      }
      const session = ensureSession(liveMessage.externalChatId, liveMessage.sessionId);
      if (!session) {
        return;
      }
      if (session.channel !== "web") {
        return;
      }
      addMessage(session.externalChatId, makeMessage("assistant", liveMessage.text, "OpenSprite"));
      scrollMessagesToBottom();
      return;
    }

    if (event.type === "run_event") {
      handleRunEvent(event.payload);
      scrollMessagesToBottom();
      return;
    }

    if (event.type === "session_status") {
      applySessionStatus(event.payload);
      return;
    }

    if (event.type === "error") {
      setNotice(normalizeLiveSocketErrorMessage(event.payload, copy.value.notices.gatewayError), "error");
    }
  }

  function connectSocket(): void {
    const session = ensureActiveWebSession();
    if (!session) {
      return;
    }
    autoReconnectEnabled = true;
    clearGatewayReconnectTimer();

    let socketUrl: string;
    try {
      socketUrl = buildSocketUrl(state.wsUrl, session.externalChatId, state.accessToken);
    } catch {
      setNotice(copy.value.notices.invalidWs, "error");
      openSettings("general");
      return;
    }

    if (activeSocket) {
      disconnectSocket(copy.value.notices.refreshConnection, "info", { manual: false });
    }

    state.connectionState = "connecting";
    setNotice(copy.value.notices.connectingTo(state.wsUrl), "info");

    const socket = new WebSocket(socketUrl);
    activeSocket = socket;

    socket.addEventListener("open", () => {
      if (activeSocket !== socket) {
        return;
      }
      state.authRequired = false;
      state.authError = "";
      state.connectionState = "connected";
      setNotice(copy.value.notices.connected, "success");
      void loadSessionHistory({ quiet: true });
      scheduleSessionHistoryRefresh();
    });

    socket.addEventListener("message", (event: MessageEvent) => {
      if (activeSocket !== socket) {
        return;
      }
      if (typeof event.data !== "string") {
        setNotice(copy.value.notices.parseError, "error");
        return;
      }
      handleSocketMessage(event.data);
    });

    socket.addEventListener("error", () => {
      if (activeSocket !== socket) {
        return;
      }
      if (state.accessToken) {
        state.authError = copy.value.auth.connectionFailed;
      }
      setNotice(copy.value.notices.socketFailed, "error");
    });

    socket.addEventListener("close", () => {
      if (activeSocket !== socket) {
        return;
      }
      const failedToConnect = state.connectionState === "connecting";
      activeSocket = null;
      state.connectionState = "disconnected";
      scheduleGatewayReconnect(
        failedToConnect ? copy.value.notices.couldNotConnect : copy.value.notices.disconnected,
        failedToConnect ? "error" : "warning",
      );
    });
  }

  function resizeComposer(): void {
    const input = messageInput;
    if (!input) {
      return;
    }
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 220)}px`;
  }

  function scrollMessagesToBottom(options: ScrollOptions = {}): void {
    const force = Boolean(options?.force);
    runAfterCurrentMicrotask(() => {
      const stage = messageStage;
      if (stage) {
        if (!force && !messageStagePinnedToBottom) {
          return;
        }
        stage.scrollTop = stage.scrollHeight;
        messageStagePinnedToBottom = true;
        window.requestAnimationFrame?.(() => {
          stage.scrollTop = stage.scrollHeight;
          messageStagePinnedToBottom = true;
        });
      }
    });
  }

  function createNewChat(): void {
    const session = createSession();
    state.sessions.unshift(session);
    state.activeExternalChatId = session.externalChatId;
    writeStoredValue(STORAGE_KEYS.activeExternalChatId, session.externalChatId);
    persistLocalDraftSessions();
    setNotice(copy.value.notices.newDraft, "info");
    scrollMessagesToBottom({ force: true });
  }

  function clearSessionRunTimers(session: ChatSession | null | undefined): void {
    for (const run of session?.runs || []) {
      if (run?.runId) {
        clearRunSummaryTimer(session.sessionId, run.runId);
      }
    }
  }

  function sessionTombstoneKeys(session: SessionIdentity | null | undefined): string[] {
    const sessionId = String(session?.sessionId || "").trim();
    const externalChatId = String(session?.externalChatId || "").trim();
    const transportExternalChatId = String(session?.transportExternalChatId || "").trim();
    const derivedExternalChatId = externalChatIdFromSessionId(sessionId);
    return [
      sessionId,
      externalChatId,
      transportExternalChatId,
      derivedExternalChatId,
    ].filter(Boolean);
  }

  function isDeletedSessionTombstoned(session: SessionIdentity | null | undefined): boolean {
    return sessionTombstoneKeys(session).some((key) => deletedSessionTombstones.has(key));
  }

  function isDeletedSessionIdentity(identity: DeletedSessionIdentity = {}): boolean {
    return isDeletedSessionTombstoned({
      sessionId: identity.sessionId,
      externalChatId: identity.externalChatId,
      transportExternalChatId: identity.transportExternalChatId,
    });
  }

  function rememberDeletedSession(session: SessionIdentity | null | undefined): void {
    for (const key of sessionTombstoneKeys(session)) {
      const existingTimer = deletedSessionTombstones.get(key);
      if (existingTimer) {
        clearTimeout(existingTimer);
      }
      const timer = window.setTimeout(() => {
        deletedSessionTombstones.delete(key);
      }, DELETED_SESSION_TOMBSTONE_MS);
      deletedSessionTombstones.set(key, timer);
    }
  }

  function rememberDeletedSessions(sessions: SessionIdentity[]): void {
    for (const session of sessions) {
      rememberDeletedSession(session);
    }
  }

  function forgetDeletedSession(session: SessionIdentity | null | undefined): void {
    for (const key of sessionTombstoneKeys(session)) {
      const timer = deletedSessionTombstones.get(key);
      if (timer) {
        clearTimeout(timer);
      }
      deletedSessionTombstones.delete(key);
    }
  }

  function sessionMatchesDeleteSets(session: SessionIdentity, externalChatIds: Set<string>, sessionIds: Set<string>): boolean {
    return sessionTombstoneKeys(session).some((key) => {
      return externalChatIds.has(key) || sessionIds.has(key) || deletedSessionTombstones.has(key);
    });
  }

  function isNonEmptyString(value: string | null | undefined): value is string {
    return typeof value === "string" && value.length > 0;
  }

  function reconnectSocketSoon(): void {
    disconnectSocket(copy.value.notices.refreshConnection, "info", { manual: false });
    window.setTimeout(() => {
      if (clientDisposed || state.authRequired) {
        return;
      }
      connectSocket();
    }, 0);
  }

  function ensureActiveAfterSessionRemoval(preferWeb = false): void {
    if (state.sessions.some((session) => session.externalChatId === state.activeExternalChatId)) {
      writeStoredValue(STORAGE_KEYS.activeExternalChatId, state.activeExternalChatId);
      return;
    }
    let nextSession = preferWeb ? getFirstWebSession() : state.sessions[0];
    if (!nextSession) {
      nextSession = createSession();
      state.sessions.unshift(nextSession);
    }
    state.activeExternalChatId = nextSession.externalChatId;
    writeStoredValue(STORAGE_KEYS.activeExternalChatId, nextSession.externalChatId);
    persistLocalDraftSessions();
  }

  function removeSessionsFromState(
    predicate: (session: ChatSession) => boolean,
    { preferWeb = false }: { preferWeb?: boolean } = {},
  ): number {
    const removed = state.sessions.filter(predicate);
    for (const session of removed) {
      clearSessionRunTimers(session);
    }
    state.sessions = state.sessions.filter((session) => !predicate(session));
    ensureActiveAfterSessionRemoval(preferWeb);
    persistLocalDraftSessions();
    scrollMessagesToBottom({ force: true });
    return removed.length;
  }

  async function deleteSessions(sessions: ChatSession[]): Promise<void> {
    const targets = Array.isArray(sessions) ? sessions.filter(isChatSession) : [];
    if (targets.length === 0) {
      return;
    }

    rememberDeletedSessions(targets);
    const targetExternalChatIds = new Set<string>(targets.map((session) => session.externalChatId).filter(isNonEmptyString));
    const targetSessionIds = new Set<string>(targets.map((session) => getSessionOwnerId(session) || session.sessionId).filter(isNonEmptyString));
    const activeSessionId = getSessionOwnerId(currentSession.value) || currentSession.value?.sessionId || "";
    const deletesActiveSession = targets.some((session) => {
      const sessionId = getSessionOwnerId(session) || session.sessionId || "";
      return session.externalChatId === state.activeExternalChatId || (activeSessionId && sessionId === activeSessionId);
    });
    removeSessionsFromState((candidate) => sessionMatchesDeleteSets(candidate, targetExternalChatIds, targetSessionIds));
    if (deletesActiveSession) {
      reconnectSocketSoon();
    }

    const deletedSessions: ChatSession[] = [];
    const deletedExternalChatIds = new Set<string>();
    const deletedSessionIds = new Set<string>();
    const failedSessions: ChatSession[] = [];
    let failureCount = 0;
    let lastError = "";
    for (const session of targets) {
      const sessionId = session.sessionId ? getSessionOwnerId(session) : "";
      if (!sessionId) {
        deletedSessions.push(session);
        deletedExternalChatIds.add(session.externalChatId);
        continue;
      }
      try {
        await requestSettingsJson(buildSessionDeletePath(sessionId), { method: "DELETE" });
        deletedSessions.push(session);
        deletedExternalChatIds.add(session.externalChatId);
        deletedSessionIds.add(sessionId);
      } catch (error: unknown) {
        if (settingsErrorStatus(error) === 404) {
          deletedSessions.push(session);
          deletedExternalChatIds.add(session.externalChatId);
          deletedSessionIds.add(sessionId);
          continue;
        }
        failureCount += 1;
        failedSessions.push(session);
        lastError = settingsErrorMessage(error, copy.value.notices.sessionDeleteFailed);
      }
    }

    if (deletedExternalChatIds.size > 0) {
      removeSessionsFromState((candidate) => sessionMatchesDeleteSets(candidate, deletedExternalChatIds, deletedSessionIds));
    }

    if (failureCount > 0) {
      for (const session of failedSessions) {
        forgetDeletedSession(session);
      }
      await loadSessionHistory({ quiet: true });
      const message = deletedExternalChatIds.size > 0
        ? copy.value.notices.sessionsDeletedWithFailures(deletedExternalChatIds.size, failureCount)
        : lastError;
      setNotice(message || copy.value.notices.sessionDeleteFailed, "warning");
      return;
    }

    if (deletedSessions.length > 0) {
      await loadSessionHistory({ quiet: true, pruneMissingHistorySessions: true });
    }
    setNotice(copy.value.notices.sessionsDeleted(deletedExternalChatIds.size), "success");
  }

  async function deleteSession(session: ChatSession | null | undefined): Promise<void> {
    await deleteSessions(session ? [session] : []);
  }

  async function clearWebSessions(): Promise<void> {
    try {
      const payload = toSessionClearPayload(
        await requestSettingsJson(buildSessionsClearPath("web"), { method: "DELETE" }),
      );
      const clearResult = normalizeSessionClearPayload(payload);
      rememberDeletedSessions(state.sessions.filter((session) => !session.channel || session.channel === "web"));
      removeSessionsFromState((session) => !session.channel || session.channel === "web", { preferWeb: true });
      reconnectSocketSoon();
      await loadSessionHistory({ quiet: true, pruneMissingHistorySessions: true });
      setNotice(copy.value.notices.sessionsCleared(clearResult.deleted), "success");
    } catch (error: unknown) {
      setNotice(settingsErrorMessage(error, copy.value.notices.sessionDeleteFailed), "warning");
    }
  }

  function saveConnectionSettings(): void {
    const nextWsUrl = settingsForm.wsUrl.trim() || DEFAULT_WS_URL;
    const nextAccessToken = settingsForm.accessToken.trim();
    const shouldReconnect = (state.wsUrl !== nextWsUrl || state.accessToken !== nextAccessToken) && activeSocket && state.connectionState !== "disconnected";

    state.wsUrl = nextWsUrl;
    state.accessToken = nextAccessToken;
    state.displayName = settingsForm.displayName.trim() || "Local browser";
    saveRunPanelVisibilitySettings(
      settingsForm.showRunHistory,
      settingsForm.showRunTimeline,
      settingsForm.showRunSummary,
      settingsForm.showRunTrace,
    );

    const requestedExternalChatId = settingsForm.externalChatId.trim();
    if (requestedExternalChatId) {
      ensureSession(requestedExternalChatId, "", { allowDeleted: true });
      state.activeExternalChatId = requestedExternalChatId;
    } else {
      const session = createSession();
      state.sessions.unshift(session);
      state.activeExternalChatId = session.externalChatId;
      settingsForm.externalChatId = session.externalChatId;
    }
    persistLocalDraftSessions();

    writeStoredValue(STORAGE_KEYS.wsUrl, state.wsUrl);
    writeStoredValue(STORAGE_KEYS.accessToken, state.accessToken);
    writeStoredValue(STORAGE_KEYS.displayName, state.displayName);
    writeStoredValue(STORAGE_KEYS.activeExternalChatId, state.activeExternalChatId);
    settingsForm.wsUrl = state.wsUrl;
    settingsForm.accessToken = state.accessToken;
    settingsForm.displayName = state.displayName;
    settingsForm.externalChatId = state.activeExternalChatId;
    void loadCommandCatalog();

    if (shouldReconnect) {
      connectSocket();
    }
  }

  function submitAccessToken(): void {
    const nextAccessToken = settingsForm.accessToken.trim();
    state.accessToken = nextAccessToken;
    writeStoredValue(STORAGE_KEYS.accessToken, state.accessToken);
    settingsForm.accessToken = state.accessToken;
    state.authError = "";
    state.authRequired = false;
    void loadCommandCatalog();
    connectSocket();
  }

  function toggleSettingsConnection(shouldConnect: boolean): void {
    if (shouldConnect) {
      saveConnectionSettings();
      connectSocket();
      return;
    }
    autoReconnectEnabled = false;
    disconnectSocket(copy.value.notices.disconnectedManual, "warning");
  }

  async function cancelRun(run: RunViewState | null | undefined): Promise<void> {
    const session = currentSession.value;
    if (!session || !run?.runId || run.status !== "running") {
      return;
    }
    const sessionId = getSessionApiId(session);
    if (!sessionId) {
      setNotice(copy.value.notices.sessionNotReady, "warning");
      return;
    }

    run.cancelPending = true;
    try {
      const response = await fetch(buildRunCancelUrl(state.wsUrl, run.runId, sessionId), {
        method: "POST",
        headers: authorizedHeaders(),
      });
      if (!response.ok) {
        throw new Error(`Cancel request failed with HTTP ${response.status}`);
      }
      setNotice(copy.value.notices.cancelRequested(run.runId), "warning");
    } catch (error: unknown) {
      setNotice(settingsErrorMessage(error, copy.value.notices.cancelFailed), "error");
    } finally {
      run.cancelPending = false;
    }
  }

  async function revertRunFileChange(
    run: RunViewState | null | undefined,
    change: TraceFileChangeView | null | undefined,
  ): Promise<RunFileChangeRevertRecord | null> {
    const sessionId = String(run?.sessionId || currentSession.value?.sessionId || "").trim();
    const changeId = String(change?.changeId || change?.sourceId || "").trim();
    if (!run?.runId || !sessionId || !changeId) {
      setNotice(copy.value.runFileInspector.revertUnavailable, "warning");
      return null;
    }

    try {
      const payload = toRunFileChangeRevertPayload(
        await requestSettingsJson(buildRunFileChangeRevertPath(run.runId, sessionId, changeId), {
          method: "POST",
          body: JSON.stringify({ dry_run: false }),
        }),
      );
      const revertResult = normalizeRunFileChangeRevertPayload(payload);
      const revert = revertResult.revert;
      if (!revertResult.applied) {
        setNotice(revertResult.reason || copy.value.runFileInspector.revertUnavailable, "warning");
        return revert;
      }
      setNotice(copy.value.runFileInspector.revertApplied(String(change?.path || "")), "success");
      await loadRunTrace(currentSession.value, run);
      return revert;
    } catch (error: unknown) {
      setNotice(settingsErrorMessage(error, copy.value.runFileInspector.revertFailed), "error");
      return null;
    }
  }

  async function cleanupWorktreeSandbox(run: RunViewState | null | undefined): Promise<WorktreeCleanupRecord | null> {
    const sandbox = run?.worktreeSandbox;
    const sandboxPath = String(sandbox?.sandboxPath || "").trim();
    if (!sandbox || !sandboxPath || !sandbox.cleanupSupported) {
      setNotice(copy.value.notices.worktreeCleanupUnavailable, "warning");
      return null;
    }
    if (sandbox.cleanupPending) {
      return null;
    }
    if (typeof window !== "undefined" && !window.confirm(copy.value.runSummary.confirmCleanupSandbox(sandboxPath))) {
      return null;
    }

    sandbox.cleanupPending = true;
    try {
      const payload = toWorktreeCleanupPayload(
        await requestSettingsJson(buildWorktreeCleanupPath(), {
          method: "POST",
          body: JSON.stringify({
            sandbox_path: sandboxPath,
            session_id: run?.sessionId || currentSession.value?.sessionId || "",
            run_id: run?.runId || "",
          }),
        }),
      );
      const cleanupResult = normalizeWorktreeCleanupPayload(payload);
      const cleanup = cleanupResult.cleanup;
      sandbox.cleanupResult = cleanup;
      if (!cleanupResult.ok) {
        setNotice(cleanupResult.reason || copy.value.notices.worktreeCleanupFailed, "warning");
        return cleanup;
      }
      sandbox.status = cleanupResult.status || "removed";
      sandbox.cleanupSupported = false;
      setNotice(copy.value.notices.worktreeCleanupApplied, "success");
      if (currentSession.value) {
        await loadRunTrace(currentSession.value, run);
      }
      return cleanup;
    } catch (error: unknown) {
      setNotice(settingsErrorMessage(error, copy.value.notices.worktreeCleanupFailed), "error");
      return null;
    } finally {
      sandbox.cleanupPending = false;
    }
  }

  function normalizeOutgoingMessage(rawValue: unknown): OutgoingMessagePayload {
    const rawRecord = toOutgoingMessageInputPayload(rawValue);
    if (rawRecord) {
      return {
        text: rawRecord.text,
        metadata: rawRecord.metadata,
      };
    }
    return { text: String(rawValue || "").trim(), metadata: {} };
  }

  function sendMessageText(rawText: unknown, { clearComposer = false }: SendMessageOptions = {}): boolean {
    const payload = normalizeOutgoingMessage(rawText);
    const text = payload.text;
    if (!text) {
      return false;
    }

    if (!activeSocket || activeSocket.readyState !== WebSocket.OPEN) {
      if (state.connectionState === "connecting") {
        setNotice(copy.value.notices.stillConnecting, "info");
        return false;
      }
      setNotice(copy.value.notices.inactiveConnection, "warning");
      openSettings("general");
      return false;
    }

    const session = currentSession.value;
    if (!session) {
      return false;
    }
    if (session.channel !== "web") {
      setNotice(copy.value.composer.readOnlyChannel(session.channel), "info");
      return false;
    }

    addMessage(session.externalChatId, makeMessage("user", text, state.displayName || "Local browser"));
    const outgoingMetadata: OutgoingMessageMetadata = {
      overlay_profile_id: overlayProfileId.value,
      ...payload.metadata,
    };
    activeSocket.send(
      JSON.stringify({
        external_chat_id: session.externalChatId,
        ...(session.sessionId ? { session_id: session.sessionId } : {}),
        sender_name: state.displayName,
        text,
        metadata: outgoingMetadata,
      }),
    );

    if (clearComposer) {
      messageText.value = "";
      resizeComposer();
    }
    scrollMessagesToBottom({ force: true });
    return true;
  }

  function submitMessage(event: ComposerSubmitEvent): void {
    event.preventDefault();
    sendMessageText(messageText.value, { clearComposer: true });
  }

  function handleComposerKeydown(event: ComposerKeyboardEvent): void {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      submitMessage(event);
    }
  }

  function applyPrompt(text: string): void {
    messageText.value = text;
    runAfterCurrentMicrotask(() => {
      resizeComposer();
      messageInput?.focus();
    });
  }

  function applyCommandHint(command: CommandCatalogItem): void {
    const token = String(command.command || "").trim();
    if (!token) {
      return;
    }
    messageText.value = `${token} `;
    runAfterCurrentMicrotask(() => {
      resizeComposer();
      messageInput?.focus();
    });
  }

  async function initializeClient(): Promise<void> {
    await loadSessionHistory();
    if (clientDisposed) {
      return;
    }
    if (state.authRequired) {
      return;
    }
    void loadCommandCatalog();
    persistActiveSession();
    connectSocket();
  }

  function handleGlobalKeydown(event: KeyboardEvent): void {
    const pressedSettingsShortcut = event.key === "," && (event.ctrlKey || event.metaKey);
    if (pressedSettingsShortcut) {
      event.preventDefault();
      openSettings("general");
      return;
    }

    if (event.key === "Escape") {
      closeSettings();
      closeSidebar();
    }
  }

  onMounted(() => {
    addColorSchemeListener();
    applyDocumentPreferences();
    document.addEventListener("keydown", handleGlobalKeydown);
    resizeComposer();
    scrollMessagesToBottom({ force: true });
    initializeClient();
  });

  onBeforeUnmount(() => {
    clientDisposed = true;
    for (const timer of runSummaryTimers.values()) {
      clearTimeout(timer);
    }
    runSummaryTimers.clear();
    runBackfillTimes.clear();
    clearProviderAuthPollTimers();
    clearGatewayReconnectTimer();
    clearSessionHistoryRefreshTimer();
    for (const timer of toastTimers.values()) {
      clearTimeout(timer);
    }
    toastTimers.clear();
    for (const timer of deletedSessionTombstones.values()) {
      clearTimeout(timer);
    }
    deletedSessionTombstones.clear();
    removeColorSchemeListener();
    document.removeEventListener("keydown", handleGlobalKeydown);
    document.body.classList.remove("settings-open", "sidebar-open");
    detachMessageStageScrollListener(boundMessageStage);
    if (activeSocket && activeSocket.readyState !== WebSocket.CLOSED) {
      activeSocket.close(1000, "Client disconnect");
    }
    activeSocket = null;
  });

  return {
    copy,
    prompts,
    state,
    sidebarSessions,
    sidebarSessionTotal,
    webSessionCount,
    sessionChannelFilter,
    showHiddenSessions,
    messageText,
    messageInput,
    messageStage,
    sidebarOpen,
    sidebarCollapsed,
    traceInspectorCollapsed,
    settingsOpen,
    settingsSection,
    settingsForm,
    settingsState,
    toasts,
    currentEntries,
    currentMessages,
    currentRuns,
    currentRunsLoading,
    currentRunsError,
    currentRun,
    currentRunTimeline,
    currentRunSummary,
    settingsTitle,
    sessionMeta,
    runtimeHint,
    composerHint,
    commandHints,
    currentSessionReadOnly,
    sendDisabled,
    setMessageInputRef,
    setMessageStageRef,
    setMessageText,
    getSessionDisplayId,
    getSessionTitle,
    setActiveSession,
    setSessionChannelFilter,
    setShowHiddenSessions,
    selectRun,
    selectSettingsSection,
    openSettings,
    closeSettings,
    saveConnectionSettings,
    submitAccessToken,
    loadProviderSettings,
    loadProviderAuthStatusById,
    loadUpdateStatus,
    loadModelSettings,
    loadChannelSettings,
    loadScheduleSettings,
    loadNetworkSettings,
    loadSearchSettings,
    loadSearxngOptions,
    loadBrowserSettings,
    loadLogSettings,
    loadMcpSettings,
    loadCronJobs,
    beginChannelConnect,
    cancelChannelConnect,
    saveChannelConnection,
    disconnectChannel,
    beginProviderConnect,
    cancelProviderConnect,
    saveProviderConnection,
    disconnectProvider,
    setProviderCredential,
    deleteCredential,
    connectOAuthProvider,
    startProviderAuthLoginById,
    logoutProviderAuthById,
    runUpdate,
    selectModel,
    saveMediaModel,
    beginMcpEdit,
    beginMcpCreate,
    cancelMcpEdit,
    saveMcpServer,
    removeMcpServer,
    reloadMcpSettings,
    toggleMcpAdvanced,
    toggleMcpJsonInput,
    toggleMcpToolGroup,
    applyMcpJson,
    saveScheduleSettings,
    saveNetworkSettings,
    saveSearchSettings,
    saveBrowserSettings,
    runBrowserTest,
    runBrowserDoctor,
    runBrowserInstall,
    saveLogSettings,
    beginCronJobEdit,
    beginCronJobCreate,
    cancelCronJobEdit,
    saveCronJob,
    runCronJobAction,
    toggleSidebar,
    toggleSidebarCollapsed,
    toggleTraceInspectorCollapsed,
    connectSocket,
    resizeComposer,
    createNewChat,
    deleteSessions,
    deleteSession,
    clearWebSessions,
    cancelRun,
    revertRunFileChange,
    cleanupWorktreeSandbox,
    toggleSettingsConnection,
    submitMessage,
    handleComposerKeydown,
    applyPrompt,
    applyCommandHint,
    dismissToast,
  };
}
