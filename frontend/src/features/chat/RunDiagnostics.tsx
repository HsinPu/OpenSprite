import { useEffect, useRef, useState } from "react";
import { Alert, Badge, Button, Collapse, Descriptions, Drawer, Dropdown, Empty, Popover, Skeleton, Tooltip, Typography } from "antd";
import { FileSearchOutlined, MoreOutlined } from "@ant-design/icons";
import { AgentChatApiError, agentChatErrorText, listRunEventHistory, type RunEvent, type RunEventPage, type RunSnapshot } from "../../api/agentChat";
import { useI18n } from "../../i18n/I18nProvider";
import { diagnosticExport } from "./diagnosticExport";
import { diagnosticOperations, type DiagnosticOperation } from "./diagnosticOperations";
import "./RunDiagnostics.css";
import { PanelResizeHandle } from "../../ui/PanelResizeHandle";

type Props = { runId: string; conversationId: string; run?: RunSnapshot; modelName?: string };
const badgeStatus = (status: string) => status === "completed" ? "success" : status === "failed" || status === "interrupted" ? "error" : status === "started" || status === "running" ? "processing" : "default";

export function RunDiagnostics({ runId, conversationId, run, modelName }: Props) {
  const { t, locale } = useI18n();
  const [open, setOpen] = useState(false);
  const [preferredWidth, setPreferredWidth] = useState(560);
  const [viewport, setViewport] = useState(() => window.innerWidth);
  useEffect(() => {
    const resize = () => setViewport(window.innerWidth);
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);
  const mobile = viewport < 768;
  const maximumWidth = Math.max(360, viewport - 48);
  const drawerWidth = mobile ? viewport : Math.min(preferredWidth, maximumWidth);
  const [page, setPage] = useState<RunEventPage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exportError, setExportError] = useState(false);
  const [scopeOpen, setScopeOpen] = useState(false);
  const generation = useRef(0);
  const trigger = useRef<HTMLButtonElement>(null);
  const moreTrigger = useRef<HTMLButtonElement>(null);
  const scopeClose = useRef<HTMLButtonElement>(null);
  const closeScope = () => { setScopeOpen(false); moreTrigger.current?.focus(); };
  useEffect(() => {
    generation.current += 1;
    setOpen(false); setPage(null); setError(null); setLoading(false); setExportError(false); setScopeOpen(false);
    return () => { generation.current += 1; };
  }, [runId, conversationId]);

  async function load(next: number) {
    const current = ++generation.current;
    setLoading(true); setError(null);
    try {
      const result = await listRunEventHistory(runId, next);
      if (generation.current !== current) return;
      if (result.events.some(event => event.conversationId !== conversationId)) throw new Error("mismatched history");
      setPage(previous => ({ ...result, events: next === 0 ? result.events : [...(previous?.events ?? []), ...result.events] }));
    } catch (failure) {
      if (generation.current === current) setError(agentChatErrorText(failure, t));
    } finally { if (generation.current === current) setLoading(false); }
  }

  function download() {
    if (!page) return;
    let url: string | undefined;
    try {
      setExportError(false);
      url = URL.createObjectURL(new Blob([diagnosticExport(runId, page.events, 0, page.nextAfterSequence)], { type: "application/json" }));
      const link = document.createElement("a");
      link.href = url; link.download = `opensprite-diagnostics-${runId}.json`;
      link.click();
    } catch { setExportError(true); }
    finally { if (url) URL.revokeObjectURL(url); }
  }

  const rows = diagnosticOperations(page?.events ?? [], run?.status, page?.nextAfterSequence != null);
  const stageLabel = (event: RunEvent) => {
    const purpose = event.data.purpose;
    return event.type === "model.attempt" && (purpose === "main" || purpose === "continuation" || purpose === "compaction")
      ? `${t(`diagnostics.${purpose}`)} · ${t("diagnostics.attempt", { number: String(event.data.attemptNumber) })}` : t("diagnostics.operation");
  };
  const statusLabel = (value: string) => value === "started" || value === "completed" || value === "failed" || value === "cancelled" || value === "partial" || value === "missingEnd" ? t(`diagnostics.${value}`) : t("diagnostics.unknown");
  return <span className="run-diagnostics__entry" onClick={event => event.stopPropagation()}>
    <Tooltip title={t("diagnostics.open")}><Button ref={trigger} type="text" className="run-diagnostics__trigger" aria-label={t("diagnostics.open")} icon={<FileSearchOutlined />} onClick={event => { event.preventDefault(); setOpen(true); setPage(null); void load(0); }} /></Tooltip>
    {open ? <Drawer rootClassName="run-diagnostics-drawer" title={t("diagnostics.title")} open size={drawerWidth} styles={{ wrapper: { maxWidth: "100vw" } }}
      extra={<Popover afterOpenChange={visible => { if (visible) scopeClose.current?.focus(); }} trigger={[]} open={scopeOpen} onOpenChange={setScopeOpen} placement="bottomRight" title={t("diagnostics.scope")} content={<div className="run-diagnostics__scope" onKeyDown={event => { if (event.key === "Escape") { event.stopPropagation(); closeScope(); } }}><Typography.Text>{t("diagnostics.range", { from: String(page?.events[0]?.sequence ?? "—"), to: String(page?.events.at(-1)?.sequence ?? "—") })}</Typography.Text>{page?.nextAfterSequence != null ? <Typography.Text>{t("diagnostics.partial")}</Typography.Text> : null}<Typography.Text>{t("diagnostics.description")}</Typography.Text><Button ref={scopeClose} size="small" onClick={closeScope}>{t("diagnostics.closeScope")}</Button></div>}><Dropdown trigger={["click"]} menu={{ items: [{ key: "export", label: t("diagnostics.export"), disabled: loading || !page }, { key: "scope", label: t("diagnostics.scope") }], onClick: ({ key }) => { if (key === "export") download(); else setScopeOpen(true); } }}><Button ref={moreTrigger} type="text" aria-label={t("diagnostics.more")} icon={<MoreOutlined />} /></Dropdown></Popover>}
      onClose={() => { generation.current += 1; setOpen(false); setScopeOpen(false); setLoading(false); queueMicrotask(() => trigger.current?.focus()); }}>
      {!mobile ? <div className="run-diagnostics__resize"><PanelResizeHandle side="right" width={drawerWidth} minimum={360} maximum={maximumWidth} label={t("diagnostics.resize")} hint={t("diagnostics.resizeHint")} onChange={value => setPreferredWidth(Math.max(360, Math.min(maximumWidth, value)))} onReset={() => setPreferredWidth(560)} /></div> : null}
      <div className="run-diagnostics">
        <section className="run-diagnostics__overview" aria-label={t("diagnostics.result")}>
          <Badge status={badgeStatus(run?.status ?? "unknown")} text={run ? t(`execution.status.${run.status}`) : t("diagnostics.unconfirmed")} />
          {run?.status === "completed" ? <Typography.Text type="secondary">{t("diagnostics.completionNote")}</Typography.Text> : null}
          {run?.error ? <p>{agentChatErrorText(new AgentChatApiError(run.error.code), t)}</p> : null}
          {run?.error?.code === "invalid_credentials" ? <Typography.Text type="secondary">{t("diagnostics.credentialsHelp")}</Typography.Text> : null}
          <div className="run-diagnostics__metadata">
          {modelName ? <Typography.Text type="secondary" className="run-diagnostics__wrap">{modelName}</Typography.Text> : null}
          {run?.startedAt && run.finishedAt ? <Typography.Text type="secondary">{t("execution.duration")}: {Math.max(0, (Date.parse(run.finishedAt) - Date.parse(run.startedAt)) / 1000).toLocaleString(locale, { maximumFractionDigits: 1 })} s</Typography.Text> : null}
          </div>
        </section>
        <Typography.Text strong>{t("execution.record")}</Typography.Text>
        {error ? <Alert type="error" title={error} action={<Button size="small" onClick={() => void load(page?.nextAfterSequence ?? 0)}>{t("diagnostics.retry")}</Button>} /> : null}
        {exportError ? <Alert type="error" title={t("diagnostics.exportError")} /> : null}
        {loading && !page ? <Skeleton active paragraph={{ rows: 3 }} /> : rows.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={t("diagnostics.empty")} /> :
          <Collapse ghost size="small" className="run-diagnostics__events" style={{ borderRadius: 0 }} items={rows.map(operation => ({ key: operation.key,
            label: <div className="run-diagnostics__event-label"><span>{stageLabel(operation.event)}</span><span className="run-diagnostics__event-meta"><Badge status={badgeStatus(operation.status)} text={statusLabel(operation.status)} /><time dateTime={operation.event.createdAt}>{new Date(operation.event.createdAt).toLocaleTimeString(locale, { hour12: false })}</time></span></div>,
            children: <DiagnosticDetails operation={operation} hideError={rows.length === 1 && page?.nextAfterSequence == null && run?.status === "failed" && operation.event.runId === run.id && operation.event.data.errorCode === run.error?.code} />,
          }))} />}
        {page?.nextAfterSequence != null ? <footer className="run-diagnostics__footer"><Button size="small" loading={loading} onClick={() => void load(page.nextAfterSequence!)}>{t("diagnostics.next")}</Button></footer> : null}
      </div>
    </Drawer> : null}
  </span>;
}

