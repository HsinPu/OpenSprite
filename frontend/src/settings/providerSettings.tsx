import {
  authStatusLabel,
  codexDescription,
  copilotDescription,
  hasConnectedProvider,
} from "./providerHelpers";
import { AuthProviderCard } from "./authProviderCard";
import { AvailableProvidersSection } from "./availableProvidersSection";
import { ConnectedProvidersSection } from "./connectedProvidersSection";
import { ProviderConnectDialog } from "./providerConnectDialog";
import { SettingsSectionTitle, SettingsStatus } from "./settingsPrimitives";

type AnyRecord = Record<string, any>;
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
  const codexAuthStatusLabel = authStatusLabel(providerCopy.codexAuth, state.codexAuth, state.codexAuthLoading);
  const copilotAuthStatusLabel = authStatusLabel(providerCopy.copilotAuth, state.copilotAuth, state.copilotAuthLoading);
  const codexAuthDescription = codexDescription(copy, state);
  const copilotAuthDescription = copilotDescription(copy, state);

  return (
    <section className="settings-page">
      <SettingsStatus message={state.providersLoading ? providerCopy.loading || "Loading providers..." : ""} />
      <SettingsStatus message={state.providersNotice} />
      <SettingsStatus message={state.providersError} type="error" />

      {showCodexAuthCard ? (
        <>
          <SettingsSectionTitle>{providerCopy.codexAuth?.title || "OpenAI Codex auth"}</SettingsSectionTitle>
          <SettingsStatus message={state.codexAuthNotice} />
          <SettingsStatus message={state.codexAuthError} type="error" />
          <AuthProviderCard
            mark="Cx"
            name={providerCopy.codexAuth?.name || "OpenAI Codex"}
            status={codexAuthStatusLabel}
            description={codexAuthDescription}
            loading={state.codexAuthLoading}
            configured={state.codexAuth?.configured}
            copy={providerCopy.codexAuth || {}}
            auth={state.codexAuth || {}}
            onRefresh={client.loadCodexAuthStatus}
            onLogin={client.startCodexAuthLogin}
            onLogout={client.logoutCodexAuth}
          />
        </>
      ) : null}

      {showCopilotAuthCard ? (
        <>
          <SettingsSectionTitle>{providerCopy.copilotAuth?.title || "GitHub Copilot auth"}</SettingsSectionTitle>
          <SettingsStatus message={state.copilotAuthNotice} />
          <SettingsStatus message={state.copilotAuthError} type="error" />
          <AuthProviderCard
            mark="Gh"
            name={providerCopy.copilotAuth?.name || "GitHub Copilot"}
            status={copilotAuthStatusLabel}
            description={copilotAuthDescription}
            loading={state.copilotAuthLoading}
            configured={state.copilotAuth?.configured}
            copy={providerCopy.copilotAuth || {}}
            auth={state.copilotAuth || {}}
            onRefresh={client.loadCopilotAuthStatus}
            onLogin={client.startCopilotAuthLogin}
            onLogout={client.logoutCopilotAuth}
          />
        </>
      ) : null}

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
