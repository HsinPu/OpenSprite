import { Descriptions, Tag } from "antd";
import { runStatusColor } from "./displayHelpers";
import type { RunViewState } from "../composables/chatClientRunHelpers";

export type RunSummaryCopy = {
  run: {
    statusLabels?: Record<string, string>;
  };
  runSummary: {
    status: string;
    duration: string;
    durationSeconds: (seconds: number) => string;
    tools: string;
    title?: string;
    headline: string;
    loading?: string;
  };
};

function text(value: unknown, fallback = ""): string {
  return String(value || fallback).trim();
}

export function RunSummaryCard({
  copy,
  run,
}: {
  copy: RunSummaryCopy;
  run: RunViewState;
}) {
  const summary = run.summary;
  const statusText = text(summary?.status, run.status);
  const durationText =
    summary?.durationSeconds === null || summary?.durationSeconds === undefined
      ? ""
      : copy.runSummary.durationSeconds(summary.durationSeconds);
  const metricItems = [
    {
      key: "status",
      label: copy.runSummary.status,
      children: statusText,
    },
    ...(durationText
      ? [
          {
            key: "duration",
            label: copy.runSummary.duration,
            children: durationText,
          },
        ]
      : []),
    ...(summary
      ? [
          {
            key: "tools",
            label: copy.runSummary.tools,
            children: summary.toolCount,
          },
        ]
      : []),
  ];

  return (
    <section className="run-summary-card" data-status={run.status || "unknown"}>
      <header className="run-summary-card__header">
        <div className="run-summary-card__title">
          <span className="run-summary-card__eyebrow">{copy.runSummary.title || "Run Summary"}</span>
          <strong>{copy.runSummary.headline}</strong>
        </div>
        <div className="run-summary-card__actions">
          <Tag className="run-summary-card__status" color={runStatusColor(run.status)} data-status={run.status || "unknown"}>
            {copy.run.statusLabels?.[run.status] || run.status}
          </Tag>
        </div>
      </header>
      <div className="run-summary-card__body">
        {run.summaryLoading ? <div className="run-summary-card__message">{copy.runSummary.loading || "Loading..."}</div> : null}
        {run.summaryError ? <div className="run-summary-card__message" data-tone="error">{run.summaryError}</div> : null}
        <Descriptions className="run-summary-card__metrics" size="small" column={1} items={metricItems} />
      </div>
    </section>
  );
}
