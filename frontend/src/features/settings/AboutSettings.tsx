import { useI18n } from "../../i18n/I18nProvider";
import { useAppInfo } from "../app-info/useAppInfo";
import { formatTime } from "../general-settings/dateTime";
import { SettingsCard } from "./SettingsPrimitives";

export function AboutSettings() {
  const { locale, t } = useI18n();
  const { info, loading, error, reload } = useAppInfo();
  return <div className="settings-form-stack"><SettingsCard icon="info" title="OpenSprite">
    {loading ? <p className="settings-card-description" role="status">{t("about.loading")}</p> : null}
    {error ? <div className="settings-model-load-error" role="alert"><p>{t("about.error")}</p><button type="button" className="settings-secondary-button settings-model-retry" onClick={() => void reload()}>{t("common.retry")}</button></div> : null}
    {info ? <dl className="settings-about-details">
      <div><dt>{t("about.version")}</dt><dd>{info.version}</dd></div>
      <div><dt>{t("about.revision")}</dt><dd>{info.revision}{info.dirty ? ` · ${t("about.dirty")}` : ""}</dd></div>
      <div><dt>{t("about.buildType")}</dt><dd>{t(info.buildType === "installed" ? "about.installed" : "about.development")}</dd></div>
      <div><dt>{t("about.installedAt")}</dt><dd>{info.installedAt ? formatTime(info.installedAt, locale, "system") : "—"}</dd></div>
    </dl> : null}
  </SettingsCard></div>;
}
