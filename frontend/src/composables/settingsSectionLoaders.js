export function createSettingsSectionLoader(loaders) {
  const sectionLoaders = {
    general: () => loaders.loadUpdateStatus(),
    channels: () => loaders.loadChannelSettings(),
    providers: () => {
      loaders.loadProviderSettings();
      loaders.loadCodexAuthStatus();
      loaders.loadCopilotAuthStatus();
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
