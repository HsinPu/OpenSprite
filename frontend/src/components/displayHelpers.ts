import { shortRunId } from "../composables/chatClientRunHelpers";
import type { RunViewState } from "../composables/chatClientRunHelpers";
import type { ConnectionState, NoticeTone } from "../composables/useChatClient";

export type ConnectionCopy = {
  connection?: Record<string, string>;
};

export type RunOptionCopy = {
  run: {
    statusLabels?: Record<string, string>;
  };
  runHistory: {
    latest?: string;
  };
};

export function connectionLabel(copy: ConnectionCopy, state: ConnectionState) {
  return copy.connection?.[state] || state;
}

export function noticeTone(tone: NoticeTone | string | null | undefined): NoticeTone {
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

export function runOptionLabel(copy: RunOptionCopy, run: RunViewState, index: number) {
  const statusLabel = copy.run.statusLabels?.[run.status] || run.status;
  const prefix = index === 0 ? copy.runHistory.latest || "Latest" : `#${index + 1}`;
  return `${prefix} · Run ${shortRunId(run.runId)} · ${statusLabel}`;
}
