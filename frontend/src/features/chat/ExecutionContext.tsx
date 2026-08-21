import { useId, useMemo, useState } from "react";

import type { RunEvent, RunSnapshot } from "../../api/agentChat";


function OpenSpriteMark() {
  return <span aria-hidden="true" className="chat-workspace__mark chat-workspace__mark--small" />;
}

const statusText: Record<RunSnapshot["status"], string> = {
  queued: "等待中",
  running: "執行中",
  cancelling: "停止中",
  completed: "已完成",
  failed: "失敗",
  cancelled: "已停止",
  interrupted: "已中斷",
};

const responseModeText: Record<RunSnapshot["responseMode"], string> = {
  default: "廠商預設",
  fast: "快速",
  balanced: "平衡",
  deep: "深入",
};

function timeText(value: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-TW", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(new Date(value));
}

function durationText(run: RunSnapshot | null): string {
  if (!run?.startedAt) return "—";
  const end = run.finishedAt ? new Date(run.finishedAt).getTime() : Date.now();
  const seconds = Math.max(0, Math.floor((end - new Date(run.startedAt).getTime()) / 1000));
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

function eventLabel(event: RunEvent): string | null {
  switch (event.type) {
    case "run.started": return "開始執行";
    case "model.started": return `請求模型 ${String(event.data.modelId ?? "")}`.trim();
    case "assistant.delta": return null;
    case "tool.started": return `執行工具 ${String(event.data.toolName ?? "")}`.trim();
    case "tool.completed": return `工具完成 ${String(event.data.toolName ?? "")}`.trim();
    case "tool.failed": return `工具失敗 ${String(event.data.toolName ?? "")}`.trim();
    case "run.completed": return "完成回覆";
    case "run.failed": return "執行失敗";
    case "run.cancelled": return "使用者停止執行";
    case "run.interrupted": return "本機服務中斷執行";
  }
}

function processEvents(events: RunEvent[]): Array<{ key: string; label: string; time: string; state: "complete" | "active" | "error" }> {
  const steps: Array<{ key: string; label: string; time: string; state: "complete" | "active" | "error" }> = [];
  let addedTextStep = false;
  for (const event of events) {
    if (event.type === "assistant.delta") {
      if (!addedTextStep) {
        addedTextStep = true;
        steps.push({ key: "assistant-output", label: "產生回覆", time: timeText(event.createdAt), state: "active" });
      }
      continue;
    }
    const label = eventLabel(event);
    if (!label) continue;
    const terminalError = event.type === "run.failed" || event.type === "run.interrupted" || event.type === "tool.failed";
    steps.push({ key: `${event.sequence}-${event.type}`, label, time: timeText(event.createdAt), state: terminalError ? "error" : "complete" });
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
};

export function ExecutionContext({ modelName, run, events }: ExecutionContextProps) {
  const [isExpanded, setIsExpanded] = useState(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return true;
    return !window.matchMedia("(max-width: 767px)").matches;
  });
  const contextId = useId();
  const executionTitleId = `${contextId}-execution-title`;
  const executionBodyId = `${contextId}-execution-body`;
  const steps = useMemo(() => processEvents(events), [events]);
  const toolNames = useMemo(() => Array.from(new Set(events.filter((event) => event.type.startsWith("tool.")).map((event) => String(event.data.toolName ?? "")).filter(Boolean))), [events]);
  const status = run ? statusText[run.status] : "尚未執行";

  return (
    <aside className={`chat-workspace__context${isExpanded ? "" : " chat-workspace__context--collapsed"}`} aria-labelledby={executionTitleId}>
      <div className="chat-workspace__context-heading">
        <button
          type="button"
          className="chat-workspace__context-toggle"
          aria-expanded={isExpanded}
          aria-controls={executionBodyId}
          aria-label={isExpanded ? "收合本次執行" : "展開本次執行"}
          title={isExpanded ? "收合本次執行" : "展開本次執行"}
          onClick={() => setIsExpanded((current) => !current)}
        >
          <span aria-hidden="true" className="chat-workspace__context-toggle-icon chat-workspace__context-toggle-icon--horizontal">{isExpanded ? "›" : "‹"}</span>
          <span aria-hidden="true" className="chat-workspace__context-toggle-icon chat-workspace__context-toggle-icon--vertical">{isExpanded ? "⌃" : "⌄"}</span>
        </button>
        <h2 id={executionTitleId}>本次執行</h2>
      </div>

      <div className="chat-workspace__context-summary" aria-hidden={isExpanded}>
        <span>{status}</span>
        <span>{run ? modelName : "—"}</span>
        <span>{steps.length}</span>
      </div>

      <div id={executionBodyId} className="chat-workspace__context-body" hidden={!isExpanded}>
        {run ? (
          <>
            <section className="chat-workspace__context-section" aria-labelledby={`${contextId}-model-title`}>
              <h3 id={`${contextId}-model-title`}>模型</h3>
              <div className="chat-workspace__model-card">
                <OpenSpriteMark />
                <span>{modelName}</span>
                <span className={`chat-workspace__run-pill chat-workspace__run-pill--${run.status}`}><i aria-hidden="true" />{status}</span>
              </div>
              <p className="chat-workspace__model-meta">{run.providerId} · {run.modelId} · {responseModeText[run.responseMode]}</p>
            </section>

            <section className="chat-workspace__context-section" aria-labelledby={`${contextId}-tools-title`}>
              <h3 id={`${contextId}-tools-title`}>工具</h3>
              {toolNames.length > 0 ? (
                <ul className="chat-workspace__capability-list">
                  {toolNames.map((name) => <li key={name}><span className="chat-workspace__capability-icon" aria-hidden="true">⌘</span><span>{name}</span><i aria-label="已執行" /></li>)}
                </ul>
              ) : <p className="chat-workspace__empty-tools">本次執行沒有使用額外工具。</p>}
            </section>

            <section className="chat-workspace__context-section chat-workspace__execution-info" aria-labelledby={`${contextId}-info-title`}>
              <h3 id={`${contextId}-info-title`}>執行資訊</h3>
              <dl className="chat-workspace__stats">
                <div><dt>開始時間</dt><dd>{timeText(run.startedAt)}</dd></div>
                <div><dt>執行時長</dt><dd>{durationText(run)}</dd></div>
                <div><dt>事件</dt><dd>{events.length}</dd></div>
                <div><dt>來源</dt><dd>對話紀錄</dd></div>
              </dl>
            </section>

            <details className="chat-workspace__record-details" open={run.status === "failed" || run.status === "interrupted"}>
              <summary><span>執行紀錄</span><span aria-hidden="true">⌄</span></summary>
              {steps.length > 0 ? (
                <ol className="chat-workspace__process-list" aria-label="執行事件">
                  {steps.map((step) => (
                    <li key={step.key} className={`chat-workspace__process-item chat-workspace__process-item--${step.state}`}>
                      <span className="chat-workspace__step-icon" aria-hidden="true">{step.state === "complete" ? "✓" : step.state === "error" ? "!" : ""}</span>
                      <span>{step.label}</span>
                      <time>{step.time}</time>
                    </li>
                  ))}
                </ol>
              ) : <p>等待執行事件。</p>}
              {run.error ? <p className="chat-workspace__record-error">{run.error.message}</p> : null}
            </details>
          </>
        ) : (
          <div className="chat-workspace__context-empty">
            <OpenSpriteMark />
            <p>送出訊息後，模型、狀態與實際執行事件會顯示在這裡。</p>
          </div>
        )}
      </div>
    </aside>
  );
}
