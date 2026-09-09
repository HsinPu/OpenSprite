import { useCallback, useEffect, useRef, useState } from "react";

import {
  cancelSubagent,
  getSubagentResult,
  listSubagents,
  SubagentApiError,
  type SubagentResult,
  type SubagentStatus,
  type SubagentSummary,
} from "../../api/subagents";
import type { MessageKey } from "../../i18n/catalog";
import { useI18n } from "../../i18n/I18nProvider";
import "./SubagentExecution.css";

type SubagentExecutionProps = {
  parentRunId: string;
  parentActive: boolean;
  historical?: boolean;
};

type ResultState = {
  status: SubagentStatus;
  error: string | null;
  text: string;
  nextOffset: number | null;
  loading: boolean;
};

const statusKeys: Record<SubagentStatus, MessageKey> = {
  queued: "subagents.status.queued",
  running: "subagents.status.running",
  cancelling: "subagents.status.cancelling",
  completed: "subagents.status.completed",
  failed: "subagents.status.failed",
  cancelled: "subagents.status.cancelled",
  interrupted: "subagents.status.interrupted",
  timed_out: "subagents.status.timedOut",
};

function apiError(error: unknown): string {
  return error instanceof SubagentApiError ? error.code : error instanceof Error ? error.message : "network_error";
}

function activeStatus(status: SubagentStatus): boolean {
  return status === "queued" || status === "running" || status === "cancelling";
}

