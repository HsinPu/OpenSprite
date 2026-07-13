import { ReloadOutlined } from "@ant-design/icons";
import { Button, Space, Tag } from "antd";
import { SettingsCard } from "./settingsPrimitives";

type AuthProviderCardCopy = {
  login?: unknown;
  logout?: unknown;
  openVerification?: unknown;
  refresh?: unknown;
  userCodeLabel?: unknown;
};
type AuthProviderCardState = {
  userCode?: unknown;
  verificationUri?: unknown;
};
type AuthProviderCardProps = {
  mark: string;
  name: string;
  status: string;
  description: string;
  loading?: boolean;
  configured?: boolean;
  copy: AuthProviderCardCopy;
  auth: AuthProviderCardState;
  onRefresh: () => void;
  onLogin: () => void;
  onLogout: () => void;
};

function text(value: unknown, fallback = ""): string {
  return String(value || fallback);
}

export function AuthProviderCard({
  mark,
  name,
  status,
  description,
  loading,
  configured,
  copy,
  auth,
  onRefresh,
  onLogin,
  onLogout,
}: AuthProviderCardProps) {
  const userCode = text(auth.userCode);
  const verificationUri = text(auth.verificationUri);

  return (
    <SettingsCard className="provider-card">
      <div className="provider-row provider-row--stacked codex-auth-row">
        <div className="provider-row__content">
          <div className="provider-row__main">
            <span className="provider-row__mark" aria-hidden="true">{mark}</span>
            <div>
              <div className="provider-row__title">
                <strong>{name}</strong>
                <Tag className="provider-row__badge">{status}</Tag>
              </div>
              <span>{description}</span>
            </div>
          </div>
          <Space className="provider-row__actions" wrap>
            <Button icon={<ReloadOutlined />} loading={loading} disabled={loading} onClick={onRefresh}>{text(copy.refresh, "Refresh")}</Button>
            <Button type="primary" loading={loading} disabled={loading} onClick={onLogin}>{text(copy.login, "Login")}</Button>
            <Button disabled={loading || !configured} onClick={onLogout}>{text(copy.logout, "Logout")}</Button>
          </Space>
        </div>
        {userCode ? (
          <div className="codex-auth-command">
            <span>{text(copy.userCodeLabel, "User code")}</span>
            <code>{userCode}</code>
            {verificationUri ? <a href={verificationUri} target="_blank" rel="noreferrer">{text(copy.openVerification, "Open verification")}</a> : null}
          </div>
        ) : null}
      </div>
    </SettingsCard>
  );
}
