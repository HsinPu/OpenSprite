import { RunHistorySelector } from "./runHistorySelector";
import { RunSummaryCard } from "./runSummaryCard";
import { RunTimeline } from "./runTimeline";
import { RunTraceViewer } from "./runTraceViewer";
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
