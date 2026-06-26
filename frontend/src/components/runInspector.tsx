import { Button, Collapse, Empty, List, Tag, Timeline } from "antd";
import { runStatusColor } from "./displayHelpers";
import { RunHistorySelector } from "./runHistorySelector";
import { RunSummaryCard } from "./runSummaryCard";
import { RunTimeline } from "./runTimeline";
import { WorkStateCard } from "./workStateCard";

type AnyRecord = Record<string, any>;
type ValueRef<T> = { value: T };

export type RunInspectorClient = {
  state: AnyRecord;
  copy: ValueRef<AnyRecord>;
  currentRun: ValueRef<AnyRecord | null>;
  currentRuns: ValueRef<AnyRecord[]>;
  currentRunsLoading: ValueRef<boolean>;
  currentRunsError: ValueRef<string>;
  currentWorkState: ValueRef<AnyRecord | null>;
  currentRunTimeline: ValueRef<AnyRecord[]>;
  selectRun: (runId: string) => void;
  resumeFollowUp: (prompt: string) => void;
  runVerification: (prompt: string) => void;
  cleanupWorktreeSandbox: (run: AnyRecord) => void;
  cancelRun: (run: AnyRecord) => void;
  revertRunFileChange: (run: AnyRecord, change: AnyRecord) => void;
};

export function RunInspector({ client }: { client: RunInspectorClient }) {
  const copy = client.copy.value;
  const run = client.currentRun.value;
  const runs = client.currentRuns.value || [];

  return (
    <div className="trace-sidebar__body">
      <RunHistorySelector client={client} run={run} runs={runs} />

      {client.state.showWorkState && client.currentWorkState.value ? (
        <WorkStateCard client={client} workState={client.currentWorkState.value} />
      ) : null}

      <RunDetailsPanel client={client} run={run} />
    </div>
  );
}

function RunDetailsPanel({ client, run }: { client: RunInspectorClient; run: AnyRecord | null }) {
  const copy = client.copy.value;
  if (!run) {
    return <div className="run-trace__empty">{copy.trace?.noRun || copy.runHistory.unavailable}</div>;
  }

  return (
    <div className="run-details-panel">
      {client.state.showRunSummary ? <RunSummaryCard copy={copy} run={run} cleanupWorktreeSandbox={client.cleanupWorktreeSandbox} /> : null}
      {client.state.showRunTimeline ? <RunTimeline copy={copy} events={client.currentRunTimeline.value || []} /> : null}
      {client.state.showRunTrace ? (
        <RunTraceViewer
          copy={copy}
          run={run}
          cancelRun={client.cancelRun}
          revertFileChange={client.revertRunFileChange}
        />
      ) : null}
    </div>
  );
}

function RunTraceViewer({
  copy,
  run,
  cancelRun,
  revertFileChange,
}: {
  copy: AnyRecord;
  run: AnyRecord;
  cancelRun: (run: AnyRecord) => void;
  revertFileChange: (run: AnyRecord, change: AnyRecord) => void;
}) {
  const artifacts = run.artifacts || [];
  const events = run.rawEvents || run.events || [];
  const parts = run.parts || [];
  const fileChanges = run.fileChanges || [];

  function exportDebugJson() {
    const blob = new Blob([JSON.stringify({ run, exported_at: new Date().toISOString() }, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${run.runId || "run"}-trace.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  const items = [
    {
      key: "artifacts",
      label: `${copy.trace.artifactHeading || copy.trace.artifacts} (${artifacts.length})`,
      children: artifacts.length ? (
        <List
          dataSource={artifacts}
          renderItem={(artifact: AnyRecord) => (
            <List.Item>
              <List.Item.Meta
                avatar={<Tag color={runStatusColor(artifact.status)}>{artifact.status || artifact.kind || artifact.type}</Tag>}
                title={artifact.title || artifact.name || artifact.toolName || artifact.kind || artifact.type}
                description={artifact.detail || artifact.summary || artifact.path || artifact.message}
              />
            </List.Item>
          )}
        />
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ),
    },
    {
      key: "events",
      label: `${copy.trace.events || "Events"} (${events.length})`,
      children: events.length ? (
        <Timeline
          items={events.slice(-120).map((event: AnyRecord) => ({
            color: event.status === "failed" || event.tone === "error" ? "red" : "blue",
            children: (
              <Collapse
                className="run-trace__event-collapse"
                size="small"
                ghost
                items={[
                  {
                    key: event.id || event.eventType || event.type || "event",
                    label: event.label || event.eventType || event.type,
                    children: <pre>{JSON.stringify(event.payload || event, null, 2)}</pre>,
                  },
                ]}
              />
            ),
          }))}
        />
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ),
    },
    {
      key: "parts",
      label: `${copy.trace.parts} (${parts.length})`,
      children: parts.length ? (
        <Collapse
          items={parts.map((part: AnyRecord, index: number) => ({
            key: part.id || index,
            label: part.title || part.type || `${copy.trace.parts} ${index + 1}`,
            children: <pre>{part.text || part.content || JSON.stringify(part, null, 2)}</pre>,
          }))}
        />
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ),
    },
    {
      key: "files",
      label: `${copy.runSummary.diffSummary || "Files"} (${fileChanges.length})`,
      children: fileChanges.length ? (
        <List
          dataSource={fileChanges}
          renderItem={(change: AnyRecord) => (
            <List.Item
              actions={[
                change.revertSupported ? (
                  <Button size="small" onClick={() => revertFileChange(run, change)}>
                    {copy.runFileInspector?.revert || "Revert"}
                  </Button>
                ) : null,
              ].filter(Boolean)}
            >
              <List.Item.Meta title={change.path || change.label} description={change.status || change.kind} />
            </List.Item>
          )}
        />
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ),
    },
  ];

  return (
    <section className="run-trace" data-status={run.status || "unknown"}>
      <header className="run-trace__header">
        <div className="run-trace__title">
          <span className="run-trace__eyebrow">{copy.trace.title}</span>
          <strong>{run.runId}</strong>
        </div>
        <div className="run-trace__actions">
          <Tag className="run-trace__status" color={runStatusColor(run.status)} data-status={run.status || "unknown"}>{run.status}</Tag>
          <Button className="run-summary-card__copy" size="small" onClick={exportDebugJson}>
            {copy.trace.exportDebug}
          </Button>
          {run.status === "running" ? (
            <Button className="run-trace__cancel" size="small" danger disabled={run.cancelPending} onClick={() => cancelRun(run)}>
              {copy.trace.cancelRun}
            </Button>
          ) : null}
        </div>
      </header>
      <div className="run-trace__body">
        {run.traceError ? <div className="run-summary-card__message" data-tone="error">{run.traceError}</div> : null}
        {run.traceLoading ? <div className="run-summary-card__message">{copy.trace.loading || "Loading..."}</div> : null}
        <div className="run-trace__summary">
          <Tag>{events.length} {copy.trace.events || "events"}</Tag>
          <Tag>{artifacts.length} {copy.trace.artifacts}</Tag>
          <Tag>{parts.length} {copy.trace.parts}</Tag>
          <Tag>{fileChanges.length} {copy.runSummary.diffSummary || "files"}</Tag>
        </div>
        <Collapse className="run-trace__sections" size="small" defaultActiveKey={["artifacts"]} items={items} />
      </div>
    </section>
  );
}
