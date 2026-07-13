import { toPayloadSource } from "./payloadBoundary";

export const MCP_TRANSPORT_TYPES = ["stdio", "sse", "streamableHttp"] as const;
export type McpTransportType = (typeof MCP_TRANSPORT_TYPES)[number];
const MCP_TRANSPORT_TYPE_SET: ReadonlySet<string> = new Set(MCP_TRANSPORT_TYPES);

type ChannelPayload = {
  id?: unknown;
  name?: unknown;
  type?: unknown;
  enabled?: unknown;
  description?: unknown;
  status?: unknown;
  token_configured?: unknown;
};
type ChannelSettingsPayload = {
  connected?: unknown;
  available?: unknown;
  channels?: unknown;
};
type NormalizedChannelSettingsPayload = {
  connected: ChannelPayload[];
  available: ChannelPayload[];
  channels: ChannelPayload[];
};
type MediaSectionsPayload = {
  vision?: unknown;
  ocr?: unknown;
  speech?: unknown;
  video?: unknown;
};
type MediaSettingsPayload = {
  sections?: unknown;
  providers?: unknown;
};
type McpSettingsPayload = {
  servers?: unknown;
  runtime?: unknown;
};
type McpRuntimePayload = {
  connected?: unknown;
  connecting?: unknown;
  connect_failures?: unknown;
  retry_after?: unknown;
  tool_names?: unknown;
};
type McpServerPayload = {
  id?: unknown;
  name?: unknown;
  type?: unknown;
  command?: unknown;
  args?: unknown;
  url?: unknown;
  tool_timeout?: unknown;
  enabled_tools?: unknown;
  env_configured?: unknown;
  env_keys?: unknown;
  headers_configured?: unknown;
  headers_keys?: unknown;
};
type ProviderModelMetadataPayload = {
  model_metadata_fields?: unknown;
};

function toChannelSettingsPayload(value: unknown): ChannelSettingsPayload {
  const payload = toPayloadSource<ChannelSettingsPayload>(value);
  if (!payload) {
    return {};
  }
  return {
    connected: payload.connected,
    available: payload.available,
    channels: payload.channels,
  };
}

function toMediaSettingsPayload(value: unknown): MediaSettingsPayload {
  const payload = toPayloadSource<MediaSettingsPayload>(value);
  if (!payload) {
    return {};
  }
  return {
    sections: payload.sections,
    providers: payload.providers,
  };
}

function toMediaSectionsPayload(value: unknown): MediaSectionsPayload {
  const payload = toPayloadSource<MediaSectionsPayload>(value);
  if (!payload) {
    return {};
  }
  return {
    vision: payload.vision,
    ocr: payload.ocr,
    speech: payload.speech,
    video: payload.video,
  };
}

function toMcpSettingsPayload(value: unknown): McpSettingsPayload {
  const payload = toPayloadSource<McpSettingsPayload>(value);
  if (!payload) {
    return {};
  }
  return {
    servers: payload.servers,
    runtime: payload.runtime,
  };
}

function toMcpRuntimePayload(value: unknown): McpRuntimePayload | null {
  const payload = toPayloadSource<McpRuntimePayload>(value);
  return payload && Object.keys(payload).length > 0
    ? {
        connected: payload.connected,
        connecting: payload.connecting,
        connect_failures: payload.connect_failures,
        retry_after: payload.retry_after,
        tool_names: payload.tool_names,
      }
    : null;
}

function toMcpServerPayload(value: unknown): McpServerPayload | null {
  const payload = toPayloadSource<McpServerPayload>(value);
  return payload
    ? {
        id: payload.id,
        name: payload.name,
        type: payload.type,
        command: payload.command,
        args: payload.args,
        url: payload.url,
        tool_timeout: payload.tool_timeout,
        enabled_tools: payload.enabled_tools,
        env_configured: payload.env_configured,
        env_keys: payload.env_keys,
        headers_configured: payload.headers_configured,
        headers_keys: payload.headers_keys,
      }
    : null;
}