function DiagnosticDetails({ operation, hideError }: { operation: DiagnosticOperation; hideError: boolean }) {
  const { event, start } = operation;
  const { t, locale } = useI18n();
  const [showZero, setShowZero] = useState(false);
  const context = (start?.data.context ?? event.data.context) as Record<string, unknown> | undefined;
  const components = context?.components as Record<string, number> | undefined;
  const format = (value: unknown) => typeof value === "number" ? value.toLocaleString(locale) : t("diagnostics.unreported");
  return <div className="run-diagnostics__details">
    {!start && event.type === "model.attempt" ? <Typography.Text type="secondary">{t("diagnostics.missingStart")}</Typography.Text> : null}
    {!hideError && typeof event.data.errorCode === "string" ? <Typography.Text>{agentChatErrorText(new AgentChatApiError(event.data.errorCode as ConstructorParameters<typeof AgentChatApiError>[0]), t)}</Typography.Text> : null}
    {event.data.retryCause ? <Typography.Text>{t("diagnostics.retryCause")}</Typography.Text> : null}
    {event.type.startsWith("context.compaction.") ? <section>
      <Typography.Text strong>{t("diagnostics.compactionSummary")}</Typography.Text>
      <dl className="run-diagnostics__numbers">
        <div><dt>{t("diagnostics.compactionReason")}</dt><dd>{start?.data.reason === "local_budget" ? t("diagnostics.localBudget") : start?.data.reason === "provider_context_limit" ? t("diagnostics.providerLimit") : t("diagnostics.unreported")}</dd></div>
        <div><dt>{t("diagnostics.historyRange")}</dt><dd>{format(start?.data.fromSequence)}–{format(start?.data.throughSequence)}</dd></div>
        <div><dt>{t("diagnostics.beforeEstimate")}</dt><dd>{format(start?.data.estimatedBeforeTokens)}</dd></div>
        <div><dt>{t("diagnostics.inputBudgetTokens")}</dt><dd>{format(start?.data.inputBudgetTokens)}</dd></div>
      </dl>
      <Typography.Text type="secondary">{t("diagnostics.compactionNote")}</Typography.Text>
    </section> : null}
    {event.type === "model.attempt" && operation.status === "cancelled" ? <Typography.Text type="secondary">{t("diagnostics.cancelledUsage")}</Typography.Text> : null}
    <div className="run-diagnostics__metrics">
    {event.data.status === "completed" && event.type === "model.attempt" ? <section><Typography.Text strong>{t("diagnostics.actualUsage")}</Typography.Text><dl className="run-diagnostics__numbers">{(["inputTokens", "outputTokens"] as const).map(key => <div key={key}><dt>{t(`diagnostics.${key}`)}</dt><dd>{format(event.data[key])}</dd></div>)}</dl></section> : null}
    {context ? <section><Typography.Text strong>{t("diagnostics.receipt")}</Typography.Text><dl className="run-diagnostics__numbers">{(["estimatedInputTokens", "inputBudgetTokens", "outputReserveTokens"] as const).map(key => <div key={key}><dt>{t(`diagnostics.${key}`)}</dt><dd>{format(context[key])}</dd></div>)}</dl></section> : null}
    </div>
    {event.type === "model.attempt" && event.data.status === "completed" ? <Typography.Text type="secondary">{t("diagnostics.usageNote")}</Typography.Text> : null}
    {context ? <>
      <Collapse ghost size="small" items={[{ key: "sources", label: t("diagnostics.sources"), children: <>
      <dl className="run-diagnostics__usage">{(["system", "summary", "history", "currentUser", "toolResults", "assistant", "summaryInput", "unattributed", "toolDefinitions", "framing"] as const).filter(key => showZero || (components?.[key] ?? 0) > 0).map(key => <div key={key}><dt>{t(`diagnostics.source.${key}`)}</dt><dd>{format(components?.[key])}</dd></div>)}</dl>
      <Button type="text" size="small" className="run-diagnostics__zero" onClick={() => setShowZero(!showZero)}>{t(showZero ? "diagnostics.hideZero" : "diagnostics.showZero")}</Button>
      <Typography.Text type="secondary" className="run-diagnostics__note">{t("diagnostics.estimateNote")}</Typography.Text>
      </> }]} />
    </> : null}
    <Collapse ghost size="small" items={[{ key: "technical", label: t("diagnostics.technical"), children: <Descriptions column={1} size="small" items={[
      { key: "type", label: "Event", children: event.type },
      { key: "events", label: t("diagnostics.range", { from: String(operation.events[0].sequence), to: String(operation.events.at(-1)!.sequence) }), children: operation.events.map(item => <div key={item.sequence}>{item.createdAt} · {String(item.data.status ?? item.type)}</div>) },
      { key: "run", label: "Run ID", children: <Typography.Text copyable className="run-diagnostics__wrap">{event.runId}</Typography.Text> },
      ...Object.entries(event.data).filter(([key, value]) => key !== "context" && value != null).map(([key, value]) => ({ key, label: key, children: <Typography.Text className="run-diagnostics__wrap" copyable={/Id$/.test(key)}>{String(value)}</Typography.Text> })),
      ...Object.entries(context ?? {}).filter(([key, value]) => key !== "components" && value != null).map(([key, value]) => ({
        key: "context-" + key, label: key,
        children: typeof value === "object"
          ? <pre className="run-diagnostics__receipt">{JSON.stringify(value, null, 2)}</pre>
          : <Typography.Text className="run-diagnostics__wrap" copyable={key.endsWith("Hash")}>{String(value)}</Typography.Text>,
      })),
    ]} /> }]} />
  </div>;
}
