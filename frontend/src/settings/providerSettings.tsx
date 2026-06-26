import { type AnyRecord, selectedConnectProvider } from "./providerHelpers";
import { AvailableProvidersSection } from "./availableProvidersSection";
import { ConnectedProvidersSection } from "./connectedProvidersSection";
import { providerAuthSections } from "./providerAuthSections";
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
  const connectProvider = selectedConnectProvider(providers, state.connectForm.providerId);
  const authSections = providerAuthSections(copy, state, client);

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

      {connectProvider ? (
        <ProviderConnectDialog
          provider={connectProvider}
          state={state}
          providerCopy={providerCopy}
          onCancel={client.cancelProviderConnect}
          onSave={client.saveProviderConnection}
        />
      ) : null}
    </section>
  );
}
