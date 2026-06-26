import { List } from "antd";
import { ConnectedProviderRow } from "./connectedProviderRow";
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
