import { useEffect, useRef, useState } from "react";
import { Alert, Button, Descriptions, Drawer, Space, Table, Typography } from "antd";
import { agentChatErrorText, listRunEventHistory, type RunEvent, type RunEventPage } from "../../api/agentChat";
import { useI18n } from "../../i18n/I18nProvider";
import { diagnosticEvents, diagnosticExport } from "./diagnosticExport";
import "./RunDiagnostics.css";

export function RunDiagnostics({ runId, conversationId }: { runId: string; conversationId: string }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState<RunEventPage | null>(null);
  const [cursor, setCursor] = useState(0);
  const [previous, setPrevious] = useState<number[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const generation = useRef(0);
  const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    generation.current += 1;
    setOpen(false); setPage(null); setCursor(0); setPrevious([]); setError(null); setLoading(false);
    return () => { generation.current += 1; };
  }, [runId, conversationId]);

  async function load(next: number, history: number[]) {
    const current = ++generation.current;
    setLoading(true); setError(null);
    try {
      const result = await listRunEventHistory(runId, next);
      if (generation.current !== current) return;
      if (result.events.some(event => event.conversationId !== conversationId)) throw new Error("mismatched history");
      setPage(result); setCursor(next); setPrevious(history);
    } catch (failure) {
      if (generation.current === current) setError(agentChatErrorText(failure, t));
    } finally { if (generation.current === current) setLoading(false); }
  }

  function download() {
    if (!page) return;
    const url = URL.createObjectURL(new Blob([diagnosticExport(runId, page.events, cursor, page.nextAfterSequence)], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url; link.download = `opensprite-diagnostics-${runId}-${cursor}.json`;
    link.click(); URL.revokeObjectURL(url);
  }

  const rows = diagnosticEvents(page?.events ?? []);
  const statusLabel = (event: RunEvent) => {
    const value = event.data.status ?? event.type.split(".").at(-1);
    return value === "started" || value === "completed" || value === "failed" || value === "cancelled"
      ? t(`diagnostics.${value}`) : t("diagnostics.unknown");
  };
  const stageLabel = (event: RunEvent) => {
    const purpose = event.data.purpose;
    return event.type === "model.attempt" && (purpose === "main" || purpose === "continuation" || purpose === "compaction")
      ? `${t(`diagnostics.${purpose}`)} · ${String(event.data.attemptNumber)}` : t("diagnostics.operation");
  };
  return <>
    <Button ref={trigger} size="small" onClick={() => { setOpen(true); void load(0, []); }}>{t("diagnostics.open")}</Button>
    {open ? <Drawer title={t("diagnostics.title")} open size={760} styles={{ wrapper: { maxWidth: "100vw" } }} onClose={() => { generation.current += 1; setOpen(false); setLoading(false); queueMicrotask(() => trigger.current?.focus()); }}>
      <div className="run-diagnostics">
        <Typography.Paragraph type="secondary">{t("diagnostics.description")}</Typography.Paragraph>
        {error ? <Alert type="error" title={error} action={<Button onClick={() => void load(cursor, previous)}>{t("diagnostics.retry")}</Button>} /> : null}
        <Space wrap>
          <Button size="small" disabled={loading || previous.length === 0} onClick={() => void load(previous.at(-1)!, previous.slice(0, -1))}>{t("diagnostics.previous")}</Button>
          <Button size="small" disabled={loading || page?.nextAfterSequence == null} onClick={() => void load(page!.nextAfterSequence!, [...previous, cursor])}>{t("diagnostics.next")}</Button>
          <Button size="small" disabled={loading || !page} onClick={download}>{t("diagnostics.export")}</Button>
        </Space>
        <Typography.Text type="secondary">{t("diagnostics.range", { from: String(page?.events[0]?.sequence ?? "—"), to: String(page?.events.at(-1)?.sequence ?? "—") })}</Typography.Text>
        <Table<RunEvent> size="small" rowKey="sequence" loading={loading} pagination={false} dataSource={rows}
          locale={{ emptyText: t("diagnostics.empty") }}
          columns={[
            { title: "#", dataIndex: "sequence", width: 60 },
            { title: t("diagnostics.stage"), key: "stage", render: (_, event) => <span className="run-diagnostics__wrap">{stageLabel(event)}</span> },
            { title: t("diagnostics.status"), key: "status", render: (_, event) => statusLabel(event) },
          ]}
          expandable={{ expandedRowRender: event => <DiagnosticDetails event={event} /> }} />
      </div>
    </Drawer> : null}
  </>;
}

function DiagnosticDetails({ event }: { event: RunEvent }) {
  const { t } = useI18n();
  const context = event.data.context as Record<string, unknown> | undefined;
  const components = context?.components as Record<string, number> | undefined;
  return <div className="run-diagnostics__details">
    <time dateTime={event.createdAt}>{event.createdAt}</time>
    <Descriptions column={1} size="small" items={Object.entries(event.data).filter(([key]) => key !== "context").map(([key, value]) => ({ key, label: key, children: <span className="run-diagnostics__wrap">{value === null ? t(key === "inputTokens" || key === "outputTokens" ? "diagnostics.unknown" : "diagnostics.none") : String(value)}</span> }))} />
    {context ? <>
      <Typography.Text strong>{t("diagnostics.estimate")}: {String(context.estimatedInputTokens)}</Typography.Text>
      <Descriptions column={1} size="small" items={Object.entries(components ?? {}).map(([key, value]) => ({ key, label: key, children: value }))} />
      <Typography.Paragraph type="secondary">{t("diagnostics.estimateNote")}</Typography.Paragraph>
      <pre className="run-diagnostics__receipt">{JSON.stringify({ ...context, components: undefined }, null, 2)}</pre>
    </> : null}
  </div>;
}
