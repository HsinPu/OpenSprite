import { Button, Form, List, Select, Tag } from "antd";
import {
  type AnyRecord,
  credentialSourceLabel,
  providerAuthConfigured,
  providerAuthKey,
  providerCredentials,
  providerDescription,
  providerEffectiveCredentialId,
  providerMark,
} from "./providerHelpers";

export function ConnectedProviderRow({
  copy,
  state,
  provider,
  providerCopy,
  onSetCredential,
  onDeleteCredential,
  onDisconnect,
}: {
  copy: AnyRecord;
  state: AnyRecord;
  provider: AnyRecord;
  providerCopy: AnyRecord;
  onSetCredential: (provider: AnyRecord, credentialId: string) => void;
  onDeleteCredential: (provider: AnyRecord, credentialId: string) => void;
  onDisconnect: (provider: AnyRecord) => void;
}) {
  const credentials = providerCredentials(state, provider);
  const effectiveCredentialId = providerEffectiveCredentialId(provider);
  const authKey = providerAuthKey(provider);

  return (
    <List.Item key={provider.id} className="provider-row">
      <div className="provider-row__main">
        <span className="provider-row__mark" aria-hidden="true">{providerMark(provider)}</span>
        <div>
          <div className="provider-row__title">
            <strong>{provider.name || provider.id}</strong>
            {provider.is_default ? <Tag className="provider-row__badge">{providerCopy.currentBadge || "Current"}</Tag> : null}
            {provider.preset_name && provider.preset_name !== provider.name ? <Tag className="provider-row__badge">{provider.preset_name}</Tag> : null}
            {authKey && !providerAuthConfigured(state, provider) ? <Tag className="provider-row__badge">{providerCopy[authKey]?.notConfigured || "Not configured"}</Tag> : null}
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
}
