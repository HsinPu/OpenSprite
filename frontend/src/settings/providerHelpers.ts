import {
  PROVIDER_AUTH_SECTION_CONFIGS,
  providerAuthKeyForId,
} from "./providerConstants";

export type AnyRecord = Record<string, any>;

export function providerCatalogKey(provider: AnyRecord) {
  return provider?.provider || provider?.id;
}

export function providerMark(value: AnyRecord) {
  return String(value?.name || value?.id || value?.type || "??").trim().slice(0, 2).toUpperCase();
}

export function hasConnectedProvider(state: AnyRecord, presetId: string) {
  return (state.providers?.connected || []).some((provider: AnyRecord) => providerCatalogKey(provider) === presetId);
}

export function providerAuthVisible(state: AnyRecord, providerId: string, auth: AnyRecord = {}, loading = false, notice = "", error = "") {
  return Boolean(hasConnectedProvider(state, providerId) || loading || auth?.configured || auth?.userCode || notice || error);
}

export function providerAuthKey(provider: AnyRecord) {
  return providerAuthKeyForId(provider?.provider);
}

export function providerAuthConfigured(state: AnyRecord, provider: AnyRecord) {
  const authKey = providerAuthKey(provider);
  return !authKey || Boolean(state[authKey]?.configured);
}

export function authStatusLabel(copy: AnyRecord = {}, auth: AnyRecord = {}, loading = false) {
  if (loading) {
    return copy.loading || "Loading";
  }
  if (!auth.configured) {
    return copy.notConfigured || "Not configured";
  }
  if (auth.expired) {
    return copy.expired || "Expired";
  }
  return copy.configured || "Configured";
}

const [CODEX_AUTH_CONFIG, COPILOT_AUTH_CONFIG] = PROVIDER_AUTH_SECTION_CONFIGS;

export function codexDescription(copy: AnyRecord, state: AnyRecord) {
  const auth = state[CODEX_AUTH_CONFIG.authKey] || {};
  const authCopy = copy.settings.providers?.[CODEX_AUTH_CONFIG.copyKey] || {};
  if (!auth.configured) {
    return authCopy.description || "";
  }
  const parts = [];
  if (auth.account_id && typeof authCopy.account === "function") {
    parts.push(authCopy.account(auth.account_id));
  }
  if (auth.expires_at && typeof authCopy.expires === "function") {
    parts.push(authCopy.expires(auth.expires_at));
  }
  return parts.join(" - ") || authCopy.configuredDescription || "";
}

export function copilotDescription(copy: AnyRecord, state: AnyRecord) {
  const auth = state[COPILOT_AUTH_CONFIG.authKey] || {};
  const authCopy = copy.settings.providers?.[COPILOT_AUTH_CONFIG.copyKey] || {};
  if (!auth.configured) {
    return authCopy.description || "";
  }
  return auth.path && typeof authCopy.path === "function" ? authCopy.path(auth.path) : authCopy.configuredDescription || "";
}

export function providerCredentials(state: AnyRecord, provider: AnyRecord) {
  const providerKey = providerCatalogKey(provider);
  return state.credentials?.[providerKey] || [];
}

export function selectedConnectProvider(providers: AnyRecord, providerId: string) {
  return [...(providers.available || []), ...(providers.connected || [])]
    .find((provider: AnyRecord) => provider.id === providerId) || null;
}

export function providerEffectiveCredentialId(provider: AnyRecord) {
  return provider?.credential_effective_id || provider?.effective_credential_id || provider?.credential_id || "";
}

export function credentialSourceLabel(copy: AnyRecord, provider: AnyRecord) {
  const sources = copy.settings.providers?.credentialSources || {};
  return sources[provider?.credential_source] || "";
}

export function providerDescription(copy: AnyRecord, state: AnyRecord, provider: AnyRecord) {
  const providerCopy = copy.settings.providers || {};
  const authKey = providerAuthKey(provider);
  if (authKey && !providerAuthConfigured(state, provider)) {
    return providerCopy[authKey]?.providerNeedsLogin || provider.base_url || "";
  }
  return provider?.base_url || provider?.description || "";
}

export function modelOptionsForProvider(provider: AnyRecord, selectedModel = "") {
  const models = Array.isArray(provider?.models) ? [...provider.models] : [];
  const selected = String(selectedModel || "").trim();
  if (selected && !models.includes(selected)) {
    models.unshift(selected);
  }
  return models;
}

function formatCompactTokenCount(value: any) {
  const tokens = Number(value);
  if (!Number.isFinite(tokens) || tokens <= 0) {
    return "";
  }
  if (tokens >= 1_000_000) {
    const millions = tokens / 1_000_000;
    return `${Number(millions.toFixed(millions >= 10 ? 0 : 1))}M`;
  }
  if (tokens >= 1_000) {
    return `${Math.round(tokens / 1_000)}K`;
  }
  return String(Math.round(tokens));
}

export function textModelOptionLabel(copy: AnyRecord, provider: AnyRecord, model: string) {
  const contextLength = provider?.model_metadata?.[model]?.context_length;
  const formatted = formatCompactTokenCount(contextLength);
  const context = formatted && typeof copy.settings.models?.modelMetadata?.contextLength === "function"
    ? copy.settings.models.modelMetadata.contextLength(formatted)
    : "";
  const label = [model, context].filter(Boolean).join(" - ");
  return provider?.is_default && provider.selected_model === model
    ? `${label} (${copy.settings.models?.active || "active"})`
    : label;
}

export function mediaModelCategories(copy: AnyRecord) {
  const categories = copy.settings.models?.mediaCategories || {};
  return [
    { key: "vision", mark: "VI", title: categories.vision?.title || "Vision", description: categories.vision?.description || "" },
    { key: "ocr", mark: "OC", title: categories.ocr?.title || "OCR", description: categories.ocr?.description || "" },
    { key: "speech", mark: "SP", title: categories.speech?.title || "Speech", description: categories.speech?.description || "" },
    { key: "video", mark: "VD", title: categories.video?.title || "Video", description: categories.video?.description || "" },
  ];
}

export function mediaModelsForProvider(state: AnyRecord, category: string, providerId: string, selectedModel = "") {
  const provider = (state.media.providers || []).find((entry: AnyRecord) => entry.id === providerId);
  const mediaModels = provider?.media_models?.[category];
  const models = Array.isArray(mediaModels) ? [...mediaModels] : Array.isArray(provider?.models) ? [...provider.models] : [];
  const selected = String(selectedModel || "").trim();
  if (selected && !models.includes(selected)) {
    models.unshift(selected);
  }
  return models;
}
