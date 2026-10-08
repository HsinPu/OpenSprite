import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { DownOutlined } from "@ant-design/icons";
import { BrandLogo } from "../../ui/BrandLogo";

import { AgentChatApiError, agentChatErrorText, type RunEvent, type RunSnapshot } from "../../api/agentChat";
import type { MessageKey, Translator } from "../../i18n/catalog";
import { useI18n } from "../../i18n/I18nProvider";
import type { TimeZoneSetting } from "../../api/generalSettings";
import type { WorkspaceAvailability } from "../../api/workspaces";
import { formatTime } from "../general-settings/dateTime";
import { formatTokenLimit } from "../ai-settings/contextBudget";
import { responseModeResolutionText } from "../ai-settings/ResponseModeHint";
import { RunDiagnostics } from "./RunDiagnostics";


function OpenSpriteMark() {
  return <BrandLogo className="chat-workspace__mark chat-workspace__mark--small" />;
}

const statusKeys: Record<RunSnapshot["status"], MessageKey> = {
  queued: "execution.status.queued",
  running: "execution.status.running",
  cancelling: "execution.status.cancelling",
  completed: "execution.status.completed",
  failed: "execution.status.failed",
  cancelled: "execution.status.cancelled",
  interrupted: "execution.status.interrupted",
};

const responseModeKeys: Record<RunSnapshot["responseMode"], MessageKey> = {
  default: "execution.mode.default",
  fast: "execution.mode.fast",
  balanced: "execution.mode.balanced",
  deep: "execution.mode.deep",
  low: "models.response.low",
  medium: "models.response.medium",
  high: "models.response.high",
  xhigh: "models.response.xhigh",
  max: "models.response.max",
  ultra: "models.response.ultra",

};

