import { List } from "antd";
import { AvailableProviderRow } from "./availableProviderRow";
import { ProviderEmptyState } from "./providerEmptyState";
import type { AnyRecord } from "./providerHelpers";
import { SettingsCard, SettingsSectionTitle } from "./settingsPrimitives";

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
              <ProviderEmptyState
                title={providerCopy.noAvailableTitle || "No available providers"}
                description={providerCopy.noAvailableDescription || ""}
              />
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
