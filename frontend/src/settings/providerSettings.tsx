import { ArrowLeftOutlined, CloseOutlined } from "@ant-design/icons";
import { Button, Form, Input } from "antd";
import {
  authStatusLabel,
  codexDescription,
  copilotDescription,
  hasConnectedProvider,
  providerMark,
} from "./providerHelpers";
import { AuthProviderCard } from "./authProviderCard";
import { AvailableProvidersSection } from "./availableProvidersSection";
import { ConnectedProvidersSection } from "./connectedProvidersSection";
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
  const selectedConnectProviderRequiresApiKey = selectedConnectProvider?.requires_api_key !== false || selectedConnectProvider?.api_key_optional === true;

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
        <div className="provider-connect-dialog" role="dialog" aria-modal="true">
          <header className="provider-connect-dialog__top">
            <Button type="text" aria-label={providerCopy.backAria || "Back"} icon={<ArrowLeftOutlined />} onClick={client.cancelProviderConnect} />
            <Button type="text" aria-label={providerCopy.closeAria || "Close"} icon={<CloseOutlined />} onClick={client.cancelProviderConnect} />
          </header>
          <Form className="provider-connect-dialog__body" layout="vertical" onFinish={() => client.saveProviderConnection()}>
            <div className="provider-connect-dialog__title">
              <span className="provider-row__mark" aria-hidden="true">{providerMark(selectedConnectProvider)}</span>
              <h3>{typeof providerCopy.dialogTitle === "function" ? providerCopy.dialogTitle(selectedConnectProvider.name) : `Connect ${selectedConnectProvider.name}`}</h3>
            </div>
            <p>{typeof providerCopy.dialogDescription === "function" ? providerCopy.dialogDescription(selectedConnectProvider.name) : ""}</p>
            <Form.Item className="provider-connect-field" label={providerCopy.nameLabel || "Name"}>
              <Input value={state.connectForm.name} placeholder={selectedConnectProvider.name} autoComplete="off" onChange={(event) => (state.connectForm.name = event.target.value)} />
            </Form.Item>
            {selectedConnectProviderRequiresApiKey ? (
              <Form.Item className="provider-connect-field" label={typeof providerCopy.apiKeyLabel === "function" ? providerCopy.apiKeyLabel(selectedConnectProvider.name) : "API key"}>
                <Input.Password value={state.connectForm.apiKey} placeholder="API key" autoComplete="off" onChange={(event) => (state.connectForm.apiKey = event.target.value)} />
              </Form.Item>
            ) : null}
            <Button type="link" className="provider-connect-dialog__advanced" onClick={() => (state.connectForm.showAdvanced = !state.connectForm.showAdvanced)}>
              {state.connectForm.showAdvanced ? providerCopy.advancedHide || "Hide advanced" : providerCopy.advancedShow || "Advanced"}
            </Button>
            {state.connectForm.showAdvanced ? (
              <Form.Item className="provider-connect-field" label="Base URL">
                <Input value={state.connectForm.baseUrl} spellCheck={false} onChange={(event) => (state.connectForm.baseUrl = event.target.value)} />
              </Form.Item>
            ) : null}
            <Button className="provider-connect-dialog__submit" type="primary" htmlType="submit" loading={state.providersLoading} disabled={state.providersLoading}>
              {providerCopy.submit || "Save"}
            </Button>
          </Form>
        </div>
      ) : null}
    </section>
  );
}
