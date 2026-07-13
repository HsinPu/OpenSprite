import { Button, List, Tag } from "antd";
import { isOAuthProviderAuthType } from "./providerAuthHelpers";
import { providerMark, type ProviderLike } from "./providerHelpers";

type AvailableProviderView = ProviderLike & {
  auth_type?: unknown;
  connected_count?: unknown;
  default_base_url?: unknown;
};
type AvailableProviderCopyView = {
  builtInBadge?: unknown;
  connect?: unknown;
  connectOAuth?: unknown;
  connectedCount?: unknown;
};

function text(value: unknown, fallback = ""): string {
  return String(value || fallback);
}

function connectedCountLabel(copy: AvailableProviderCopyView, count: unknown): string {
  if (typeof copy.connectedCount === "function") {
    return String(copy.connectedCount(count));
  }
  return String(count || "");
}

export function AvailableProviderRow({
  provider,
  providerCopy,
  providersLoading,
  onConnectOAuth,
  onBeginConnect,
}: {
  provider: AvailableProviderView;
  providerCopy: AvailableProviderCopyView;
  providersLoading: boolean;
  onConnectOAuth: (provider: AvailableProviderView) => void;
  onBeginConnect: (provider: AvailableProviderView) => void;
}) {
  const oauth = isOAuthProviderAuthType(text(provider.auth_type));
  const providerId = text(provider.id);
  const providerName = text(provider.name, providerId);
  const connectedCount = Number(provider.connected_count || 0);

  return (
    <List.Item key={providerId} className="provider-row provider-row--stacked">
      <div className="provider-row__content">
        <div className="provider-row__main">
          <span className="provider-row__mark" aria-hidden="true">{providerMark(provider)}</span>
          <div>
            <div className="provider-row__title">
              <strong>{providerName}</strong>
              <Tag className="provider-row__badge">{text(providerCopy.builtInBadge, "Built-in")}</Tag>
              {connectedCount ? <Tag className="provider-row__badge">{connectedCountLabel(providerCopy, connectedCount)}</Tag> : null}
            </div>
            <span>{text(provider.default_base_url || provider.description, providerId)}</span>
          </div>
        </div>
        <Button type="primary" disabled={providersLoading} onClick={() => (oauth ? onConnectOAuth(provider) : onBeginConnect(provider))}>
          {oauth ? text(providerCopy.connectOAuth, "Connect OAuth") : text(providerCopy.connect, "Connect")}
        </Button>
      </div>
    </List.Item>
  );
}
