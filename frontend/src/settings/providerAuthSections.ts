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
    key: "codex",
    providerId: CODEX_PROVIDER_ID,
    ...CODEX_AUTH_STATE_KEYS,
    mark: "Cx",
    defaultTitle: `${CODEX_PROVIDER_NAME} auth`,
    defaultName: CODEX_PROVIDER_NAME,
    describe: codexDescription,
    refreshAction: "loadCodexAuthStatus",
    loginAction: "startCodexAuthLogin",
    logoutAction: "logoutCodexAuth",
  },
  {
    key: "copilot",
    providerId: COPILOT_PROVIDER_ID,
    ...COPILOT_AUTH_STATE_KEYS,
    mark: "Gh",
    defaultTitle: `${COPILOT_PROVIDER_NAME} auth`,
    defaultName: COPILOT_PROVIDER_NAME,
    describe: copilotDescription,
    refreshAction: "loadCopilotAuthStatus",
    loginAction: "startCopilotAuthLogin",
    logoutAction: "logoutCopilotAuth",
  },
];

export function providerAuthSections(copy: AnyRecord, state: AnyRecord, client: AnyRecord) {
  const providerCopy = copy.settings.providers || {};

  return PROVIDER_AUTH_SECTIONS.map((config) => {
    const auth = state[config.copyKey] || {};
    const loading = Boolean(state[config.loadingKey]);
    const authCopy = providerCopy[config.copyKey] || {};

    return {
      key: config.key,
      visible: providerAuthVisible(
        state,
        config.providerId,
        auth,
        loading,
        state[config.noticeKey],
        state[config.errorKey],
      ),
      title: authCopy.title || config.defaultTitle,
      notice: state[config.noticeKey],
      error: state[config.errorKey],
      mark: config.mark,
      name: authCopy.name || config.defaultName,
      status: authStatusLabel(authCopy, auth, loading),
      description: config.describe(copy, state),
      loading,
      configured: auth?.configured,
      copy: authCopy,
      auth,
      onRefresh: client[config.refreshAction],
      onLogin: client[config.loginAction],
      onLogout: client[config.logoutAction],
    };
  });
}
