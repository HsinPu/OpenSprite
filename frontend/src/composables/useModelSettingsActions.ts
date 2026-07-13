import { normalizeMediaSettings } from "./settingsNormalizers";
import { normalizeModelReasoningEffort, type ModelReasoningEffort } from "./modelReasoning";
import { toPayloadSource } from "./payloadBoundary";
import { MEDIA_CATEGORIES } from "./useSettingsState";
import type {
  MediaCategory,
  MediaCustomModels,
  MediaSectionView,
  MediaSelection,
  MediaSelections,
  MediaSettings,
  ModelMetadataByModel,
  ModelMetadataEntryView,
  ModelMediaModelsByCategory,
  ModelProviderView,
  ModelSettings,
} from "./useSettingsState";

type ModelMetadataMapPayload = {
  [modelId: string]: unknown;
};
type MediaModelMapPayload = {
  [Category in MediaCategory]?: unknown;
};
type MediaSectionsMapPayload = {
  [Category in MediaCategory]?: unknown;
};
type RequestSettingsJson = (pathname: string, options?: RequestInit) => Promise<unknown>;
type ModelSelectPayload = {
  restart_required?: unknown;
  reasoning_effort?: unknown;
};
type ModelSettingsPayload = {
  default_provider?: unknown;
  active_model?: unknown;
  providers?: unknown;
};
type ModelProviderPayload = {
  id?: unknown;
  name?: unknown;
  type?: unknown;
  is_default?: unknown;
  selected_model?: unknown;
  models?: unknown;
  model_metadata?: unknown;
  media_models?: unknown;
  reasoning_effort?: unknown;
};
type MediaSavePayload = {
  media?: unknown;
  restart_required?: unknown;
};
type MediaSettingsPayload = {
  sections?: unknown;
  providers?: unknown;
};
type MediaSectionPayload = {
  category?: unknown;
  enabled?: unknown;
  provider_id?: unknown;
  model?: unknown;
};

interface ModelSettingsState {
  modelsLoading: boolean;
  modelsError: string;
  modelsNotice: string;
  models: ModelSettings;
  selectedTextProviderId: string;
  modelSelections: Record<string, string>;
  reasoningSelections: Record<string, ModelReasoningEffort>;
  customModels: Record<string, string>;
  mediaLoading: boolean;
  mediaError: string;
  mediaNotice: string;
  media: MediaSettings;
  mediaSelections: MediaSelections;
  mediaCustomModels: MediaCustomModels;
}

interface ModelSettingsCopy {
  notices: {
    modelLoadFailed: string;
    mediaModelLoadFailed: string;
    modelRequired: string;
    modelRestartRequired: string;
    modelApplied: string;
    modelSelectFailed: string;
    mediaModelRestartRequired: string;
    mediaModelApplied: string;
    mediaModelSaveFailed: string;
  };
}

type SettingsActionContext = {
  settingsState: ModelSettingsState;
  requestSettingsJson: RequestSettingsJson;
  copy: { value: ModelSettingsCopy };
  setSettingsSuccess: (key: string, message: string) => void;
  loadProviderSettings?: () => Promise<void>;
};

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "";
}

function toModelSelectPayload(value: unknown): ModelSelectPayload {
  const payload = toPayloadSource<ModelSelectPayload>(value);
  if (!payload) {
    return {};
  }
  return {
    restart_required: payload.restart_required,
    reasoning_effort: payload.reasoning_effort,
  };
}

function toModelSettingsPayload(value: unknown): ModelSettingsPayload {
  const payload = toPayloadSource<ModelSettingsPayload>(value);
  if (!payload) {
    return {};
  }
  return {
    default_provider: payload.default_provider,
    active_model: payload.active_model,
    providers: payload.providers,
  };
}

