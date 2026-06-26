import { Button, Form, List, Select, Tag } from "antd";
import {
  credentialSourceLabel,
  providerCredentials,
  providerDescription,
  providerEffectiveCredentialId,
  providerMark,
} from "./providerHelpers";
import { SettingsCard, SettingsSectionTitle } from "./settingsPrimitives";

type AnyRecord = Record<string, any>;

export function ConnectedProvidersSection({
  copy,
  state,
  providers,
  providerCopy,
  onSetCredential,
  onDeleteCredential,
  onDisconnect,
}: {
  copy: AnyRecord;
  state: AnyRecord;
  providers: AnyRecord[];
  providerCopy: AnyRecord;
  onSetCredential: (provider: AnyRecord, credentialId: string) => void;
  onDeleteCredential: (provider: AnyRecord, credentialId: string) => void;
  onDisconnect: (provider: AnyRecord) => void;
}) {
  return (
    <>
      <SettingsSectionTitle>{providerCopy.connectedTitle || "Connected providers"}</SettingsSectionTitle>
      <SettingsCard className="provider-card">
        <List
          className="provider-row-list"
          dataSource={providers}
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
                          onChange={(value) => onSetCredential(provider, value)}
                        />
                      </Form.Item>
                    ) : null}
                  </div>
                </div>
                <div className="provider-row__actions provider-row__actions--connected">
                  {effectiveCredentialId ? (
                    <Button size="small" danger disabled={state.providersLoading} onClick={() => onDeleteCredential(provider, effectiveCredentialId)}>
                      {providerCopy.deleteCredential || "Delete credential"}
                    </Button>
                  ) : null}
                  <Button size="small" disabled={state.providersLoading} onClick={() => onDisconnect(provider)}>
                    {providerCopy.disconnect || "Disconnect"}
                  </Button>
                </div>
              </List.Item>
            );
          }}
        />
      </SettingsCard>
    </>
  );
}
