import { shortRunId } from "../composables/chatClientRunHelpers";

type AnyRecord = Record<string, any>;

export function connectionLabel(copy: AnyRecord, state: string) {
  return copy.connection?.[state] || state;
}

export function noticeTone(tone: string): "success" | "info" | "warning" | "error" {
  if (tone === "success" || tone === "warning" || tone === "error") {
    return tone;
  }
  return "info";
}

export function runStatusColor(status: string) {
  if (["completed", "success", "done"].includes(status)) {
    return "green";
  }
  if (["failed", "error"].includes(status)) {
    return "red";
  }
  if (["running", "thinking", "tool_running", "streaming"].includes(status)) {
    return "blue";
  }
  if (["cancelled", "cancelling"].includes(status)) {
    return "orange";
  }
  return "default";
}

export function runOptionLabel(copy: AnyRecord, run: AnyRecord, index: number) {
  const statusLabel = copy.run.statusLabels?.[run.status] || run.status;
  const prefix = index === 0 ? copy.runHistory.latest : `#${index + 1}`;
  return `${prefix} · Run ${shortRunId(run.runId)} · ${statusLabel}`;
}
