import { Button, Form, List, Select, Tag } from "antd";
import {
  providerAuthCopyForProvider,
  providerAuthConfigured,
  providerAuthCopyKey,
  providerDescription,
  type ProviderAuthSlotState,
} from "./providerAuthHelpers";
import {
  credentialSourceLabel,
  providerCredentials,
  providerEffectiveCredentialId,
} from "./providerCredentialHelpers";
import {
  providerMark,
  type ProviderLike,
} from "./providerHelpers";
import type { ProviderCredentialView, ProviderCredentialsState } from "../composables/useSettingsState";

type ConnectedProviderView = ProviderLike & {
  credential_label?: unknown;
  credential_preview?: unknown;
  is_default?: unknown;
  preset_name?: unknown;
  requires_api_key?: unknown;
};
type ProviderCopyView = {
  credentialLabel?: unknown;
  credentialSelect?: unknown;
  currentBadge?: unknown;
  deleteCredential?: unknown;
  disconnect?: unknown;
  missingCredential?: unknown;
};
type ConnectedProviderStateView = ProviderAuthSlotState & {
  credentials?: ProviderCredentialsState;
  providersLoading?: unknown;
};

function text(value: unknown, fallback = ""): string {
  return String(value || fallback);
}

function credentialOption(credential: ProviderCredentialView): { value: string; label: string } {
  const value = text(credential.id);
  const label = text(credential.label || credential.name || credential.id);
  const secretPreview = text(credential.secret_preview);
  return {
    value,
    label: `${label}${secretPreview ? ` - ${secretPreview}` : ""}`,
  };
}

function credentialPreviewLabel(copy: unknown, providerCopy: ProviderCopyView, provider: ConnectedProviderView): string {
  const preview = text(provider.credential_preview);
  if (!preview) return "";
  if (typeof providerCopy.credentialLabel === "function") {
    return String(providerCopy.credentialLabel(text(provider.credential_label || provider.name), preview, credentialSourceLabel(copy, provider)));
  }
  return preview;
}

export function ConnectedProviderRow({
  copy,
  state,
  provider,
  providerCopy,
  onSetCredential,
  onDeleteCredential,
  onDisconnect,
}: {
  copy: unknown;
  state: ConnectedProviderStateView;
  provider: ConnectedProviderView;
  providerCopy: ProviderCopyView;
  onSetCredential: (provider: ConnectedProviderView, credentialId: string) => void;
  onDeleteCredential: (provider: ConnectedProviderView, credentialId: string) => void;
  onDisconnect: (provider: ConnectedProviderView) => void;
}) {
  const credentials = providerCredentials(state, provider);
  const effectiveCredentialId = providerEffectiveCredentialId(provider);
  const authCopyKey = providerAuthCopyKey(provider);
  const authCopy = providerAuthCopyForProvider(copy, provider);
  const providerId = text(provider.id);
  const providerName = text(provider.name || provider.id);
  const presetName = text(provider.preset_name);
  const credentialPreview = credentialPreviewLabel(copy, providerCopy, provider);
  const providersLoading = Boolean(state.providersLoading);

  return (
    <List.Item key={providerId} className="provider-row">
      <div className="provider-row__main">
        <span className="provider-row__mark" aria-hidden="true">{providerMark(provider)}</span>
        <div>
          <div className="provider-row__title">
            <strong>{providerName}</strong>
            {provider.is_default ? <Tag className="provider-row__badge">{text(providerCopy.currentBadge, "Current")}</Tag> : null}
            {presetName && presetName !== providerName ? <Tag className="provider-row__badge">{presetName}</Tag> : null}
            {authCopyKey && !providerAuthConfigured(state, provider) ? <Tag className="provider-row__badge">{text(authCopy.notConfigured, "Not configured")}</Tag> : null}
          </div>
          <span>{providerDescription(copy, state, provider)}</span>
          {credentialPreview ? (
            <span className="provider-row__credential">
              {credentialPreview}
            </span>
          ) : provider.requires_api_key ? (
            <span className="provider-row__credential provider-row__credential--missing">{text(providerCopy.missingCredential, "Missing credential")}</span>
          ) : null}
          {credentials.length > 1 ? (
            <Form.Item className="provider-row__select" label={text(providerCopy.credentialSelect, "Credential")}>
              <Select
                value={effectiveCredentialId}
                disabled={providersLoading}
                options={credentials.map(credentialOption)}
                onChange={(value) => onSetCredential(provider, String(value || ""))}
              />
            </Form.Item>
          ) : null}
        </div>
      </div>
      <div className="provider-row__actions provider-row__actions--connected">
        {effectiveCredentialId ? (
          <Button size="small" danger disabled={providersLoading} onClick={() => onDeleteCredential(provider, effectiveCredentialId)}>
            {text(providerCopy.deleteCredential, "Delete credential")}
          </Button>
        ) : null}
        <Button size="small" disabled={providersLoading} onClick={() => onDisconnect(provider)}>
          {text(providerCopy.disconnect, "Disconnect")}
        </Button>
      </div>
    </List.Item>
  );
}