function durationText(run: RunSnapshot | null): string {
  if (!run?.startedAt) return "—";
  const end = run.finishedAt ? new Date(run.finishedAt).getTime() : Date.now();
  const seconds = Math.max(0, Math.floor((end - new Date(run.startedAt).getTime()) / 1000));
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

function eventLabel(event: RunEvent, t: Translator): string | null {
  switch (event.type) {
    case "run.started": return t("execution.event.runStarted");
    case "execution.selected": return t("execution.event.executionSelected", { loop: `${event.data.loopId} ${event.data.loopVersion}`, policy: `${event.data.policyId} ${event.data.policyVersion}` });
    case "context.compaction.started": return t("execution.event.contextCompactionStarted");
    case "context.compaction.completed": return t("execution.event.contextCompactionCompleted");
    case "context.compaction.failed": return t("execution.event.contextCompactionFailed");
    case "context.compaction.cancelled": return t("execution.event.contextCompactionCancelled");
    case "model.started": return t("execution.event.modelStarted", { model: String(event.data.modelId ?? "") }).trim();
    case "response.continuation.started": return t("execution.event.continuationStarted", { attempt: String(event.data.attempt ?? ""), maximum: event.data.maxAttempts === null ? "∞" : String(event.data.maxAttempts ?? "") });
    case "assistant.delta": return null;
    case "model.attempt": return null;
    case "run.completed": return t(
      event.data.completionReason === "output_limit"
        ? "execution.event.outputLimit"
        : event.data.completionReason === "context_limit"
          ? "execution.event.contextLimit"
          : "execution.event.runCompleted",
    );
    case "run.failed": return t("execution.event.runFailed");
    case "run.cancelled": return t("execution.event.runCancelled");
    case "run.interrupted": return t("execution.event.runInterrupted");
  }
}

function processEvents(events: RunEvent[], t: Translator, locale: string, timeZone: TimeZoneSetting, runStatus?: RunSnapshot["status"]): Array<{ key: string; label: string; time: string; state: "complete" | "active" | "error" | "unknown" }> {
  const steps: Array<{ key: string; label: string; time: string; state: "complete" | "active" | "error" | "unknown" }> = [];
  let addedTextStep = false;
  const compactions = new Map<string, number>();
  const terminal = (runStatus !== undefined && ["completed", "failed", "cancelled", "interrupted"].includes(runStatus)) || events.some((event) => ["run.completed", "run.failed", "run.cancelled", "run.interrupted"].includes(event.type));
  for (const event of events) {
    if (event.type === "assistant.delta") {
      if (!addedTextStep) {
        addedTextStep = true;
        steps.push({ key: "assistant-output", label: t("execution.event.output"), time: formatTime(event.createdAt, locale, timeZone), state: "active" });
      }
      continue;
    }
    if (event.type === "context.compaction.started") {
      const id = String(event.data.compactionId ?? `legacy-${event.sequence}`);
      compactions.set(id, steps.length);
      steps.push({ key: `compaction-${id}`, label: t(terminal || !event.data.compactionId ? "execution.event.contextCompactionUnknown" : "execution.event.contextCompactionStarted"), time: formatTime(event.createdAt, locale, timeZone), state: terminal || !event.data.compactionId ? "unknown" : "active" });
      continue;
    }
    if (event.type.startsWith("context.compaction.")) {
      const index = compactions.get(String(event.data.compactionId));
      const step = { key: `compaction-${String(event.data.compactionId)}`, label: eventLabel(event, t)!, time: formatTime(event.createdAt, locale, timeZone), state: event.type === "context.compaction.completed" ? "complete" as const : event.type === "context.compaction.failed" ? "error" as const : "unknown" as const };
      if (index !== undefined) steps[index] = step;
      else steps.push(step);
      continue;
    }
    const label = eventLabel(event, t);
    if (!label) continue;
    const terminalError = event.type === "run.failed" || event.type === "run.interrupted";
    steps.push({ key: `${event.sequence}-${event.type}`, label, time: formatTime(event.createdAt, locale, timeZone), state: terminalError ? "error" : "complete" });
  }
  if (steps.length > 0 && !terminal && !steps[steps.length - 1]!.key.startsWith("compaction-")) {
    steps[steps.length - 1] = { ...steps[steps.length - 1]!, state: "active" };
  }
  return steps;
}

type ExecutionContextProps = {
  modelName: string;
  run: RunSnapshot | null;
  events: RunEvent[];
  timeZone: TimeZoneSetting;
  historical?: boolean;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  onReturnToLatest?: () => void;
  inspectionRunId?: string | null;
  defaultExpanded: boolean;
  mode?: "sidebar" | "drawer";
  expanded?: boolean;
  onExpandedChange?: (expanded: boolean) => void;
  bodyId?: string;
};

export function ExecutionContext({ modelName, run, events, timeZone, historical = false, loading = false, error = null, onRetry, onReturnToLatest, inspectionRunId = null, defaultExpanded, mode = "sidebar", expanded, onExpandedChange, bodyId }: ExecutionContextProps) {
  const { locale, t } = useI18n();
  const isDrawerMode = mode === "drawer";
  const [internalExpanded, setInternalExpanded] = useState(defaultExpanded);
  const isExpanded = expanded ?? internalExpanded;
  const setExpanded = useCallback((nextExpanded: boolean) => {
    if (expanded === undefined) setInternalExpanded(nextExpanded);
    onExpandedChange?.(nextExpanded);
  }, [expanded, onExpandedChange]);
  const previousDefaultExpandedRef = useRef(defaultExpanded);
  const wasHistoricalRef = useRef(false);
  const contextId = useId();
  const executionTitleId = `${contextId}-execution-title`;
  const executionBodyId = bodyId ?? `${contextId}-execution-body`;
  const executionProfile = events.find(event => event.type === "execution.selected")?.data;
  const steps = useMemo(() => processEvents(events, t, locale, timeZone, run?.status), [events, locale, t, timeZone, run?.status]);
  const maxOutputTokens = useMemo(() => {
    const event = [...events].reverse().find((item) => item.type === "model.started");
    return typeof event?.data.maxOutputTokens === "number" ? event.data.maxOutputTokens : null;
  }, [events]);
  const workspaceAvailability = useMemo(() => {
    const value = events.find((event) => event.type === "run.started")?.data.workspaceAvailability;
    return ["available", "unavailable", "not_applicable"].includes(String(value))
      ? value as WorkspaceAvailability
      : null;
  }, [events]);
  const status = run
    ? t(run.completionReason === "output_limit" ? "execution.status.outputLimit" : run.completionReason === "context_limit" ? "execution.status.contextLimit" : statusKeys[run.status])
    : t("execution.status.none");
  const title = t(historical ? "execution.detailsTitle" : "execution.title");

  useEffect(() => {
    const defaultChanged = previousDefaultExpandedRef.current !== defaultExpanded;
    const returnedToLatest = wasHistoricalRef.current && !historical;
    const enteredHistorical = historical && inspectionRunId !== null && !wasHistoricalRef.current;
    previousDefaultExpandedRef.current = defaultExpanded;

    if (enteredHistorical) {
      setExpanded(true);
    } else if (defaultChanged || returnedToLatest) {
      setExpanded(defaultExpanded);
    }
    wasHistoricalRef.current = historical;
  }, [defaultExpanded, historical, inspectionRunId, setExpanded]);

  return (
    <aside className={`chat-workspace__context${isDrawerMode ? " chat-workspace__context--drawer" : isExpanded ? "" : " chat-workspace__context--collapsed"}`} aria-labelledby={isDrawerMode ? undefined : executionTitleId} aria-busy={historical && loading}>
      {!isDrawerMode ? <>
        <div className="chat-workspace__context-heading">
          <h2 id={executionTitleId}>{title}</h2>
        </div>

        <div className="chat-workspace__context-summary" aria-hidden={isExpanded}>
          <span>{status}</span>
          <span>{run ? modelName : "—"}</span>
          <span>{steps.length}</span>
        </div>
      </> : null}

      <div id={executionBodyId} className="chat-workspace__context-body" hidden={!isDrawerMode && !isExpanded}>
        {historical ? <div className="chat-workspace__history-toolbar"><span>{t("execution.historical")}</span><button type="button" onClick={onReturnToLatest}>{t("execution.backToLatest")}</button></div> : null}
        {historical && loading ? <div className="chat-workspace__context-message" role="status">{t("execution.loadingHistory")}</div> : historical && error ? <div className="chat-workspace__context-message chat-workspace__context-message--error" role="alert"><p>{error}</p>{onRetry ? <button type="button" onClick={onRetry}>{t("common.retry")}</button> : null}</div> : run ? (
          <>
            <section className="chat-workspace__context-section" aria-labelledby={`${contextId}-model-title`}>
              <h3 id={`${contextId}-model-title`}>{t("execution.model")}</h3>
              <div className="chat-workspace__model-card">
                <OpenSpriteMark />
                <span>{modelName}</span>
                <span className={`chat-workspace__run-pill chat-workspace__run-pill--${run.status}`}><i aria-hidden="true" />{status}</span>
              </div>
              <p className="chat-workspace__model-meta">{run.providerId} · {run.modelId} · {t(responseModeKeys[run.responseMode])}</p>
              {run.reasoningResolution ? <p className="chat-workspace__model-meta">{responseModeResolutionText(run.reasoningResolution, t)}</p> : null}
            </section>

            <section className="chat-workspace__context-section chat-workspace__execution-info" aria-labelledby={`${contextId}-info-title`}>
              <h3 id={`${contextId}-info-title`}>{t("execution.info")}</h3>
              <dl className="chat-workspace__stats">
                <div><dt>{t("execution.startTime")}</dt><dd>{formatTime(run.startedAt, locale, timeZone)}</dd></div>
                <div><dt>{t("execution.duration")}</dt><dd>{durationText(run)}</dd></div>
                <div><dt>{t("execution.events")}</dt><dd>{events.length}</dd></div>
                {executionProfile ? <div><dt>{t("diagnostics.executionPlugins")}</dt><dd>{`${executionProfile.loopId} ${executionProfile.loopVersion} / ${executionProfile.policyId} ${executionProfile.policyVersion}`}</dd></div> : null}
                {maxOutputTokens !== null ? <div><dt>{t("execution.maxOutputTokens")}</dt><dd>{formatTokenLimit(maxOutputTokens)}</dd></div> : null}
                {workspaceAvailability ? <div><dt>{t("execution.workspaceAvailability")}</dt><dd>{t(workspaceAvailability === "available" ? "workspaces.available" : workspaceAvailability === "unavailable" ? "workspaces.unavailable" : "workspaces.noRoot")}</dd></div> : null}
                <div><dt>{t("execution.source")}</dt><dd>{t(historical ? "execution.history" : "execution.currentConversation")}</dd></div>
              </dl>
            </section>

            <details className="chat-workspace__record-details" open={run.status === "failed" || run.status === "interrupted"}>
              <summary><span>{t("execution.record")}</span><span className="run-diagnostics__entry-actions"><RunDiagnostics key={run.id} runId={run.id} conversationId={run.conversationId} run={run} modelName={modelName} /><DownOutlined className="chat-workspace__record-chevron" /></span></summary>
              {steps.length > 0 ? (
                <ol className="chat-workspace__process-list" aria-label={t("execution.eventList")}>
                  {steps.map((step) => (
                    <li key={step.key} className={`chat-workspace__process-item chat-workspace__process-item--${step.state}`}>
                      <span className="chat-workspace__step-icon" aria-hidden="true">{step.state === "complete" ? "✓" : step.state === "error" ? "!" : step.state === "unknown" ? "—" : ""}</span>
                      <span>{step.label}</span>
                      <time>{step.time}</time>
                    </li>
                  ))}
                </ol>
              ) : <p>{t("execution.waitingEvents")}</p>}
              {run.error ? <p className="chat-workspace__record-error">{agentChatErrorText(new AgentChatApiError(run.error.code), t)}</p> : null}
            </details>
          </>
        ) : (
          <div className="chat-workspace__context-empty">
            <OpenSpriteMark />
            <p>{t("execution.empty")}</p>
          </div>
        )}
      </div>
    </aside>
  );
}
