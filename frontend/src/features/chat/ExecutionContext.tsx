import { useEffect, useId, useMemo, useRef, useState } from "react";
import { DownOutlined, LeftOutlined, RightOutlined } from "@ant-design/icons";
import { Button } from "antd";

import { AgentChatApiError, agentChatErrorText, type RunEvent, type RunSnapshot } from "../../api/agentChat";
import type { MessageKey, Translator } from "../../i18n/catalog";
import { useI18n } from "../../i18n/I18nProvider";
import type { TimeZoneSetting } from "../../api/generalSettings";
import { formatTime } from "../general-settings/dateTime";


function OpenSpriteMark() {
  return <span aria-hidden="true" className="chat-workspace__mark chat-workspace__mark--small" />;
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
    case "model.started": return t("execution.event.modelStarted", { model: String(event.data.modelId ?? "") }).trim();
    case "assistant.delta": return null;
    case "tool.started": return t("execution.event.toolStarted", { tool: String(event.data.toolName ?? "") }).trim();
    case "tool.completed": return t("execution.event.toolCompleted", { tool: String(event.data.toolName ?? "") }).trim();
    case "tool.failed": return t("execution.event.toolFailed", { tool: String(event.data.toolName ?? "") }).trim();
    case "run.completed": return t("execution.event.runCompleted");
    case "run.failed": return t("execution.event.runFailed");
    case "run.cancelled": return t("execution.event.runCancelled");
    case "run.interrupted": return t("execution.event.runInterrupted");
  }
}

function processEvents(events: RunEvent[], t: Translator, locale: string, timeZone: TimeZoneSetting): Array<{ key: string; label: string; time: string; state: "complete" | "active" | "error" }> {
  const steps: Array<{ key: string; label: string; time: string; state: "complete" | "active" | "error" }> = [];
  let addedTextStep = false;
  for (const event of events) {
    if (event.type === "assistant.delta") {
      if (!addedTextStep) {
        addedTextStep = true;
        steps.push({ key: "assistant-output", label: t("execution.event.output"), time: formatTime(event.createdAt, locale, timeZone), state: "active" });
      }
      continue;
    }
    const label = eventLabel(event, t);
    if (!label) continue;
    const terminalError = event.type === "run.failed" || event.type === "run.interrupted" || event.type === "tool.failed";
    steps.push({ key: `${event.sequence}-${event.type}`, label, time: formatTime(event.createdAt, locale, timeZone), state: terminalError ? "error" : "complete" });
  }
  if (steps.length > 0 && !events.some((event) => ["run.completed", "run.failed", "run.cancelled", "run.interrupted"].includes(event.type))) {
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
};

export function ExecutionContext({ modelName, run, events, timeZone, historical = false, loading = false, error = null, onRetry, onReturnToLatest, inspectionRunId = null }: ExecutionContextProps) {
  const { locale, t } = useI18n();
  const [isExpanded, setIsExpanded] = useState(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return true;
    return !window.matchMedia("(max-width: 767px)").matches;
  });
  const contextRef = useRef<HTMLElement>(null);
  const contextId = useId();
  const executionTitleId = `${contextId}-execution-title`;
  const executionBodyId = `${contextId}-execution-body`;
  const steps = useMemo(() => processEvents(events, t, locale, timeZone), [events, locale, t, timeZone]);
  const toolNames = useMemo(() => Array.from(new Set(events.filter((event) => event.type.startsWith("tool.")).map((event) => String(event.data.toolName ?? "")).filter(Boolean))), [events]);
  const status = run ? t(statusKeys[run.status]) : t("execution.status.none");
  const title = t(historical ? "execution.detailsTitle" : "execution.title");

  useEffect(() => {
    if (!historical || inspectionRunId === null) return;
    setIsExpanded(true);
    if (typeof window.matchMedia !== "function" || !window.matchMedia("(max-width: 767px)").matches) return;
    window.requestAnimationFrame(() => {
      const behavior = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
      contextRef.current?.scrollIntoView?.({ behavior, block: "start" });
    });
  }, [historical, inspectionRunId]);

  return (
    <aside ref={contextRef} className={`chat-workspace__context${isExpanded ? "" : " chat-workspace__context--collapsed"}`} aria-labelledby={executionTitleId} aria-busy={historical && loading}>
      <div className="chat-workspace__context-heading">
        <Button
          type="default"
          className="chat-workspace__context-toggle"
          icon={isExpanded ? <RightOutlined /> : <LeftOutlined />}
          aria-expanded={isExpanded}
          aria-controls={executionBodyId}
          aria-label={isExpanded ? t(historical ? "execution.collapseDetails" : "execution.collapse") : t(historical ? "execution.expandDetails" : "execution.expand")}
          title={isExpanded ? t(historical ? "execution.collapseDetails" : "execution.collapse") : t(historical ? "execution.expandDetails" : "execution.expand")}
          onClick={() => setIsExpanded((current) => !current)}
        />
        <h2 id={executionTitleId}>{title}</h2>
      </div>

      <div className="chat-workspace__context-summary" aria-hidden={isExpanded}>
        <span>{status}</span>
        <span>{run ? modelName : "—"}</span>
        <span>{steps.length}</span>
      </div>

      <div id={executionBodyId} className="chat-workspace__context-body" hidden={!isExpanded}>
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
            </section>

            <section className="chat-workspace__context-section" aria-labelledby={`${contextId}-tools-title`}>
              <h3 id={`${contextId}-tools-title`}>{t("execution.tools")}</h3>
              {toolNames.length > 0 ? (
                <ul className="chat-workspace__capability-list">
                  {toolNames.map((name) => <li key={name}><span className="chat-workspace__capability-icon" aria-hidden="true">⌘</span><span>{name}</span><i aria-label={t("execution.executed")} /></li>)}
                </ul>
              ) : <p className="chat-workspace__empty-tools">{t("execution.noTools")}</p>}
            </section>

            <section className="chat-workspace__context-section chat-workspace__execution-info" aria-labelledby={`${contextId}-info-title`}>
              <h3 id={`${contextId}-info-title`}>{t("execution.info")}</h3>
              <dl className="chat-workspace__stats">
                <div><dt>{t("execution.startTime")}</dt><dd>{formatTime(run.startedAt, locale, timeZone)}</dd></div>
                <div><dt>{t("execution.duration")}</dt><dd>{durationText(run)}</dd></div>
                <div><dt>{t("execution.events")}</dt><dd>{events.length}</dd></div>
                <div><dt>{t("execution.source")}</dt><dd>{t(historical ? "execution.history" : "execution.currentConversation")}</dd></div>
              </dl>
            </section>

            <details className="chat-workspace__record-details" open={run.status === "failed" || run.status === "interrupted"}>
              <summary><span>{t("execution.record")}</span><DownOutlined className="chat-workspace__record-chevron" /></summary>
              {steps.length > 0 ? (
                <ol className="chat-workspace__process-list" aria-label={t("execution.eventList")}>
                  {steps.map((step) => (
                    <li key={step.key} className={`chat-workspace__process-item chat-workspace__process-item--${step.state}`}>
                      <span className="chat-workspace__step-icon" aria-hidden="true">{step.state === "complete" ? "✓" : step.state === "error" ? "!" : ""}</span>
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
