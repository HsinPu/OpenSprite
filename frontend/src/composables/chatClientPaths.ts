export function buildRunSummaryPath(runId: string, sessionId: string): string {
  return `/api/runs/${encodeURIComponent(runId)}/summary?session_id=${encodeURIComponent(sessionId)}`;
}

export function buildRunTracePath(runId: string, sessionId: string): string {
  return `/api/runs/${encodeURIComponent(runId)}?session_id=${encodeURIComponent(sessionId)}`;
}

export function buildRunFileChangeRevertPath(runId: string, sessionId: string, changeId: string): string {
  return `/api/runs/${encodeURIComponent(runId)}/file-changes/${encodeURIComponent(changeId)}/revert?session_id=${encodeURIComponent(sessionId)}`;
}

export function buildRunsPath(sessionId: string, limit: number): string {
  return `/api/runs?session_id=${encodeURIComponent(sessionId)}&limit=${limit}`;
}

export function buildSessionDeletePath(sessionId: string): string {
  return `/api/sessions?session_id=${encodeURIComponent(sessionId)}`;
}

export function buildSessionsClearPath(channel = "web"): string {
  return `/api/sessions?channel=${encodeURIComponent(channel)}`;
}
