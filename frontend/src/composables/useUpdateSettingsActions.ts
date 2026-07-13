import type { UpdateStatusView } from "./useSettingsState";
import { toPayloadSource } from "./payloadBoundary";

type RequestSettingsJson = (pathname: string, options?: RequestInit) => Promise<unknown>;
type UpdateStatusPayload = {
  supported?: unknown;
  dirty?: unknown;
  update_available?: unknown;
  commits_behind?: unknown;
  current_rev_short?: unknown;
  branch?: unknown;
  project_root?: unknown;
};
type RunUpdatePayload = {
  after_rev_short?: unknown;
  restart_scheduled?: unknown;
};
type RunUpdateResultView = {
  after_rev_short: string;
  restart_scheduled: boolean;
};

interface UpdateSettingsState {
  updateLoading: boolean;
  updateError: string;
  updateNotice: string;
  updateStatus: UpdateStatusView;
}

interface UpdateSettingsCopy {
  notices: {
    updateStatusFailed: string;
    updateRestarting: string;
    updateApplied: string;
    updateFailed: string;
  };
}

type SettingsActionContext = {
  settingsState: UpdateSettingsState;
  requestSettingsJson: RequestSettingsJson;
  copy: { value: UpdateSettingsCopy };
};

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "";
}

function textValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function toUpdateStatusPayload(value: unknown): UpdateStatusPayload {
  const payload = toPayloadSource<UpdateStatusPayload>(value);
  if (!payload) {
    return {};
  }
  return {
    supported: payload.supported,
    dirty: payload.dirty,
    update_available: payload.update_available,
    commits_behind: payload.commits_behind,
    current_rev_short: payload.current_rev_short,
    branch: payload.branch,
    project_root: payload.project_root,
  };
}

function toRunUpdatePayload(value: unknown): RunUpdatePayload {
  const payload = toPayloadSource<RunUpdatePayload>(value);
  if (!payload) {
    return {};
  }
  return {
    after_rev_short: payload.after_rev_short,
    restart_scheduled: payload.restart_scheduled,
  };
}

function numberValue(value: unknown): number {
  const numberValue = Number(value || 0);
  return Number.isFinite(numberValue) ? numberValue : 0;
}

function normalizeUpdateStatus(value: unknown): UpdateStatusView {
  const payload = toUpdateStatusPayload(value);
  return {
    supported: Boolean(payload.supported),
    dirty: Boolean(payload.dirty),
    update_available: Boolean(payload.update_available),
    commits_behind: numberValue(payload.commits_behind),
    current_rev_short: textValue(payload.current_rev_short),
    branch: textValue(payload.branch),
    project_root: textValue(payload.project_root),
  };
}

function normalizeRunUpdateResult(value: unknown): RunUpdateResultView {
  const payload = toRunUpdatePayload(value);
  return {
    after_rev_short: textValue(payload.after_rev_short),
    restart_scheduled: Boolean(payload.restart_scheduled),
  };
}

export function useUpdateSettingsActions({ settingsState, requestSettingsJson, copy }: SettingsActionContext) {
  async function loadUpdateStatus(): Promise<void> {
    settingsState.updateLoading = true;
    settingsState.updateError = "";
    try {
      settingsState.updateStatus = normalizeUpdateStatus(await requestSettingsJson("/api/settings/update"));
    } catch (error: unknown) {
      settingsState.updateError = errorMessage(error) || copy.value.notices.updateStatusFailed;
    } finally {
      settingsState.updateLoading = false;
    }
  }

  async function runUpdate(): Promise<void> {
    settingsState.updateLoading = true;
    settingsState.updateError = "";
    settingsState.updateNotice = "";
    try {
      const payload = normalizeRunUpdateResult(await requestSettingsJson("/api/settings/update", {
        method: "POST",
        body: JSON.stringify({ restart: true }),
      }));
      const restartScheduled = payload.restart_scheduled;
      const currentStatus = settingsState.updateStatus;
      settingsState.updateStatus = {
        supported: currentStatus.supported,
        dirty: currentStatus.dirty,
        update_available: false,
        commits_behind: 0,
        current_rev_short: payload.after_rev_short || currentStatus.current_rev_short,
        branch: currentStatus.branch,
        project_root: currentStatus.project_root,
      };
      settingsState.updateNotice = restartScheduled
        ? copy.value.notices.updateRestarting
        : copy.value.notices.updateApplied;
      if (restartScheduled) {
        window.setTimeout(() => window.location.reload(), 5000);
      }
    } catch (error: unknown) {
      settingsState.updateError = errorMessage(error) || copy.value.notices.updateFailed;
    } finally {
      settingsState.updateLoading = false;
    }
  }

  return {
    loadUpdateStatus,
    runUpdate,
  };
}
