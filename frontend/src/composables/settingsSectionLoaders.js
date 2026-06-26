import { CODEX_PROVIDER_ID, COPILOT_PROVIDER_ID } from "../settings/providerConstants";

const PROVIDER_AUTH_REFRESH_IDS = [CODEX_PROVIDER_ID, COPILOT_PROVIDER_ID];

export function createSettingsSectionLoader(loaders) {
  const sectionLoaders = {
    general: () => loaders.loadUpdateStatus(),
    channels: () => loaders.loadChannelSettings(),
    providers: () => {
      loaders.loadProviderSettings();
      for (const providerId of PROVIDER_AUTH_REFRESH_IDS) {
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
