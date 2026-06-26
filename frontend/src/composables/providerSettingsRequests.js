import { providerCredentialEndpoint, providerSettingsEndpoint } from "../settings/providerEndpoints";
import {
  providerConnectPayloadFromForm,
  providerCredentialPayload,
} from "./providerConnectForm";

export function requestProviderConnect(requestSettingsJson, form) {
  return requestSettingsJson(providerSettingsEndpoint(form.providerId, "connect"), {
    method: "PUT",
    body: JSON.stringify(providerConnectPayloadFromForm(form)),
  });
}

export function requestProviderDisconnect(requestSettingsJson, provider) {
  return requestSettingsJson(providerSettingsEndpoint(provider.id, "disconnect"), {
    method: "POST",
  });
}

export function requestProviderCredentialUpdate(requestSettingsJson, provider, credentialId) {
  return requestSettingsJson(providerSettingsEndpoint(provider.id, "credential"), {
    method: "POST",
    body: JSON.stringify(providerCredentialPayload(credentialId)),
  });
}

export function requestProviderCredentialDelete(requestSettingsJson, providerKey, credentialId) {
  return requestSettingsJson(
    providerCredentialEndpoint(providerKey, credentialId),
    { method: "DELETE" },
  );
}
