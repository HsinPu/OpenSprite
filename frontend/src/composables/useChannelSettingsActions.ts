import { normalizeChannelSettings } from "./settingsNormalizers";
import { toPayloadSource } from "./payloadBoundary";
import type { ChannelConnectForm, ChannelSettings, ChannelView } from "./useSettingsState";

type RequestSettingsJson = (pathname: string, options?: RequestInit) => Promise<unknown>;
type ChannelSettingsPayload = {
  connected?: unknown;
  available?: unknown;
  channels?: unknown;
};
type ChannelMutationPayload = {
  channel?: unknown;
  restart_required?: unknown;
};
type ChannelPayloadRecord = {
  id?: unknown;
  name?: unknown;
  type?: unknown;
  enabled?: unknown;
  description?: unknown;
  status?: unknown;
};

interface ChannelSettingsState {
  channelsLoading: boolean;
  channelsError: string;
  channelsNotice: string;
  channels: ChannelSettings;
  channelConnectForm: ChannelConnectForm;
}

interface ChannelSettingsCopy {
  notices: {
    channelLoadFailed: string;
    channelConnected: (name: string, restartRequired: boolean) => string;
    channelConnectFailed: string;
    channelDisconnected: (name: string, restartRequired: boolean) => string;
    channelDisconnectFailed: string;
  };
}

type SettingsActionContext = {
  settingsState: ChannelSettingsState;
  requestSettingsJson: RequestSettingsJson;
  copy: { value: ChannelSettingsCopy };
  setSettingsSuccess: (key: string, message: string) => void;
  cancelProviderConnect?: () => void;
};

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "";
}

function toChannelPayloadRecord(value: unknown): ChannelPayloadRecord | null {
  const payload = toPayloadSource<ChannelPayloadRecord>(value);
  return payload
    ? {
        id: payload.id,
        name: payload.name,
        type: payload.type,
        enabled: payload.enabled,
        description: payload.description,
        status: payload.status,
      }
    : null;
}

function toChannelSettingsPayload(value: unknown): ChannelSettingsPayload | null {
  const payload = toPayloadSource<ChannelSettingsPayload>(value);
  return payload
    ? {
        connected: payload.connected,
        available: payload.available,
        channels: payload.channels,
      }
    : null;
}

function toChannelMutationPayload(value: unknown): ChannelMutationPayload {
  const payload = toPayloadSource<ChannelMutationPayload>(value);
  if (!payload) {
    return {};
  }
  return {
    channel: payload.channel,
    restart_required: payload.restart_required,
  };
}

function toChannelView(value: unknown): ChannelView | null {
  const record = toChannelPayloadRecord(value);
  const id = String(record?.id || "").trim();
  if (!record || !id) {
    return null;
  }
  return {
    id,
    name: typeof record.name === "string" ? record.name : undefined,
    type: typeof record.type === "string" ? record.type : undefined,
    enabled: record.enabled === undefined ? undefined : Boolean(record.enabled),
    description: typeof record.description === "string" || typeof record.description === "number" ? String(record.description) : undefined,
    status: typeof record.status === "string" || typeof record.status === "number" ? String(record.status) : undefined,
  };
}

function channelViewList(value: unknown): ChannelView[] {
  const values = Array.isArray(value) ? value : [];
  return values.map(toChannelView).filter((channel): channel is ChannelView => channel !== null);
}

function normalizeChannels(payload: unknown): ChannelSettings {
  const settings = normalizeChannelSettings(toChannelSettingsPayload(payload) || {});
  return {
    connected: channelViewList(settings.connected),
    available: channelViewList(settings.available),
    channels: channelViewList(settings.channels),
  };
}

function channelDisplayName(channel: ChannelView): string {
  return String(channel.name || channel.id);
}

function isVisibleChannel(channel: ChannelView): boolean {
  return channel.id !== "web" && channel.id !== "console";
}

function sortChannelViews(channels: ChannelView[]): ChannelView[] {
  return [...channels].sort((left, right) => String(left.name || left.id).localeCompare(String(right.name || right.id)));
}

