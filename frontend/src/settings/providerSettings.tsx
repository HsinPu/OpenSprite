import { selectedConnectProvider, type ProviderLike } from "./providerHelpers";
import { AvailableProvidersSection } from "./availableProvidersSection";
import { ConnectedProvidersSection } from "./connectedProvidersSection";
import type { ProviderAuthSlotState } from "./providerAuthHelpers";
import { providerAuthSections } from "./providerAuthSections";
import { ProviderAuthSection } from "./providerAuthSection";
import { ProviderConnectDialog } from "./providerConnectDialog";
import { SettingsStatus } from "./settingsPrimitives";
import type { ProviderConnectForm } from "../composables/providerConnectForm";
import type {
  ProviderCredentialsState,
  ProviderSettings as ProviderSettingsView,
} from "../composables/useSettingsState";
import { toPayloadSource } from "../composables/payloadBoundary";

type ValueRef<T> = { value: T };
type ProviderSettingsCopy = {
  settings?: unknown;
};
type ProviderSettingsContainerPayload = {
  providers?: unknown;
};
type ProviderSettingsCopyView = {
  builtInBadge?: unknown;
  connect?: unknown;
  connectOAuth?: unknown;
  connectedTitle?: unknown;
  connectedCount?: unknown;
  credentialLabel?: unknown;
  credentialSelect?: unknown;
  currentBadge?: unknown;
  deleteCredential?: unknown;
  disconnect?: unknown;
  loading?: unknown;
  missingCredential?: unknown;
  noAvailableDescription?: unknown;
  noAvailableTitle?: unknown;
  noConnectedDescription?: unknown;
  noConnectedTitle?: unknown;
  popularTitle?: unknown;
};
type ProviderSettingsStateView = ProviderAuthSlotState & {
  connectForm: ProviderConnectForm;
  credentials?: ProviderCredentialsState;
  providers: ProviderSettingsView;
  providersError: string;
  providersLoading: boolean;
  providersNotice: string;
};

type ProviderSettingsClient = {
  copy: ValueRef<ProviderSettingsCopy>;
  settingsState: ProviderSettingsStateView;
  loadProviderAuthStatusById: (providerId: string) => void;
  startProviderAuthLoginById: (providerId: string) => void;
  logoutProviderAuthById: (providerId: string) => void;
  setProviderCredential: (provider: ProviderLike, credentialId: string) => void;
  deleteCredential: (provider: ProviderLike, credentialId: string) => void;
  disconnectProvider: (provider: ProviderLike) => void;
  connectOAuthProvider: (provider: ProviderLike) => void;
  beginProviderConnect: (provider: ProviderLike) => void;
  cancelProviderConnect: () => void;
  saveProviderConnection: () => void;
};

function text(value: unknown, fallback = ""): string {
  return String(value || fallback);
}

function providerSettingsCopy(copy: ProviderSettingsCopy): ProviderSettingsCopyView {
  const settings = toPayloadSource<ProviderSettingsContainerPayload>(copy.settings);
  return toPayloadSource<ProviderSettingsCopyView>(settings?.providers) || {};
}

export function ProviderSettings({ client }: { client: ProviderSettingsClient }) {
  const copy = client.copy.value;
  const state = client.settingsState;
  const providers = state.providers;
  const providerCopy = providerSettingsCopy(copy);
  const connectProvider = selectedConnectProvider(providers, state.connectForm.providerId);
  const authSections = providerAuthSections(copy, state, client);

  return (
    <section className="settings-page">
      <SettingsStatus message={state.providersLoading ? text(providerCopy.loading, "Loading providers...") : ""} />
      <SettingsStatus message={state.providersNotice} />
      <SettingsStatus message={state.providersError} type="error" />

      {authSections.map(({ key, visible, ...section }) =>
        visible ? <ProviderAuthSection key={key} {...section} /> : null
      )}

      <ConnectedProvidersSection
        copy={copy}
        state={state}
        providers={providers.connected}
        providerCopy={providerCopy}
        onSetCredential={client.setProviderCredential}
        onDeleteCredential={client.deleteCredential}
        onDisconnect={client.disconnectProvider}
      />

      <AvailableProvidersSection
        providers={providers.available}
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