function toModelProviderPayload(value: unknown): ModelProviderPayload {
  const payload = toPayloadSource<ModelProviderPayload>(value);
  if (!payload) {
    return {};
  }
  return {
    id: payload.id,
    name: payload.name,
    type: payload.type,
    is_default: payload.is_default,
    selected_model: payload.selected_model,
    models: payload.models,
    model_metadata: payload.model_metadata,
    media_models: payload.media_models,
    reasoning_effort: payload.reasoning_effort,
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

function toMediaSectionPayload(value: unknown): MediaSectionPayload {
  const payload = toPayloadSource<MediaSectionPayload>(value);
  if (!payload) {
    return {};
  }
  return {
    category: payload.category,
    enabled: payload.enabled,
    provider_id: payload.provider_id,
    model: payload.model,
  };
}

function toMediaSavePayload(value: unknown): MediaSavePayload {
  const payload = toPayloadSource<MediaSavePayload>(value);
  if (!payload) {
    return {};
  }
  return {
    media: payload.media,
    restart_required: payload.restart_required,
  };
}

function normalizeTextList(value: unknown): string[] {
  const values = Array.isArray(value) ? value : [];
  return values.map((item) => String(item || "").trim()).filter(Boolean);
}

function optionalText(value: unknown): string | undefined {
  const text = String(value || "").trim();
  return text || undefined;
}

function optionalPositiveNumber(value: unknown): number | undefined {
  const numberValue = Number(value);
  return Number.isFinite(numberValue) && numberValue > 0 ? numberValue : undefined;
}

function normalizeModelMetadataEntry(value: unknown): ModelMetadataEntryView | null {
  const payload = toPayloadSource<ModelMetadataEntryView>(value);
  if (!payload) {
    return null;
  }
  const contextLength = optionalPositiveNumber(payload.context_length);
  return contextLength !== undefined ? { context_length: contextLength } : null;
}

function normalizeModelMetadata(value: unknown): ModelMetadataByModel | undefined {
  const payload = toPayloadSource<ModelMetadataMapPayload>(value);
  if (!payload) {
    return undefined;
  }
  const entries = Object.entries(payload).flatMap(([model, metadata]) => {
    const normalizedModel = String(model || "").trim();
    const normalizedMetadata = normalizeModelMetadataEntry(metadata);
    return normalizedModel && normalizedMetadata
      ? [[normalizedModel, normalizedMetadata] as const]
      : [];
  });
  return entries.length ? Object.fromEntries(entries) : undefined;
}

function normalizeMediaModelMap(value: unknown): ModelMediaModelsByCategory | undefined {
  const payload = toPayloadSource<MediaModelMapPayload>(value);
  if (!payload) {
    return undefined;
  }
  const mediaModels: ModelMediaModelsByCategory = {};
  for (const category of MEDIA_CATEGORIES) {
    const models = payload[category];
    if (Array.isArray(models)) {
      mediaModels[category] = normalizeTextList(models);
    }
  }
  return MEDIA_CATEGORIES.some((category) => mediaModels[category] !== undefined)
    ? mediaModels
    : undefined;
}

function normalizeModelProvider(value: unknown): ModelProviderView | null {
  const provider = toModelProviderPayload(value);
  const id = String(provider.id || "").trim();
  if (!id) return null;
  return {
    id,
    name: optionalText(provider.name),
    type: optionalText(provider.type),
    is_default: provider.is_default === true,
    selected_model: String(provider.selected_model || ""),
    models: normalizeTextList(provider.models),
    model_metadata: normalizeModelMetadata(provider.model_metadata),
    media_models: normalizeMediaModelMap(provider.media_models),
    reasoning_effort: normalizeModelReasoningEffort(provider.reasoning_effort),
  };
}

function normalizeModelProviders(value: unknown): ModelProviderView[] {
  if (!Array.isArray(value)) return [];
  return value.map(normalizeModelProvider).filter((provider): provider is ModelProviderView => provider !== null);
}

function normalizeModelSettings(payload: unknown): ModelSettings {
  const settings = toModelSettingsPayload(payload);
  return {
    default_provider: String(settings.default_provider || ""),
    active_model: String(settings.active_model || ""),
    providers: normalizeModelProviders(settings.providers),
  };
}

function normalizeMediaCategory(value: unknown, fallback: MediaCategory): MediaCategory {
  return value === "vision" || value === "ocr" || value === "speech" || value === "video"
    ? value
    : fallback;
}

function normalizeMediaSection(value: unknown, category: MediaCategory): MediaSectionView {
  const section = toMediaSectionPayload(value);
  return {
    category: normalizeMediaCategory(section.category, category),
    enabled: section.enabled === true,
    provider_id: String(section.provider_id || ""),
    model: String(section.model || ""),
  };
}

function normalizeMediaSettingsView(payload: unknown): MediaSettings {
  const settings = toMediaSettingsPayload(normalizeMediaSettings(toMediaSettingsPayload(payload)));
  const sectionsSource = toPayloadSource<MediaSectionsMapPayload>(settings.sections) || {};
  return {
    sections: {
      vision: normalizeMediaSection(sectionsSource.vision, "vision"),
      ocr: normalizeMediaSection(sectionsSource.ocr, "ocr"),
      speech: normalizeMediaSection(sectionsSource.speech, "speech"),
      video: normalizeMediaSection(sectionsSource.video, "video"),
    },
    providers: normalizeModelProviders(settings.providers),
  };
}

function createEmptyMediaSelection(): MediaSelection {
  return { enabled: false, providerId: "", model: "" };
}

const mediaSelectionFromSection = (section: MediaSectionView, providerId = "", model = ""): MediaSelection => ({
  enabled: Boolean(section.enabled),
  providerId: section.provider_id || providerId || "",
  model: section.model || model || "",
});

export function useModelSettingsActions({ settingsState, requestSettingsJson, copy, setSettingsSuccess, loadProviderSettings }: SettingsActionContext) {
  async function loadModelSettings(): Promise<void> {
    settingsState.modelsLoading = true;
    settingsState.mediaLoading = true;
    settingsState.modelsError = "";
    settingsState.mediaError = "";
    try {
      const [models, media] = await Promise.all([
        requestSettingsJson("/api/settings/models"),
        requestSettingsJson("/api/settings/media"),
      ]);
      settingsState.models = normalizeModelSettings(models);
      settingsState.media = normalizeMediaSettingsView(media);
      const activeProvider = (settingsState.models.providers || []).find((provider) => provider.is_default);
      settingsState.selectedTextProviderId = activeProvider?.id || settingsState.models.providers?.[0]?.id || "";
      for (const provider of settingsState.models.providers || []) {
        const selectedModel = provider.selected_model || provider.models?.[0] || "";
        settingsState.modelSelections[provider.id] = selectedModel;
        settingsState.reasoningSelections[provider.id] = normalizeModelReasoningEffort(provider.reasoning_effort);
        settingsState.customModels[provider.id] = "";
      }
      for (const category of MEDIA_CATEGORIES) {
        const section = settingsState.media.sections[category];
        settingsState.mediaSelections[category] = mediaSelectionFromSection(section, settingsState.media.providers?.[0]?.id);
        settingsState.mediaCustomModels[category] = "";
      }
    } catch (error: unknown) {
      settingsState.modelsError = errorMessage(error) || copy.value.notices.modelLoadFailed;
      settingsState.mediaError = errorMessage(error) || copy.value.notices.mediaModelLoadFailed;
    } finally {
      settingsState.modelsLoading = false;
      settingsState.mediaLoading = false;
    }
  }

  async function selectModel(providerId: string, model: string, reasoningEffort: ModelReasoningEffort = ""): Promise<void> {
    const normalizedModel = String(model || "").trim();
    const normalizedReasoningEffort = normalizeModelReasoningEffort(reasoningEffort);
    if (!normalizedModel) {
      settingsState.modelsError = copy.value.notices.modelRequired;
      return;
    }

    settingsState.modelsLoading = true;
    settingsState.modelsError = "";
    settingsState.modelsNotice = "";
    try {
      const payload = toModelSelectPayload(await requestSettingsJson("/api/settings/models/select", {
        method: "POST",
        body: JSON.stringify({
          provider_id: providerId,
          model: normalizedModel,
          reasoning_effort: normalizedReasoningEffort,
        }),
      }));
      setSettingsSuccess(
        "modelsNotice",
        payload.restart_required ? copy.value.notices.modelRestartRequired : copy.value.notices.modelApplied,
      );
      settingsState.customModels[providerId] = "";
      settingsState.modelSelections[providerId] = normalizedModel;
      settingsState.reasoningSelections[providerId] = normalizeModelReasoningEffort(payload.reasoning_effort ?? normalizedReasoningEffort);
      await loadModelSettings();
      await loadProviderSettings?.();
    } catch (error: unknown) {
      settingsState.modelsError = errorMessage(error) || copy.value.notices.modelSelectFailed;
    } finally {
      settingsState.modelsLoading = false;
    }
  }

  async function saveMediaModel(category: MediaCategory, modelOverride = ""): Promise<void> {
    const selection = settingsState.mediaSelections[category] || createEmptyMediaSelection();
    const normalizedModel = String(modelOverride || selection.model || "").trim();
    if (selection.enabled && !normalizedModel) {
      settingsState.mediaError = copy.value.notices.modelRequired;
      return;
    }
    settingsState.mediaLoading = true;
    settingsState.mediaError = "";
    settingsState.mediaNotice = "";
    try {
      const payload = toMediaSavePayload(await requestSettingsJson("/api/settings/media", {
        method: "PUT",
        body: JSON.stringify({
          category,
          enabled: Boolean(selection.enabled),
          provider_id: selection.providerId,
          model: normalizedModel,
        }),
      }));
      settingsState.media = normalizeMediaSettingsView(payload.media);
      settingsState.mediaSelections[category] = mediaSelectionFromSection(settingsState.media.sections[category], selection.providerId, normalizedModel);
      settingsState.mediaCustomModels[category] = "";
      setSettingsSuccess(
        "mediaNotice",
        payload.restart_required ? copy.value.notices.mediaModelRestartRequired : copy.value.notices.mediaModelApplied,
      );
    } catch (error: unknown) {
      settingsState.mediaError = errorMessage(error) || copy.value.notices.mediaModelSaveFailed;
    } finally {
      settingsState.mediaLoading = false;
    }
  }

  return {
    loadModelSettings,
    selectModel,
    saveMediaModel,
  };
}
