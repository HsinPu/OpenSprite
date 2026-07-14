import { RunHistorySelector } from "./runHistorySelector";
import { RunSummaryCard } from "./runSummaryCard";
import { RunTimeline } from "./runTimeline";
import { RunTraceViewer } from "./runTraceViewer";
import type { RunSummaryCopy } from "./runSummaryCard";
import type { RunTimelineCopy } from "./runTimeline";
import type { RunTraceCopy } from "./runTraceViewer";
import type { RunTimelineEventView, RunViewState } from "../composables/chatClientRunHelpers";
import type { TraceFileChangeView } from "../composables/runTraceNormalizers";

type ValueRef<T> = { value: T };

export type RunInspectorStateView = {
  showRunHistory: boolean;
  showRunSummary: boolean;
  showRunTimeline: boolean;
  showRunTrace: boolean;
};

export type RunInspectorCopy = RunSummaryCopy &
  RunTimelineCopy &
  RunTraceCopy & {
    trace: RunTraceCopy["trace"] & {
      collapse?: string;
      noRun?: string;
    };
    runHistory: RunTimelineCopy["runHistory"] & {
      latest?: string;
      loading?: string;
      select?: string;
      unavailable: string;
    };
    runSummary: RunSummaryCopy["runSummary"] & {
      objective?: string;
    };
  };

export type RunInspectorClient = {
  state: RunInspectorStateView;
  copy: ValueRef<RunInspectorCopy>;
  currentRun: ValueRef<RunViewState | null>;
  currentRuns: ValueRef<RunViewState[]>;
  currentRunsLoading: ValueRef<boolean>;
  currentRunsError: ValueRef<string>;
  currentRunTimeline: ValueRef<RunTimelineEventView[]>;
  selectRun: (runId: string) => void;
  cleanupWorktreeSandbox: (run: RunViewState) => void;
  cancelRun: (run: RunViewState) => void;
  revertRunFileChange: (run: RunViewState, change: TraceFileChangeView) => void;
};

export function RunInspector({ client }: { client: RunInspectorClient }) {
  const copy = client.copy.value;
  const run = client.currentRun.value;
  const runs = client.currentRuns.value || [];

  return (
    <div className="trace-sidebar__body">
      <RunHistorySelector client={client} run={run} runs={runs} />
      <RunDetailsPanel client={client} run={run} />
    </div>
  );
}

function RunDetailsPanel({ client, run }: { client: RunInspectorClient; run: RunViewState | null }) {
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
