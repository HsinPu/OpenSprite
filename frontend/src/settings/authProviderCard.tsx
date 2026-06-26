import { ReloadOutlined } from "@ant-design/icons";
import { Button, Space, Tag } from "antd";
import type { AnyRecord } from "./providerHelpers";
import { SettingsCard } from "./settingsPrimitives";

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
}: AnyRecord) {
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
            <Button icon={<ReloadOutlined />} loading={loading} disabled={loading} onClick={onRefresh}>{copy.refresh || "Refresh"}</Button>
            <Button type="primary" loading={loading} disabled={loading} onClick={onLogin}>{copy.login || "Login"}</Button>
            <Button disabled={loading || !configured} onClick={onLogout}>{copy.logout || "Logout"}</Button>
          </Space>
        </div>
        {auth.userCode ? (
          <div className="codex-auth-command">
            <span>{copy.userCodeLabel || "User code"}</span>
            <code>{auth.userCode}</code>
            {auth.verificationUri ? <a href={auth.verificationUri} target="_blank" rel="noreferrer">{copy.openVerification || "Open verification"}</a> : null}
          </div>
        ) : null}
      </div>
    </SettingsCard>
  );
}
