import { coerceNonNegativeInteger } from "./chatClientCoercion";

export function normalizeDeviceAuthLogin(payload, deviceKey, payloadDeviceKey, extra = {}) {
  return {
    ...extra,
    verificationUri: payload.verification_uri || "",
    userCode: payload.user_code || "",
    [deviceKey]: payload[payloadDeviceKey] || "",
    pollIntervalSeconds: coerceNonNegativeInteger(payload.interval) || 5,
  };
}

export function clearedDeviceAuthState(deviceKey) {
  return {
    verificationUri: "",
    userCode: "",
    [deviceKey]: "",
  };
}
