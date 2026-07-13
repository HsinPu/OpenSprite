import { providerCredentialEndpoint, providerSettingsEndpoint } from "../settings/providerEndpoints";
import {
  type ProviderConnectForm,
  type ProviderPayload,
  providerConnectPayloadFromForm,
  providerCredentialPayload,
} from "./providerConnectForm";
import { toPayloadSource } from "./payloadBoundary";

type RequestSettingsJson = (pathname: string, options?: RequestInit) => Promise<unknown>;
type ProviderIdentityPayload = Pick<ProviderPayload, "id">;
export type ProviderMutationPayload = {
  restart_required?: unknown;
};

function providerId(provider: ProviderIdentityPayload): string {
  return String(provider.id || "").trim();
}

function toProviderMutationPayload(value: unknown): ProviderMutationPayload {
  const payload = toPayloadSource<ProviderMutationPayload>(value);
  if (!payload) {
    return {};
  }
  return {
    restart_required: payload.restart_required,
  };
}

export async function requestProviderConnect(requestSettingsJson: RequestSettingsJson, form: ProviderConnectForm): Promise<ProviderMutationPayload> {
  return toProviderMutationPayload(await requestSettingsJson(providerSettingsEndpoint(form.providerId, "connect"), {
    method: "PUT",
    body: JSON.stringify(providerConnectPayloadFromForm(form)),
  }));
}

export async function requestProviderDisconnect(requestSettingsJson: RequestSettingsJson, provider: ProviderIdentityPayload): Promise<ProviderMutationPayload> {
  return toProviderMutationPayload(await requestSettingsJson(providerSettingsEndpoint(providerId(provider), "disconnect"), {
    method: "POST",
  }));
}

export async function requestProviderCredentialUpdate(
  requestSettingsJson: RequestSettingsJson,
  provider: ProviderIdentityPayload,
  credentialId: string,
): Promise<ProviderMutationPayload> {
  return toProviderMutationPayload(await requestSettingsJson(providerSettingsEndpoint(providerId(provider), "credential"), {
    method: "POST",
    body: JSON.stringify(providerCredentialPayload(credentialId)),
  }));
}

export async function requestProviderCredentialDelete(
  requestSettingsJson: RequestSettingsJson,
  providerKey: string,
  credentialId: string,
): Promise<ProviderMutationPayload> {
  return toProviderMutationPayload(await requestSettingsJson(
    providerCredentialEndpoint(providerKey, credentialId),
    { method: "DELETE" },
  ));
}
