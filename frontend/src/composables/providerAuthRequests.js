import { providerSettingsEndpoint } from "../settings/providerEndpoints";
import { providerOAuthConnectPayload } from "./providerConnectForm";

export function requestProviderAuthStatus(requestSettingsJson, config) {
  return requestSettingsJson(config.endpoint);
}

export function requestProviderOAuthConnect(requestSettingsJson, provider, options) {
  const providerId = provider?.id || options.providerId;
  return requestSettingsJson(providerSettingsEndpoint(providerId, "connect"), {
    method: "PUT",
    body: JSON.stringify(providerOAuthConnectPayload(provider, options)),
  });
}

export function requestProviderAuthLogin(requestSettingsJson, config) {
  return requestSettingsJson(config.loginEndpoint, { method: "POST" });
}

export function requestProviderAuthPoll(requestSettingsJson, config, pendingAuth) {
  return requestSettingsJson(config.pollEndpoint, {
    method: "POST",
    body: JSON.stringify(config.buildPollBody(pendingAuth)),
  });
}

export function requestProviderAuthLogout(requestSettingsJson, config) {
  return requestSettingsJson(config.logoutEndpoint, { method: "POST" });
}