function mcpServerPayloadList(value: unknown): McpServerPayload[] {
  return Array.isArray(value)
    ? value
        .map(toMcpServerPayload)
        .filter((item): item is McpServerPayload => item !== null)
    : [];
}

function channelPayloadList(value: unknown): ChannelPayload[] {
  return Array.isArray(value)
    ? value
        .map((item) => toPayloadSource<ChannelPayload>(item))
        .filter((item): item is ChannelPayload => item !== null)
    : [];
}

export function providerModelMetadataFields(provider: unknown = {}): string[] {
  const payload = toPayloadSource<ProviderModelMetadataPayload>(provider);
  return Array.isArray(payload?.model_metadata_fields)
    ? payload.model_metadata_fields.map((field) => String(field || "").trim()).filter(Boolean)
    : [];
}

export function providerSupportsModelMetadata(provider: unknown, field: string): boolean {
  return providerModelMetadataFields(provider).includes(field);
}

function isMcpTransportType(value: string): value is McpTransportType {
  return MCP_TRANSPORT_TYPE_SET.has(value);
}

export function normalizeMcpTransport(value: unknown, fallback: McpTransportType = "stdio"): McpTransportType {
  const transport = String(value || "").trim();
  if (isMcpTransportType(transport)) {
    return transport;
  }
  if (["streamable-http", "streamable_http", "http"].includes(transport)) {
    return "streamableHttp";
  }
  return fallback;
}

export function normalizeMcpSettings(payload: McpSettingsPayload = {}, fallbackRuntime: McpRuntimePayload = {}): McpSettingsPayload {
  const settings = toMcpSettingsPayload(payload);
  const runtime = toMcpRuntimePayload(settings.runtime);
  return {
    servers: mcpServerPayloadList(settings.servers),
    runtime: runtime
      ? {
          connected: Boolean(runtime.connected),
          connecting: Boolean(runtime.connecting),
          connect_failures: Number(runtime.connect_failures || 0),
          retry_after: Number(runtime.retry_after || 0),
          tool_names: Array.isArray(runtime.tool_names) ? runtime.tool_names : [],
        }
      : fallbackRuntime,
  };
}

export function visibleChannels(channels: unknown = []): ChannelPayload[] {
  return channelPayloadList(channels).filter((channel) => channel.id !== "web" && channel.id !== "console");
}

export function normalizeChannelSettings(payload: ChannelSettingsPayload = {}): NormalizedChannelSettingsPayload {
  const settings = toChannelSettingsPayload(payload);
  const channels = visibleChannels(settings.channels);
  const hasGroupedChannels = Array.isArray(settings.connected) || Array.isArray(settings.available);
  if (hasGroupedChannels) {
    return {
      connected: visibleChannels(settings.connected),
      available: visibleChannels(settings.available),
      channels,
    };
  }

  return {
    connected: channels.filter((channel) => channel.token_configured),
    available: channels.filter((channel) => !channel.token_configured),
    channels,
  };
}

export function sortChannelList(channels: ChannelPayload[]): ChannelPayload[] {
  return [...channels].sort((left, right) => String(left.name || left.id).localeCompare(String(right.name || right.id)));
}

export function normalizeMediaSettings(payload: MediaSettingsPayload = {}): MediaSettingsPayload {
  const settings = toMediaSettingsPayload(payload);
  const sections = toMediaSectionsPayload(settings.sections);
  return {
    sections: {
      vision: sections.vision || { category: "vision", enabled: false, provider_id: "", model: "" },
      ocr: sections.ocr || { category: "ocr", enabled: false, provider_id: "", model: "" },
      speech: sections.speech || { category: "speech", enabled: false, provider_id: "", model: "" },
      video: sections.video || { category: "video", enabled: false, provider_id: "", model: "" },
    },
    providers: Array.isArray(settings.providers) ? settings.providers : [],
  };
}
