import { coerceNonNegativeInteger } from "./chatClientCoercion";

export type ProviderAuthDeviceKey = "deviceAuthId" | "deviceCode";
export type ProviderDeviceAuthPayloadDeviceKey = "device_auth_id" | "device_code";
export type ProviderDeviceAuthLoginPayload = {
  verification_uri?: unknown;
  user_code?: unknown;
  interval?: unknown;
  device_auth_id?: unknown;
  device_code?: unknown;
};
export type ProviderAuthPendingPayload = {
  verificationUri?: string;
  userCode?: string;
  pollIntervalSeconds?: number;
  deviceAuthId?: string;
  deviceCode?: string;
  command?: string;
};
export type ProviderAuthStatusPayload = {
  configured?: unknown;
  path?: unknown;
  expired?: unknown;
  expires_at?: unknown;
  account_id?: unknown;
};
export type ProviderAuthStatePayload = ProviderAuthPendingPayload & {
  configured?: boolean;
  path?: string;
  expired?: boolean;
  expires_at?: string | null;
  account_id?: string;
};

function deviceAuthState(
  deviceKey: ProviderAuthDeviceKey,
  value: string,
): Pick<ProviderAuthPendingPayload, ProviderAuthDeviceKey> {
  return deviceKey === "deviceAuthId"
    ? { deviceAuthId: value }
    : { deviceCode: value };
}

function deviceAuthPayloadValue(
  payload: ProviderDeviceAuthLoginPayload,
  payloadDeviceKey: ProviderDeviceAuthPayloadDeviceKey,
): unknown {
  return payloadDeviceKey === "device_auth_id" ? payload.device_auth_id : payload.device_code;
}

export function normalizeDeviceAuthLogin(
  payload: ProviderDeviceAuthLoginPayload,
  deviceKey: ProviderAuthDeviceKey,
  payloadDeviceKey: ProviderDeviceAuthPayloadDeviceKey,
  extra: ProviderAuthPendingPayload = {},
): ProviderAuthPendingPayload {
  return {
    ...extra,
    verificationUri: String(payload.verification_uri || ""),
    userCode: String(payload.user_code || ""),
    ...deviceAuthState(deviceKey, String(deviceAuthPayloadValue(payload, payloadDeviceKey) || "")),
    pollIntervalSeconds: coerceNonNegativeInteger(payload.interval) || 5,
  };
}

export function clearedDeviceAuthState(deviceKey: ProviderAuthDeviceKey): ProviderAuthPendingPayload {
  return {
    verificationUri: "",
    userCode: "",
    ...deviceAuthState(deviceKey, ""),
  };
}
