import { AuthProviderCard } from "./authProviderCard";
import type { AnyRecord } from "./providerHelpers";
import { SettingsSectionTitle, SettingsStatus } from "./settingsPrimitives";

export function ProviderAuthSection({
  title,
  notice,
  error,
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
}: {
  title: string;
  notice?: string;
  error?: string;
  mark: string;
  name: string;
  status: string;
  description: string;
  loading?: boolean;
  configured?: boolean;
  copy: AnyRecord;
  auth: AnyRecord;
  onRefresh: () => void;
  onLogin: () => void;
  onLogout: () => void;
}) {
  return (
    <>
      <SettingsSectionTitle>{title}</SettingsSectionTitle>
      <SettingsStatus message={notice} />
      <SettingsStatus message={error} type="error" />
      <AuthProviderCard
        mark={mark}
        name={name}
        status={status}
        description={description}
        loading={loading}
        configured={configured}
        copy={copy}
        auth={auth}
        onRefresh={onRefresh}
        onLogin={onLogin}
        onLogout={onLogout}
      />
    </>
  );
}
