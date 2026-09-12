import type { RunEvent } from "../../api/agentChat";
import { validAttemptPayload } from "../../api/attemptEvents";
import { validCompactionPayload } from "../../api/compactionEvents";

export function diagnosticEvents(events: RunEvent[]): RunEvent[] {
  return events.filter(event => event.type === "model.attempt" ? validAttemptPayload(event.data)
    : event.type.startsWith("context.compaction.") && validCompactionPayload(event.type, event.data));
}

export function diagnosticExport(runId: string, events: RunEvent[], afterSequence: number, nextAfterSequence: number | null): string {
  return JSON.stringify({ schemaVersion: 1, runId, scope: "loaded-page", afterSequence, nextAfterSequence,
    coversCurrentHistory: afterSequence === 0 && nextAfterSequence === null,
    runCompletionAsserted: false,
    contentIncluded: false,
    events: diagnosticEvents(events).filter(event => event.runId === runId).map(event => ({
      sequence: event.sequence, type: event.type, createdAt: event.createdAt, data: event.data,
    })),
  }, null, 2);
}
