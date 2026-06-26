import {
  type AnyRecord,
  authStatusLabel,
  codexDescription,
  copilotDescription,
  providerAuthVisible,
} from "./providerHelpers";
import {
  CODEX_AUTH_STATE_KEYS,
  CODEX_PROVIDER_ID,
  CODEX_PROVIDER_NAME,
  COPILOT_AUTH_STATE_KEYS,
  COPILOT_PROVIDER_ID,
  COPILOT_PROVIDER_NAME,
} from "./providerConstants";

const PROVIDER_AUTH_SECTIONS = [
  {
    providerId: CODEX_PROVIDER_ID,
    ...CODEX_AUTH_STATE_KEYS,
    mark: "Cx",
    providerName: CODEX_PROVIDER_NAME,
    describe: codexDescription,
  },
  {
    providerId: COPILOT_PROVIDER_ID,
    ...COPILOT_AUTH_STATE_KEYS,
    mark: "Gh",
    providerName: COPILOT_PROVIDER_NAME,
    describe: copilotDescription,
  },
];

export function providerAuthSections(copy: AnyRecord, state: AnyRecord, client: AnyRecord) {
  const providerCopy = copy.settings.providers || {};

  return PROVIDER_AUTH_SECTIONS.map((config) => {
    const auth = state[config.copyKey] || {};
    const loading = Boolean(state[config.loadingKey]);
    const authCopy = providerCopy[config.copyKey] || {};

    return {
      key: config.providerId,
      visible: providerAuthVisible(
        state,
        config.providerId,
        auth,
        loading,
        state[config.noticeKey],
        state[config.errorKey],
      ),
      title: authCopy.title || `${config.providerName} auth`,
      notice: state[config.noticeKey],
      error: state[config.errorKey],
      mark: config.mark,
      name: authCopy.name || config.providerName,
      status: authStatusLabel(authCopy, auth, loading),
      description: config.describe(copy, state),
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
