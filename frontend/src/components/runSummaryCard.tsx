import { Button, Descriptions, Tag } from "antd";
import { runStatusColor } from "./displayHelpers";
import type { RunViewState } from "../composables/chatClientRunHelpers";

export type RunSummaryCopy = {
  run: {
    statusLabels?: Record<string, string>;
  };
  runSummary: {
    status: string;
    duration: string;
    tools: string;
    title?: string;
    fallbackObjective: string;
    cleanupSandbox?: string;
    loading?: string;
  };
};

function text(value: unknown, fallback = ""): string {
  return String(value || fallback).trim();
}

type RunSummary = NonNullable<RunViewState["summary"]>;

function summaryTitle(summary: RunSummary | null | undefined, fallback = ""): string {
  return text(summary?.objective || summary?.title, fallback);
}

function summaryResult(summary: RunSummary | null | undefined): string {
  return text(summary?.result || summary?.finalAnswer);
}

export function RunSummaryCard({
  copy,
  run,
  cleanupWorktreeSandbox,
}: {
  copy: RunSummaryCopy;
  run: RunViewState;
  cleanupWorktreeSandbox: (run: RunViewState) => void;
}) {
  const summary = run.summary;
  const statusText = text(summary?.status, run.status);
  const durationText = text(summary?.duration);
  const resultText = summaryResult(summary);
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
    ...(Array.isArray(summary?.tools)
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
          <strong>{summaryTitle(summary, copy.runSummary.fallbackObjective)}</strong>
        </div>
        <div className="run-summary-card__actions">
          <Tag className="run-summary-card__status" color={runStatusColor(run.status)} data-status={run.status || "unknown"}>
            {copy.run.statusLabels?.[run.status] || run.status}
          </Tag>
          {Boolean(run.worktreeSandbox?.cleanupSupported) ? (
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
        {resultText ? (
          <p className="run-summary-card__note">{resultText}</p>
        ) : null}
      </div>
    </section>
  );
}
