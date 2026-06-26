import {
  type AnyRecord,
} from "./providerHelpers";
import {
  authStatusLabel,
  providerAuthDescription,
  providerAuthVisible,
} from "./providerAuthHelpers";
import { PROVIDER_AUTH_SECTION_CONFIGS } from "./providerAuthMetadata";

export function providerAuthSections(copy: AnyRecord, state: AnyRecord, client: AnyRecord) {
  const providerCopy = copy.settings.providers || {};

  return PROVIDER_AUTH_SECTION_CONFIGS.map((config) => {
    const auth = state[config.stateKey] || {};
    const loading = Boolean(state[config.loadingKey]);
    const authCopy = providerCopy[config.copyKey] || {};

    return {
      key: config.providerId,
      visible: providerAuthVisible(state, config),
      title: authCopy.title || `${config.providerName} auth`,
      notice: state[config.noticeKey],
      error: state[config.errorKey],
      mark: config.mark,
      name: authCopy.name || config.providerName,
      status: authStatusLabel(authCopy, auth, loading),
      description: providerAuthDescription(copy, state, config),
      loading,
      configured: auth?.configured,
      copy: authCopy,
      auth,
      onRefresh: () => client.loadProviderAuthStatusById(config.providerId),
      onLogin: () => client.startProviderAuthLoginById(config.providerId),
      onLogout: () => client.logoutProviderAuthById(config.providerId),
    };
  });
}
