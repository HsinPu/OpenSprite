import { PROVIDER_AUTH_PROVIDER_IDS } from "../settings/providerConstants";

export function createSettingsSectionLoader(loaders) {
  const sectionLoaders = {
    general: () => loaders.loadUpdateStatus(),
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
