import { Button, Descriptions, Tag } from "antd";
import { runStatusColor } from "./displayHelpers";

type AnyRecord = Record<string, any>;

export function RunSummaryCard({
  copy,
  run,
  cleanupWorktreeSandbox,
}: {
  copy: AnyRecord;
  run: AnyRecord;
  cleanupWorktreeSandbox: (run: AnyRecord) => void;
}) {
  const summary = run.summary || {};
  const metricItems = [
    {
      key: "status",
      label: copy.runSummary.status,
      children: summary.status || run.status,
    },
    ...(summary.duration
      ? [
          {
            key: "duration",
            label: copy.runSummary.duration,
            children: summary.duration,
          },
        ]
      : []),
    ...(Array.isArray(summary.tools)
      ? [
          {
            key: "tools",
            label: copy.runSummary.tools,
            children: summary.tools.length,
          },
        ]
      : []),
  ];

  return (
    <section className="run-summary-card" data-status={run.status || "unknown"}>
      <header className="run-summary-card__header">
        <div className="run-summary-card__title">
          <span className="run-summary-card__eyebrow">{copy.runSummary.title || "Run Summary"}</span>
          <strong>{summary.objective || summary.title || copy.runSummary.fallbackObjective}</strong>
        </div>
        <div className="run-summary-card__actions">
          <Tag className="run-summary-card__status" color={runStatusColor(run.status)} data-status={run.status || "unknown"}>
            {copy.run.statusLabels?.[run.status] || run.status}
          </Tag>
          {run.worktreeSandbox?.cleanupSupported ? (
            <Button className="run-summary-card__copy" size="small" onClick={() => cleanupWorktreeSandbox(run)}>
              {copy.runSummary.cleanupSandbox || "Cleanup sandbox"}
            </Button>
          ) : null}
        </div>
      </header>
      <div className="run-summary-card__body">
        {run.summaryLoading ? <div className="run-summary-card__message">{copy.runSummary.loading || "Loading..."}</div> : null}
        {run.summaryError ? <div className="run-summary-card__message" data-tone="error">{run.summaryError}</div> : null}
        <Descriptions className="run-summary-card__metrics" size="small" column={1} items={metricItems} />
        {summary.result || summary.final_answer ? (
          <p className="run-summary-card__note">{summary.result || summary.final_answer}</p>
        ) : null}
      </div>
    </section>
  );
}
