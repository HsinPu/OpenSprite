import { ArrowLeftOutlined, CloseOutlined } from "@ant-design/icons";
import { Button, Form, Input, List, Select, Tag } from "antd";
import {
  authStatusLabel,
  codexDescription,
  copilotDescription,
  credentialSourceLabel,
  hasConnectedProvider,
  providerCredentials,
  providerDescription,
  providerEffectiveCredentialId,
  providerMark,
} from "./providerHelpers";
import { AuthProviderCard } from "./authProviderCard";
import { SettingsCard, SettingsSectionTitle, SettingsStatus } from "./settingsPrimitives";

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

      <SettingsSectionTitle>{providerCopy.connectedTitle || "Connected providers"}</SettingsSectionTitle>
      <SettingsCard className="provider-card">
        <List
          className="provider-row-list"
          dataSource={providers.connected || []}
          locale={{
            emptyText: (
              <div className="provider-row provider-row--empty">
                <div>
                  <strong>{providerCopy.noConnectedTitle || "No connected providers"}</strong>
                  <span>{providerCopy.noConnectedDescription || ""}</span>
                </div>
              </div>
            ),
          }}
          renderItem={(provider: AnyRecord) => {
            const credentials = providerCredentials(state, provider);
            const effectiveCredentialId = providerEffectiveCredentialId(provider);
            return (
              <List.Item key={provider.id} className="provider-row">
                <div className="provider-row__main">
                  <span className="provider-row__mark" aria-hidden="true">{providerMark(provider)}</span>
                  <div>
                    <div className="provider-row__title">
                      <strong>{provider.name || provider.id}</strong>
                      {provider.is_default ? <Tag className="provider-row__badge">{providerCopy.currentBadge || "Current"}</Tag> : null}
                      {provider.preset_name && provider.preset_name !== provider.name ? <Tag className="provider-row__badge">{provider.preset_name}</Tag> : null}
                      {provider.provider === "openai-codex" && !state.codexAuth?.configured ? <Tag className="provider-row__badge">{providerCopy.codexAuth?.notConfigured || "Not configured"}</Tag> : null}
                      {provider.provider === "copilot" && !state.copilotAuth?.configured ? <Tag className="provider-row__badge">{providerCopy.copilotAuth?.notConfigured || "Not configured"}</Tag> : null}
                    </div>
                    <span>{providerDescription(copy, state, provider)}</span>
                    {provider.credential_preview ? (
                      <span className="provider-row__credential">
                        {typeof providerCopy.credentialLabel === "function"
                          ? providerCopy.credentialLabel(provider.credential_label || provider.name, provider.credential_preview, credentialSourceLabel(copy, provider))
                          : provider.credential_preview}
                      </span>
                    ) : provider.requires_api_key ? (
                      <span className="provider-row__credential provider-row__credential--missing">{providerCopy.missingCredential || "Missing credential"}</span>
                    ) : null}
                    {credentials.length > 1 ? (
                      <Form.Item className="provider-row__select" label={providerCopy.credentialSelect || "Credential"}>
                        <Select
                          value={effectiveCredentialId}
                          disabled={state.providersLoading}
                          options={credentials.map((credential: AnyRecord) => ({
                            value: credential.id,
                            label: `${credential.label || credential.name || credential.id}${credential.secret_preview ? ` - ${credential.secret_preview}` : ""}`,
                          }))}
                          onChange={(value) => client.setProviderCredential(provider, value)}
                        />
                      </Form.Item>
                    ) : null}
                  </div>
                </div>
                <div className="provider-row__actions provider-row__actions--connected">
                  {effectiveCredentialId ? (
                    <Button size="small" danger disabled={state.providersLoading} onClick={() => client.deleteCredential(provider, effectiveCredentialId)}>
                      {providerCopy.deleteCredential || "Delete credential"}
                    </Button>
                  ) : null}
                  <Button size="small" disabled={state.providersLoading} onClick={() => client.disconnectProvider(provider)}>
                    {providerCopy.disconnect || "Disconnect"}
                  </Button>
                </div>
              </List.Item>
            );
          }}
        />
      </SettingsCard>

      <SettingsSectionTitle>{providerCopy.popularTitle || "Available providers"}</SettingsSectionTitle>
      <SettingsCard className="provider-card">
        <List
          className="provider-row-list"
          dataSource={providers.available || []}
          locale={{
            emptyText: (
              <div className="provider-row provider-row--empty">
                <div>
                  <strong>{providerCopy.noAvailableTitle || "No available providers"}</strong>
                  <span>{providerCopy.noAvailableDescription || ""}</span>
                </div>
              </div>
            ),
          }}
          renderItem={(provider: AnyRecord) => {
            const oauth = provider.auth_type === "openai_codex_oauth" || provider.auth_type === "github_copilot_oauth";
            return (
              <List.Item key={provider.id} className="provider-row provider-row--stacked">
                <div className="provider-row__content">
                  <div className="provider-row__main">
                    <span className="provider-row__mark" aria-hidden="true">{providerMark(provider)}</span>
                    <div>
                      <div className="provider-row__title">
                        <strong>{provider.name || provider.id}</strong>
                        <Tag className="provider-row__badge">{providerCopy.builtInBadge || "Built-in"}</Tag>
                        {provider.connected_count ? <Tag className="provider-row__badge">{typeof providerCopy.connectedCount === "function" ? providerCopy.connectedCount(provider.connected_count) : provider.connected_count}</Tag> : null}
                      </div>
                      <span>{provider.default_base_url || provider.description || provider.id}</span>
                    </div>
                  </div>
                  <Button type="primary" disabled={state.providersLoading} onClick={() => (oauth ? client.connectOAuthProvider(provider) : client.beginProviderConnect(provider))}>
                    {oauth ? providerCopy.connectOAuth || "Connect OAuth" : providerCopy.connect || "Connect"}
                  </Button>
                </div>
              </List.Item>
            );
          }}
        />
      </SettingsCard>

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
