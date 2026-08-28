import { FutureSettingRow, SettingsCard } from "./SettingsPrimitives";
import { isLocale, localeLabels, supportedLocales } from "../../i18n/catalog";
import { timeZones, type TimeZoneSetting } from "../../api/generalSettings";
import { useI18n } from "../../i18n/I18nProvider";
import type { GeneralSettingsController } from "../general-settings/useGeneralSettings";

type SelectOption = { value: string; label: string };

function SelectField({ id, label, value, options, disabled = false, onChange }: { id: string; label: string; value: string; options: ReadonlyArray<SelectOption>; disabled?: boolean; onChange: (value: string) => void }) {
  return <label className="settings-select-row" htmlFor={id}><span>{label}</span><select id={id} value={value} disabled={disabled} onChange={(event) => onChange(event.target.value)}>{options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>;
}

export function GeneralSettings({ generalSettings }: { generalSettings: GeneralSettingsController }) {
  const { t } = useI18n();
  const localeOptions = supportedLocales.map((value) => ({ value, label: localeLabels[value] }));
  const timezoneOptions = [
    { value: "system", label: t("general.timezone.system") },
    { value: "Asia/Taipei", label: t("general.timezone.taipei") },
    { value: "UTC", label: t("general.timezone.utc") },
  ];
  const controlsDisabled = !generalSettings.loaded || generalSettings.saving;
  return <div className="settings-form-stack"><SettingsCard icon="globe" title={t("general.languageTime")}><SelectField id="settings-language" label={t("general.interfaceLanguage")} value={generalSettings.settings.locale} options={localeOptions} disabled={controlsDisabled} onChange={(value) => { if (isLocale(value)) void generalSettings.saveLocale(value); }} /><SelectField id="settings-timezone" label={t("general.timeZone")} value={generalSettings.settings.timeZone} options={timezoneOptions} disabled={controlsDisabled} onChange={(value) => { if (timeZones.includes(value as TimeZoneSetting)) void generalSettings.saveTimeZone(value as TimeZoneSetting); }} />{generalSettings.error ? <div className="settings-model-load-error" role="alert"><p>{generalSettings.error}</p><button type="button" className="settings-secondary-button settings-model-retry" onClick={() => void generalSettings.reload()}>{t("common.retry")}</button></div> : null}</SettingsCard><SettingsCard icon="rocket" title={t("general.startupRegion")}><FutureSettingRow label={t("general.newConversation")} description={t("general.newConversationDescription")} /><FutureSettingRow label={t("general.restoreConversation")} description={t("general.restoreConversationDescription")} /><FutureSettingRow label={t("general.sendBehavior")} description={t("general.sendBehaviorDescription")} /></SettingsCard><SettingsCard icon="bell" title={t("general.notifications")}><FutureSettingRow label={t("general.notificationPlan")} description={t("general.notificationPlanDescription")} /></SettingsCard></div>;
}
