import { List } from "antd";
import { AvailableProviderRow } from "./availableProviderRow";
import { ProviderEmptyState } from "./providerEmptyState";
import type { ProviderLike } from "./providerHelpers";
import { SettingsCard, SettingsSectionTitle } from "./settingsPrimitives";

type AvailableProviderCopyView = {
  builtInBadge?: unknown;
  connect?: unknown;
  connectOAuth?: unknown;
  connectedCount?: unknown;
  noAvailableDescription?: unknown;
  noAvailableTitle?: unknown;
  popularTitle?: unknown;
};

function text(value: unknown, fallback = ""): string {
  return String(value || fallback);
}

export function AvailableProvidersSection({
  providers,
  providerCopy,
  providersLoading,
  onConnectOAuth,
  onBeginConnect,
}: {
  providers: ProviderLike[];
  providerCopy: AvailableProviderCopyView;
  providersLoading: boolean;
  onConnectOAuth: (provider: ProviderLike) => void;
  onBeginConnect: (provider: ProviderLike) => void;
}) {
  return (
    <>
      <SettingsSectionTitle>{text(providerCopy.popularTitle, "Available providers")}</SettingsSectionTitle>
      <SettingsCard className="provider-card">
        <List
          className="provider-row-list"
          dataSource={providers}
          locale={{
            emptyText: (
              <ProviderEmptyState
                title={text(providerCopy.noAvailableTitle, "No available providers")}
                description={text(providerCopy.noAvailableDescription)}
              />
            ),
          }}
          renderItem={(provider: ProviderLike) => (
            <AvailableProviderRow
              key={String(provider.id || "")}
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
