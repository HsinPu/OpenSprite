import { providerSettingsEndpoint } from "../settings/providerEndpoints";
import type { ProviderAuthConfig } from "./providerAuthConfigs";
import {
  type ProviderAuthPendingPayload,
  type ProviderAuthStatusPayload,
  type ProviderDeviceAuthLoginPayload,
} from "./providerAuthState";
import { type ProviderOAuthConnectOptions, type ProviderPayload, providerOAuthConnectPayload } from "./providerConnectForm";
import { toPayloadSource } from "./payloadBoundary";

type RequestSettingsJson = (pathname: string, options?: RequestInit) => Promise<unknown>;
type ProviderAuthRequestConfig = ProviderOAuthConnectOptions & Pick<
  ProviderAuthConfig,
  "providerId" | "endpoint" | "loginEndpoint" | "pollEndpoint" | "logoutEndpoint" | "buildPollBody"
>;
export type ProviderAuthPollPayload = {
  auth?: ProviderAuthStatusPayload;
  status?: string;
};
export type ProviderAuthMutationPayload = {
  restart_required?: unknown;
};

function optionalText(value: unknown): string {
  return String(value || "").trim();
}

function toProviderAuthStatusPayload(value: unknown): ProviderAuthStatusPayload {
  const payload = toPayloadSource<ProviderAuthStatusPayload>(value);
  if (!payload) {
    return {};
  }
  return {
    configured: payload.configured,
    path: payload.path,
    expired: payload.expired,
    expires_at: payload.expires_at,
    account_id: payload.account_id,
  };
}

function toProviderDeviceAuthLoginPayload(value: unknown): ProviderDeviceAuthLoginPayload {
  const payload = toPayloadSource<ProviderDeviceAuthLoginPayload>(value);
  if (!payload) {
    return {};
  }
  return {
    verification_uri: payload.verification_uri,
    user_code: payload.user_code,
    interval: payload.interval,
    device_auth_id: payload.device_auth_id,
    device_code: payload.device_code,
  };
}

function toProviderAuthPollPayload(value: unknown): ProviderAuthPollPayload {
  const payload = toPayloadSource<ProviderAuthPollPayload>(value);
  if (!payload) {
    return {};
  }
  return {
    auth: payload.auth === undefined ? undefined : toProviderAuthStatusPayload(payload.auth),
    status: typeof payload.status === "string" ? payload.status : undefined,
  };
}

function toProviderAuthMutationPayload(value: unknown): ProviderAuthMutationPayload {
  const payload = toPayloadSource<ProviderAuthMutationPayload>(value);
  if (!payload) {
    return {};
  }
  return {
    restart_required: payload.restart_required,
  };
}

export async function requestProviderAuthStatus(requestSettingsJson: RequestSettingsJson, config: ProviderAuthRequestConfig): Promise<ProviderAuthStatusPayload> {
  return toProviderAuthStatusPayload(await requestSettingsJson(optionalText(config.endpoint)));
}

export async function requestProviderOAuthConnect(
  requestSettingsJson: RequestSettingsJson,
  provider: ProviderPayload | null | undefined,
  options: ProviderAuthRequestConfig,
): Promise<ProviderAuthMutationPayload> {
  const providerId = optionalText(provider?.id || options.providerId);
  return toProviderAuthMutationPayload(await requestSettingsJson(providerSettingsEndpoint(providerId, "connect"), {
    method: "PUT",
    body: JSON.stringify(providerOAuthConnectPayload(provider, options)),
  }));
}

export async function requestProviderAuthLogin(requestSettingsJson: RequestSettingsJson, config: ProviderAuthRequestConfig): Promise<ProviderDeviceAuthLoginPayload> {
  return toProviderDeviceAuthLoginPayload(await requestSettingsJson(optionalText(config.loginEndpoint), { method: "POST" }));
}

export async function requestProviderAuthPoll(
  requestSettingsJson: RequestSettingsJson,
  config: ProviderAuthRequestConfig,
  pendingAuth: ProviderAuthPendingPayload,
): Promise<ProviderAuthPollPayload> {
  if (!config.buildPollBody) {
    throw new Error("Missing provider auth poll payload builder");
  }
  return toProviderAuthPollPayload(await requestSettingsJson(optionalText(config.pollEndpoint), {
    method: "POST",
    body: JSON.stringify(config.buildPollBody(pendingAuth)),
  }));
}

export async function requestProviderAuthLogout(
  requestSettingsJson: RequestSettingsJson,
  config: ProviderAuthRequestConfig,
): Promise<ProviderAuthMutationPayload> {
  return toProviderAuthMutationPayload(
    await requestSettingsJson(optionalText(config.logoutEndpoint), { method: "POST" }),
  );
}
