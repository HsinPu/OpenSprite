import { toPayloadSource } from "../composables/payloadBoundary";
import type {
  MediaCategory,
  MediaSettings as SettingsMediaSettings,
  ModelProviderView as SettingsModelProviderView,
} from "../composables/useSettingsState";

type MediaProviderView = Pick<SettingsModelProviderView, "id" | "media_models" | "models">;
type MediaStateView = {
  media?: Pick<SettingsMediaSettings, "providers">;
};
type MediaCopyRootPayload = {
  settings?: unknown;
};
type MediaCopySettingsPayload = {
  models?: unknown;
};
type MediaModelsCopyPayload = {
  mediaCategories?: unknown;
};
type MediaCategoriesCopyPayload = {
  [Category in MediaCategory]?: unknown;
};
type MediaCategoryCopyView = {
  title?: unknown;
  description?: unknown;
};
type MediaModelCategory = {
  key: MediaCategory;
  mark: string;
  title: string;
  description: string;
};

function text(value: unknown, fallback = ""): string {
  return String(value || fallback);
}

export function mediaModelCategories(copy: unknown): MediaModelCategory[] {
  const root = toPayloadSource<MediaCopyRootPayload>(copy);
  const settings = toPayloadSource<MediaCopySettingsPayload>(root?.settings);
  const models = toPayloadSource<MediaModelsCopyPayload>(settings?.models);
  const categories = toPayloadSource<MediaCategoriesCopyPayload>(models?.mediaCategories);
  const vision = toPayloadSource<MediaCategoryCopyView>(categories?.vision) || {};
  const ocr = toPayloadSource<MediaCategoryCopyView>(categories?.ocr) || {};
  const speech = toPayloadSource<MediaCategoryCopyView>(categories?.speech) || {};
  const video = toPayloadSource<MediaCategoryCopyView>(categories?.video) || {};
  return [
    { key: "vision", mark: "VI", title: text(vision.title, "Vision"), description: text(vision.description) },
    { key: "ocr", mark: "OC", title: text(ocr.title, "OCR"), description: text(ocr.description) },
    { key: "speech", mark: "SP", title: text(speech.title, "Speech"), description: text(speech.description) },
    { key: "video", mark: "VD", title: text(video.title, "Video"), description: text(video.description) },
  ];
}

export function mediaModelsForProvider(state: MediaStateView, category: MediaCategory, providerId: string, selectedModel = ""): string[] {
  const provider = (state.media?.providers ?? []).find((entry: MediaProviderView) => entry.id === providerId);
  const models = [...(provider?.media_models?.[category] ?? provider?.models ?? [])];
  const selected = String(selectedModel || "").trim();
  if (selected && !models.includes(selected)) {
    models.unshift(selected);
  }
  return models;
}
