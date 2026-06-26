import { Button, List, Tag } from "antd";
import { providerMark } from "./providerHelpers";
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
                  <Button type="primary" disabled={providersLoading} onClick={() => (oauth ? onConnectOAuth(provider) : onBeginConnect(provider))}>
                    {oauth ? providerCopy.connectOAuth || "Connect OAuth" : providerCopy.connect || "Connect"}
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
