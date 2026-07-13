import { toPayloadSource } from "./payloadBoundary";

export const DEFAULT_HTTP_PROXY = "";
export const DEFAULT_HTTPS_PROXY = "";
export const DEFAULT_NO_PROXY = "127.0.0.1,localhost";

type NetworkSettingsDataPayload = {
  http_proxy?: unknown;
  https_proxy?: unknown;
  no_proxy?: unknown;
};

export interface NetworkState {
  http_proxy: string;
  https_proxy: string;
  no_proxy: string;
}

export interface NetworkForm {
  httpProxy: string;
  httpsProxy: string;
  noProxy: string;
}

export function createDefaultNetworkState(): NetworkState {
  return {
    http_proxy: DEFAULT_HTTP_PROXY,
    https_proxy: DEFAULT_HTTPS_PROXY,
    no_proxy: DEFAULT_NO_PROXY,
  };
}

export function createDefaultNetworkForm(): NetworkForm {
  return {
    httpProxy: DEFAULT_HTTP_PROXY,
    httpsProxy: DEFAULT_HTTPS_PROXY,
    noProxy: DEFAULT_NO_PROXY,
  };
}

function toNetworkSettingsDataPayload(value: unknown): NetworkSettingsDataPayload {
  return toPayloadSource<NetworkSettingsDataPayload>(value) || {};
}

function stringOrDefault(value: unknown, fallback: string): string {
  return typeof value === "string" && value ? value : fallback;
}

export function normalizeNetworkSettings(network: unknown = {}): NetworkState {
  const payload = toNetworkSettingsDataPayload(network);
  return {
    http_proxy: stringOrDefault(payload.http_proxy, DEFAULT_HTTP_PROXY),
    https_proxy: stringOrDefault(payload.https_proxy, DEFAULT_HTTPS_PROXY),
    no_proxy: stringOrDefault(payload.no_proxy, DEFAULT_NO_PROXY),
  };
}
