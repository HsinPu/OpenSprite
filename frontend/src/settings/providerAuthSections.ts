import {
  type AnyRecord,
  authStatusLabel,
  codexDescription,
  copilotDescription,
  providerAuthVisible,
} from "./providerHelpers";

const PROVIDER_AUTH_SECTIONS = [
  {
    key: "codex",
    providerId: "openai-codex",
    copyKey: "codexAuth",
    loadingKey: "codexAuthLoading",
    noticeKey: "codexAuthNotice",
    errorKey: "codexAuthError",
    mark: "Cx",
    defaultTitle: "OpenAI Codex auth",
    defaultName: "OpenAI Codex",
    describe: codexDescription,
    refreshAction: "loadCodexAuthStatus",
    loginAction: "startCodexAuthLogin",
    logoutAction: "logoutCodexAuth",
  },
  {
    key: "copilot",
    providerId: "copilot",
    copyKey: "copilotAuth",
    loadingKey: "copilotAuthLoading",
    noticeKey: "copilotAuthNotice",
    errorKey: "copilotAuthError",
    mark: "Gh",
    defaultTitle: "GitHub Copilot auth",
    defaultName: "GitHub Copilot",
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