export function useChannelSettingsActions({ settingsState, requestSettingsJson, copy, setSettingsSuccess, cancelProviderConnect }: SettingsActionContext) {
  function upsertConnectedChannel(channel: ChannelView): void {
    if (!isVisibleChannel(channel)) {
      return;
    }
    const connected = settingsState.channels.connected.filter((entry) => entry.id !== channel.id);
    const nextConnected = sortChannelViews([...connected, channel]);
    const currentChannels = settingsState.channels;
    settingsState.channels = {
      connected: nextConnected,
      available: currentChannels.available,
      channels: nextConnected,
    };
  }

  function removeConnectedChannel(channelId: string): void {
    const nextConnected = settingsState.channels.connected.filter((entry) => entry.id !== channelId);
    const currentChannels = settingsState.channels;
    settingsState.channels = {
      connected: nextConnected,
      available: currentChannels.available,
      channels: nextConnected,
    };
  }

  async function loadChannelSettings(): Promise<void> {
    settingsState.channelsLoading = true;
    settingsState.channelsError = "";
    try {
      const payload = await requestSettingsJson("/api/settings/channels");
      settingsState.channels = normalizeChannels(payload);
    } catch (error: unknown) {
      settingsState.channelsError = errorMessage(error) || copy.value.notices.channelLoadFailed;
    } finally {
      settingsState.channelsLoading = false;
    }
  }

  function beginChannelConnect(channel: ChannelView): void {
    settingsState.channelsNotice = "";
    settingsState.channelsError = "";
    cancelProviderConnect?.();
    settingsState.channelConnectForm.type = String(channel.type || channel.id);
    settingsState.channelConnectForm.name = String(channel.name || "");
    settingsState.channelConnectForm.token = "";
  }

  function cancelChannelConnect(): void {
    settingsState.channelConnectForm.type = "";
    settingsState.channelConnectForm.name = "";
    settingsState.channelConnectForm.token = "";
  }

  async function saveChannelConnection(): Promise<void> {
    const channelType = settingsState.channelConnectForm.type;
    if (!channelType) {
      return;
    }
    settingsState.channelsLoading = true;
    settingsState.channelsError = "";
    settingsState.channelsNotice = "";
    try {
      const payload = toChannelMutationPayload(await requestSettingsJson("/api/settings/channels", {
        method: "POST",
        body: JSON.stringify({
          type: channelType,
          name: settingsState.channelConnectForm.name,
          token: settingsState.channelConnectForm.token,
        }),
      }));
      const channel = toChannelView(payload.channel);
      if (!channel) {
        throw new Error(copy.value.notices.channelConnectFailed);
      }
      setSettingsSuccess("channelsNotice", copy.value.notices.channelConnected(channelDisplayName(channel), Boolean(payload.restart_required)));
      upsertConnectedChannel(channel);
      cancelChannelConnect();
      await loadChannelSettings();
    } catch (error: unknown) {
      settingsState.channelsError = errorMessage(error) || copy.value.notices.channelConnectFailed;
    } finally {
      settingsState.channelsLoading = false;
    }
  }

  async function disconnectChannel(channel: ChannelView): Promise<void> {
    settingsState.channelsLoading = true;
    settingsState.channelsError = "";
    settingsState.channelsNotice = "";
    try {
      const payload = toChannelMutationPayload(await requestSettingsJson(`/api/settings/channels/${encodeURIComponent(channel.id)}/disconnect`, {
        method: "POST",
      }));
      setSettingsSuccess("channelsNotice", copy.value.notices.channelDisconnected(channelDisplayName(channel), Boolean(payload.restart_required)));
      removeConnectedChannel(channel.id);
      await loadChannelSettings();
    } catch (error: unknown) {
      settingsState.channelsError = errorMessage(error) || copy.value.notices.channelDisconnectFailed;
    } finally {
      settingsState.channelsLoading = false;
    }
  }

  return {
    loadChannelSettings,
    beginChannelConnect,
    cancelChannelConnect,
    saveChannelConnection,
    disconnectChannel,
  };
}
