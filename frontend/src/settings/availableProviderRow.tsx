import { Button, List, Tag } from "antd";
import { isOAuthProviderAuthType } from "./providerAuthHelpers";
import { type AnyRecord, providerMark } from "./providerHelpers";

export function AvailableProviderRow({
  provider,
  providerCopy,
  providersLoading,
  onConnectOAuth,
  onBeginConnect,
}: {
  provider: AnyRecord;
  providerCopy: AnyRecord;
  providersLoading: boolean;
  onConnectOAuth: (provider: AnyRecord) => void;
  onBeginConnect: (provider: AnyRecord) => void;
}) {
  const oauth = isOAuthProviderAuthType(provider.auth_type);

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
}
