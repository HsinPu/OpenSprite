import type { RunEvent, RunSnapshot } from "../../api/agentChat";
import { diagnosticEvents } from "./diagnosticExport";

export type DiagnosticOperation = {
  key: string;
  events: RunEvent[];
  event: RunEvent;
  start?: RunEvent;
  status: string;
};

/** Presentation only: never replace the validated raw export with these groups. */
export function diagnosticOperations(events: RunEvent[], runStatus?: RunSnapshot["status"], hasMore = false): DiagnosticOperation[] {
  const groups = new Map<string, RunEvent[]>();
  for (const event of diagnosticEvents(events).slice().sort((a, b) => a.sequence - b.sequence)) {
    const kind = event.type === "model.attempt" ? "attempt" : "compaction";
    const id = event.data[kind === "attempt" ? "attemptId" : "compactionId"];
    const key = JSON.stringify([event.runId, kind, typeof id === "string" ? id : event.sequence]);
    const group = groups.get(key) ?? [];
    if (!group.some(item => item.sequence === event.sequence)) group.push(event);
    groups.set(key, group);
  }
  return [...groups].map(([key, records]) => {
    const statusOf = (event: RunEvent) => String(event.data.status ?? event.type.split(".").at(-1));
    const start = records.find(event => statusOf(event) === "started");
    const terminal = records.slice().reverse().find(event => statusOf(event) !== "started");
    const event = terminal ?? records[records.length - 1];
    const active = runStatus === "running" || runStatus === "queued" || runStatus === "cancelling";
    return { key, events: records, event, start,
      status: terminal ? statusOf(terminal) : hasMore ? "partial" : active ? "started" : "missingEnd" };
  });
}
