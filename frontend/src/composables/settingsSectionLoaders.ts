import { PROVIDER_AUTH_PROVIDER_IDS } from "../settings/providerAuthMetadata";

type SettingsLoaderResult = void | Promise<void>;
export const SETTINGS_SECTION_IDS = [
  "general",
  "shortcuts",
  "providers",
  "models",
  "channels",
  "mcp",
  "schedule",
  "network",
  "search",
  "browser",
  "log",
] as const;
export type SettingsSectionId = (typeof SETTINGS_SECTION_IDS)[number];
const SETTINGS_SECTION_ID_SET: ReadonlySet<string> = new Set(SETTINGS_SECTION_IDS);

export function isSettingsSectionId(value: unknown): value is SettingsSectionId {
  return typeof value === "string" && SETTINGS_SECTION_ID_SET.has(value);
}

export function normalizeSettingsSectionId(value: unknown): SettingsSectionId {
  return isSettingsSectionId(value) ? value : "general";
}

type SettingsSectionLoader = () => SettingsLoaderResult;

interface SettingsLoaders {
  loadUpdateStatus: () => SettingsLoaderResult;
  loadChannelSettings: () => SettingsLoaderResult;
  loadProviderSettings: () => SettingsLoaderResult;
  loadProviderAuthStatusById: (providerId: string) => SettingsLoaderResult;
  loadModelSettings: () => SettingsLoaderResult;
  loadMcpSettings: () => SettingsLoaderResult;
  loadScheduleSettings: () => SettingsLoaderResult;
  loadCronJobs: () => SettingsLoaderResult;
  loadNetworkSettings: () => SettingsLoaderResult;
  loadSearchSettings: () => SettingsLoaderResult;
  loadBrowserSettings: () => SettingsLoaderResult;
  loadLogSettings: () => SettingsLoaderResult;
}

export function createSettingsSectionLoader(loaders: SettingsLoaders): (sectionName: SettingsSectionId) => SettingsLoaderResult | undefined {
  const sectionLoaders: Record<SettingsSectionId, SettingsSectionLoader> = {
    general: () => loaders.loadUpdateStatus(),
    shortcuts: () => undefined,
    channels: () => loaders.loadChannelSettings(),
    providers: () => {
      loaders.loadProviderSettings();
      for (const providerId of PROVIDER_AUTH_PROVIDER_IDS) {
        loaders.loadProviderAuthStatusById(providerId);
      }
    },
    models: () => loaders.loadModelSettings(),
    mcp: () => loaders.loadMcpSettings(),
    schedule: () => {
      loaders.loadScheduleSettings();
      loaders.loadCronJobs();
    },
    network: () => loaders.loadNetworkSettings(),
    search: () => loaders.loadSearchSettings(),
    browser: () => loaders.loadBrowserSettings(),
    log: () => loaders.loadLogSettings(),
  };
  return (sectionName) => sectionLoaders[sectionName]?.();
}
