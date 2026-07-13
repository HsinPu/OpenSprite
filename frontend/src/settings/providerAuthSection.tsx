import { AuthProviderCard } from "./authProviderCard";
import { SettingsSectionTitle, SettingsStatus } from "./settingsPrimitives";
import type { ProviderAuthSectionView } from "./providerAuthSections";

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
}: Omit<ProviderAuthSectionView, "key" | "visible">) {
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
