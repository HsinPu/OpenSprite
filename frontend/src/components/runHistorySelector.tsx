import { Select } from "antd";
import { runOptionLabel } from "./displayHelpers";
import type { RunInspectorClient } from "./runInspector";
import type { RunViewState } from "../composables/chatClientRunHelpers";

export function RunHistorySelector({
  client,
  run,
  runs,
}: {
  client: RunInspectorClient;
  run: RunViewState | null;
  runs: RunViewState[];
}) {
  const copy = client.copy.value;

  if (!client.state.showRunHistory || (runs.length <= 1 && !client.currentRunsLoading.value && !client.currentRunsError.value)) {
    return null;
  }

  return (
    <section className="run-history" aria-live="polite">
      <div className="run-history__title">
        <span>{copy.runHistory.title}</span>
        {client.currentRunsLoading.value ? <small>{copy.runHistory.loading}</small> : null}
        {!client.currentRunsLoading.value && client.currentRunsError.value ? <small>{copy.runHistory.unavailable}</small> : null}
      </div>
      {runs.length ? (
        <label className="run-history__select">
          <span className="sr-only">{copy.runHistory.select}</span>
          <Select
            value={run?.runId || ""}
            options={runs.map((item: RunViewState, index: number) => ({
              value: item.runId,
              label: runOptionLabel(copy, item, index),
            }))}
            onChange={(value) => client.selectRun(value)}
          />
        </label>
      ) : null}
    </section>
  );
}
