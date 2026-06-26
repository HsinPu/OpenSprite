import {
  type AnyRecord,
  authStatusLabel,
  codexDescription,
  copilotDescription,
  hasConnectedProvider,
} from "./providerHelpers";
import { AvailableProvidersSection } from "./availableProvidersSection";
import { ConnectedProvidersSection } from "./connectedProvidersSection";
import { ProviderAuthSection } from "./providerAuthSection";
import { ProviderConnectDialog } from "./providerConnectDialog";
import { SettingsStatus } from "./settingsPrimitives";

type ValueRef<T> = { value: T };

type ProviderSettingsClient = {
  copy: ValueRef<AnyRecord>;
  settingsState: AnyRecord;
  loadCodexAuthStatus: () => void;
  startCodexAuthLogin: () => void;
  logoutCodexAuth: () => void;
  loadCopilotAuthStatus: () => void;
  startCopilotAuthLogin: () => void;
  logoutCopilotAuth: () => void;
  setProviderCredential: (provider: AnyRecord, credentialId: string) => void;
  deleteCredential: (provider: AnyRecord, credentialId: string) => void;
  disconnectProvider: (provider: AnyRecord) => void;
  connectOAuthProvider: (provider: AnyRecord) => void;
  beginProviderConnect: (provider: AnyRecord) => void;
  cancelProviderConnect: () => void;
  saveProviderConnection: () => void;
};

export function ProviderSettings({ client }: { client: ProviderSettingsClient }) {
  const copy = client.copy.value;
  const state = client.settingsState;
  const providers = (state.providers || {}) as AnyRecord;
  const providerCopy = copy.settings.providers || {};
  const selectedConnectProvider =
    [...(providers.available || []), ...(providers.connected || [])].find((provider: AnyRecord) => provider.id === state.connectForm.providerId) || null;
  const showCodexAuthCard =
    hasConnectedProvider(state, "openai-codex") ||
    state.codexAuthLoading ||
    state.codexAuth?.configured ||
    Boolean(state.codexAuth?.userCode || state.codexAuthNotice || state.codexAuthError);
  const showCopilotAuthCard =
    hasConnectedProvider(state, "copilot") ||
    state.copilotAuthLoading ||
    state.copilotAuth?.configured ||
    Boolean(state.copilotAuth?.userCode || state.copilotAuthNotice || state.copilotAuthError);
  const authSections = [
    {
      key: "codex",
      visible: showCodexAuthCard,
      title: providerCopy.codexAuth?.title || "OpenAI Codex auth",
      notice: state.codexAuthNotice,
      error: state.codexAuthError,
      mark: "Cx",
      name: providerCopy.codexAuth?.name || "OpenAI Codex",
      status: authStatusLabel(providerCopy.codexAuth, state.codexAuth, state.codexAuthLoading),
      description: codexDescription(copy, state),
      loading: state.codexAuthLoading,
      configured: state.codexAuth?.configured,
      copy: providerCopy.codexAuth || {},
      auth: state.codexAuth || {},
      onRefresh: client.loadCodexAuthStatus,
      onLogin: client.startCodexAuthLogin,
      onLogout: client.logoutCodexAuth,
    },
    {
      key: "copilot",
      visible: showCopilotAuthCard,
      title: providerCopy.copilotAuth?.title || "GitHub Copilot auth",
      notice: state.copilotAuthNotice,
      error: state.copilotAuthError,
      mark: "Gh",
      name: providerCopy.copilotAuth?.name || "GitHub Copilot",
      status: authStatusLabel(providerCopy.copilotAuth, state.copilotAuth, state.copilotAuthLoading),
      description: copilotDescription(copy, state),
      loading: state.copilotAuthLoading,
      configured: state.copilotAuth?.configured,
      copy: providerCopy.copilotAuth || {},
      auth: state.copilotAuth || {},
      onRefresh: client.loadCopilotAuthStatus,
      onLogin: client.startCopilotAuthLogin,
      onLogout: client.logoutCopilotAuth,
    },
  ];

  return (
    <section className="settings-page">
      <SettingsStatus message={state.providersLoading ? providerCopy.loading || "Loading providers..." : ""} />
      <SettingsStatus message={state.providersNotice} />
      <SettingsStatus message={state.providersError} type="error" />

      {authSections.map(({ key, visible, ...section }) =>
        visible ? <ProviderAuthSection key={key} {...section} /> : null
      )}

      <ConnectedProvidersSection
        copy={copy}
        state={state}
        providers={providers.connected || []}
        providerCopy={providerCopy}
        onSetCredential={client.setProviderCredential}
        onDeleteCredential={client.deleteCredential}
        onDisconnect={client.disconnectProvider}
      />

      <AvailableProvidersSection
        providers={providers.available || []}
        providerCopy={providerCopy}
        providersLoading={state.providersLoading}
        onConnectOAuth={client.connectOAuthProvider}
        onBeginConnect={client.beginProviderConnect}
      />

      {selectedConnectProvider ? (
        <ProviderConnectDialog
          provider={selectedConnectProvider}
          state={state}
          providerCopy={providerCopy}
          onCancel={client.cancelProviderConnect}
          onSave={client.saveProviderConnection}
        />
      ) : null}
    </section>
  );
}
