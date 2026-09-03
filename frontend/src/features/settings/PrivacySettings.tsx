import { Button, Input } from "antd";
import { useState, type FormEvent } from "react";

import { AuthenticationApiError, changePassword, logoutAll } from "../../api/authentication";
import { useAuthentication } from "../auth/AuthGate";
import { useI18n } from "../../i18n/I18nProvider";
import { SettingsCard } from "./SettingsPrimitives";

export function PrivacySettings() {
  const { t } = useI18n();
  const { mode, requireLogin } = useAuthentication();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<{ error?: string; success?: string }>({});

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const length = Array.from(newPassword.normalize("NFC")).length;
    if (length < 15 || length > 128) { setFeedback({ error: t("auth.error.invalidPassword") }); return; }
    if (newPassword !== confirmation) { setFeedback({ error: t("auth.error.passwordMismatch") }); return; }
    setBusy(true); setFeedback({});
    try {
      await changePassword(currentPassword, newPassword);
      setCurrentPassword(""); setNewPassword(""); setConfirmation("");
      setFeedback({ success: t("auth.passwordChanged") });
    } catch (error) {
      setCurrentPassword(""); setNewPassword(""); setConfirmation("");
      setFeedback({ error: error instanceof AuthenticationApiError && error.code === "invalid_credentials" ? t("auth.error.invalidCredentials") : t("auth.error.unavailable") });
    } finally { setBusy(false); }
  };

  const revokeAll = async () => {
    setBusy(true); setFeedback({});
    try { await logoutAll(); } finally { requireLogin(); }
  };

  if (mode === "trusted_local") return <div className="settings-form-stack">
    <SettingsCard icon="privacy" title={t("auth.trustedLocalTitle")}>
      <p className="settings-card-description">{t("auth.trustedLocalDescription")}</p>
      <p className="settings-trust-warning" role="note">{t("auth.trustedLocalWarning")}</p>
      <p className="settings-card-description">{t("auth.trustedLocalChange")}</p>
    </SettingsCard>
  </div>;

  return <div className="settings-form-stack">
    <SettingsCard icon="privacy" title={t("auth.changeTitle")}>
      <p className="settings-card-description">{t("auth.changeDescription")}</p>
      <form className="settings-password-form" onSubmit={submit}>
        <label htmlFor="current-local-password">{t("auth.currentPassword")}</label>
        <Input.Password id="current-local-password" autoComplete="current-password" value={currentPassword} disabled={busy} onChange={(event) => setCurrentPassword(event.target.value)} />
        <label htmlFor="new-local-password">{t("auth.newPassword")}</label>
        <Input.Password id="new-local-password" autoComplete="new-password" value={newPassword} disabled={busy} onChange={(event) => setNewPassword(event.target.value)} />
        <label htmlFor="confirm-local-password">{t("auth.confirmPassword")}</label>
        <Input.Password id="confirm-local-password" autoComplete="new-password" value={confirmation} disabled={busy} onChange={(event) => setConfirmation(event.target.value)} />
        {feedback.error ? <p className="settings-action-error" role="alert">{feedback.error}</p> : null}
        {feedback.success ? <p className="settings-action-status" role="status">{feedback.success}</p> : null}
        <Button htmlType="submit" type="primary" loading={busy}>{t("auth.changeAction")}</Button>
      </form>
    </SettingsCard>
    <SettingsCard icon="privacy" title={t("auth.logoutAll")}>
      <p className="settings-card-description">{t("auth.logoutAllDescription")}</p>
      <Button danger disabled={busy} onClick={() => void revokeAll()}>{t("auth.logoutAll")}</Button>
    </SettingsCard>
  </div>;
}
