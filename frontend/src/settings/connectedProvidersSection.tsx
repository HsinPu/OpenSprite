import { List } from "antd";
import { ConnectedProviderRow } from "./connectedProviderRow";
import { ProviderEmptyState } from "./providerEmptyState";
import type { AnyRecord } from "./providerHelpers";
import { SettingsCard, SettingsSectionTitle } from "./settingsPrimitives";

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
              <ProviderEmptyState
                title={providerCopy.noConnectedTitle || "No connected providers"}
                description={providerCopy.noConnectedDescription || ""}
              />
            ),
          }}
          renderItem={(provider: AnyRecord) => (
            <ConnectedProviderRow
              key={provider.id}
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
