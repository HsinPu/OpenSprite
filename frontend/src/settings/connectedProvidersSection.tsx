import { List } from "antd";
import { ConnectedProviderRow } from "./connectedProviderRow";
import { ProviderEmptyState } from "./providerEmptyState";
import type { ProviderAuthSlotState } from "./providerAuthHelpers";
import type { ProviderLike } from "./providerHelpers";
import { SettingsCard, SettingsSectionTitle } from "./settingsPrimitives";
import type { ProviderCredentialsState } from "../composables/useSettingsState";

type ConnectedProviderCopyView = {
  connectedTitle?: unknown;
  credentialLabel?: unknown;
  credentialSelect?: unknown;
  currentBadge?: unknown;
  deleteCredential?: unknown;
  disconnect?: unknown;
  missingCredential?: unknown;
  noConnectedDescription?: unknown;
  noConnectedTitle?: unknown;
};
type ConnectedProvidersStateView = ProviderAuthSlotState & {
  credentials?: ProviderCredentialsState;
  providersLoading?: unknown;
};

function text(value: unknown, fallback = ""): string {
  return String(value || fallback);
}

export function ConnectedProvidersSection({
  copy,
  state,
  providers,
  providerCopy,
  onSetCredential,
  onDeleteCredential,
  onDisconnect,
}: {
  copy: unknown;
  state: ConnectedProvidersStateView;
  providers: ProviderLike[];
  providerCopy: ConnectedProviderCopyView;
  onSetCredential: (provider: ProviderLike, credentialId: string) => void;
  onDeleteCredential: (provider: ProviderLike, credentialId: string) => void;
  onDisconnect: (provider: ProviderLike) => void;
}) {
  return (
    <>
      <SettingsSectionTitle>{text(providerCopy.connectedTitle, "Connected providers")}</SettingsSectionTitle>
      <SettingsCard className="provider-card">
        <List
          className="provider-row-list"
          dataSource={providers}
          locale={{
            emptyText: (
              <ProviderEmptyState
                title={text(providerCopy.noConnectedTitle, "No connected providers")}
                description={text(providerCopy.noConnectedDescription)}
              />
            ),
          }}
          renderItem={(provider: ProviderLike) => (
            <ConnectedProviderRow
              key={String(provider.id || "")}
              copy={copy}
              state={state}
              provider={provider}
              providerCopy={providerCopy}
              onSetCredential={onSetCredential}
              onDeleteCredential={onDeleteCredential}
              onDisconnect={onDisconnect}
            />
          )}
        />
      </SettingsCard>
    </>
  );
}
