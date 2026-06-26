import { List } from "antd";
import { AvailableProviderRow } from "./availableProviderRow";
import { SettingsCard, SettingsSectionTitle } from "./settingsPrimitives";

type AnyRecord = Record<string, any>;

export function AvailableProvidersSection({
  providers,
  providerCopy,
  providersLoading,
  onConnectOAuth,
  onBeginConnect,
}: {
  providers: AnyRecord[];
  providerCopy: AnyRecord;
  providersLoading: boolean;
  onConnectOAuth: (provider: AnyRecord) => void;
  onBeginConnect: (provider: AnyRecord) => void;
}) {
  return (
    <>
      <SettingsSectionTitle>{providerCopy.popularTitle || "Available providers"}</SettingsSectionTitle>
      <SettingsCard className="provider-card">
        <List
          className="provider-row-list"
          dataSource={providers}
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
          renderItem={(provider: AnyRecord) => (
            <AvailableProviderRow
              key={provider.id}
              provider={provider}
              providerCopy={providerCopy}
              providersLoading={providersLoading}
              onConnectOAuth={onConnectOAuth}
              onBeginConnect={onBeginConnect}
            />
          )}
        />
      </SettingsCard>
    </>
  );
}