export function SubagentExecution({ parentRunId, parentActive, historical = false }: SubagentExecutionProps) {
  const { t } = useI18n();
  const [items, setItems] = useState<SubagentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, ResultState>>({});
  const generation = useRef(0);
  const listInFlight = useRef(false);
  const cancelInFlight = useRef(new Set<string>());
  const resultTokens = useRef(new Map<string, number>());

  const load = useCallback(async () => {
    if (listInFlight.current) return;
    listInFlight.current = true;
    const current = generation.current;
    try {
      const next = await listSubagents(parentRunId);
      if (current !== generation.current) return;
      setItems(next.items);
      setError(null);
    } catch (reason) {
      if (current === generation.current) setError(apiError(reason));
    } finally {
      if (current === generation.current) {
        setLoading(false);
        listInFlight.current = false;
      }
    }
  }, [parentRunId]);

  useEffect(() => {
    generation.current += 1;
    setItems([]);
    setResults({});
    setExpandedId(null);
    setError(null);
    setLoading(true);
    void load();
    return () => {
      generation.current += 1;
      // A run switch is allowed to start a request for the new parent while
      // the old parent's response is still pending. The generation guard
      // below discards that stale response, while clearing this gate prevents
      // it from blocking the new parent's initial load.
      listInFlight.current = false;
    };
  }, [load]);

  useEffect(() => {
    if (!parentActive || historical) return undefined;
    const timer = window.setInterval(() => { void load(); }, 2000);
    return () => window.clearInterval(timer);
  }, [historical, load, parentActive]);

  const requestResult = useCallback(async (childId: string, offset: number, append: boolean) => {
    const token = (resultTokens.current.get(childId) ?? 0) + 1;
    resultTokens.current.set(childId, token);
    const current = generation.current;
    setResults((previous) => ({
      ...previous,
      [childId]: { status: previous[childId]?.status ?? "running", error: null, text: append ? previous[childId]?.text ?? "" : "", nextOffset: previous[childId]?.nextOffset ?? null, loading: true },
    }));
    try {
      const next = await getSubagentResult(parentRunId, childId, offset);
      if (current !== generation.current || resultTokens.current.get(childId) !== token) return;
      setResults((previous) => {
        const old = previous[childId];
        return { ...previous, [childId]: { status: next.status, error: next.error, text: append && old?.text ? `${old.text}\n${next.text}` : next.text, nextOffset: next.nextOffset, loading: false } };
      });
    } catch (reason) {
      if (current !== generation.current || resultTokens.current.get(childId) !== token) return;
      setResults((previous) => ({ ...previous, [childId]: { ...(previous[childId] ?? { status: "running", error: null, text: "", nextOffset: null }), error: apiError(reason), loading: false } }));
    }
  }, [parentRunId]);

  const toggleExpanded = (item: SubagentSummary) => {
    if (expandedId === item.id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(item.id);
    if (!results[item.id]) void requestResult(item.id, 0, false);
  };

  const cancel = async (item: SubagentSummary) => {
    if (cancelInFlight.current.has(item.id) || !activeStatus(item.status) || item.status === "cancelling") return;
    cancelInFlight.current.add(item.id);
    setBusy(true); setError(null);
    const current = generation.current;
    try {
      const updated = await cancelSubagent(parentRunId, item.id);
      if (current === generation.current) setItems((previous) => previous.map((candidate) => candidate.id === updated.id ? updated : candidate));
    } catch (reason) {
      if (current === generation.current) setError(apiError(reason));
    } finally {
      cancelInFlight.current.delete(item.id);
      if (current === generation.current) setBusy(false);
    }
  };

  const retry = () => { setLoading(true); void load(); };

  return <section className="chat-workspace__context-section subagent-execution" aria-labelledby="subagent-execution-title">
    <h3 id="subagent-execution-title">{t("subagents.title")}</h3>
    {loading && items.length === 0 ? <p className="chat-workspace__context-message" role="status">{t("subagents.loading")}</p> : error && items.length === 0 ? <div className="chat-workspace__context-message chat-workspace__context-message--error" role="alert"><p>{t("subagents.error", { code: error })}</p><button type="button" onClick={retry}>{t("common.retry")}</button></div> : items.length === 0 ? <p className="chat-workspace__empty-tools">{t("subagents.empty")}</p> : <div className="subagent-execution__list">
      {items.map((item) => {
        const result = results[item.id];
        const expanded = expandedId === item.id;
        const canCancel = !historical && !busy && parentActive && activeStatus(item.status) && item.status !== "cancelling";
        return <article className="subagent-execution__card" key={item.id}>
          <div className="subagent-execution__card-heading">
            <button type="button" className="subagent-execution__expand" aria-expanded={expanded} aria-controls={`subagent-result-${item.id}`} onClick={() => toggleExpanded(item)}>
              <span className="subagent-execution__name">{item.name}</span>
              <span className="subagent-execution__model">{item.providerId} · {item.modelId}</span>
              <span className={`subagent-execution__status subagent-execution__status--${item.status}`}>{t(statusKeys[item.status])}</span>
            </button>
            {canCancel ? <button type="button" className="subagent-execution__cancel" disabled={busy} onClick={() => void cancel(item)}>{t("subagents.cancel")}</button> : null}
          </div>
          {item.errorCode ? <p className="subagent-execution__error">{t("subagents.errorCode", { code: item.errorCode })}</p> : null}
          {expanded ? <div id={`subagent-result-${item.id}`} className="subagent-execution__result" aria-busy={result?.loading ?? true}>
            {result?.loading && !result.text ? <p role="status">{t("subagents.resultLoading")}</p> : result?.error ? <div className="subagent-execution__result-error" role="alert"><p>{t("subagents.error", { code: result.error })}</p><button type="button" onClick={() => void requestResult(item.id, 0, false)}>{t("common.retry")}</button></div> : <>
              <pre>{result?.text ?? ""}</pre>
              {result?.nextOffset !== null && result?.nextOffset !== undefined ? <button type="button" disabled={result.loading} onClick={() => void requestResult(item.id, result.nextOffset!, true)}>{t("subagents.loadMore")}</button> : null}
              {!result?.text && !result?.loading ? <p>{t("subagents.noResult")}</p> : null}
            </>}
          </div> : null}
        </article>;
      })}
    </div>}
    {error && items.length > 0 ? <p className="subagent-execution__refresh-error" role="alert">{t("subagents.error", { code: error })}</p> : null}
  </section>;
}

export default SubagentExecution;
