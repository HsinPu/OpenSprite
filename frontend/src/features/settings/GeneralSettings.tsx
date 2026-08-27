import { SettingsCard } from "./SettingsPrimitives";
import type { DemoSettings } from "./settingsState";
import { isLocale, localeLabels, supportedLocales } from "../../i18n/catalog";
import { useI18n } from "../../i18n/I18nProvider";

type ChangeSetting = <K extends keyof DemoSettings>(key: K, value: DemoSettings[K]) => void;

function DemoSwitch({ checked, label, description, onChange }: { checked: boolean; label: string; description?: string; onChange: (checked: boolean) => void }) {
  return <label className="settings-switch-row"><span><span className="settings-control-label">{label}</span>{description ? <span className="settings-control-description">{description}</span> : null}</span><input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} /><span className="settings-switch" aria-hidden="true"><span /></span></label>;
}

type SelectOption = { value: string; label: string };

function SelectField({ id, label, value, options, onChange }: { id: string; label: string; value: string; options: ReadonlyArray<SelectOption>; onChange: (value: string) => void }) {
  return <label className="settings-select-row" htmlFor={id}><span>{label}</span><select id={id} value={value} onChange={(event) => onChange(event.target.value)}>{options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>;
}

export function GeneralSettings({ settings, onChange }: { settings: DemoSettings; onChange: ChangeSetting }) {
  const { locale, setLocale, t } = useI18n();
  const localeOptions = supportedLocales.map((value) => ({ value, label: localeLabels[value] }));
  const timezoneOptions = [
    { value: "system", label: t("general.timezone.system") },
    { value: "asia-taipei", label: t("general.timezone.taipei") },
    { value: "utc", label: t("general.timezone.utc") },
  ];
  const sendModeOptions = [
    { value: "enter", label: t("general.sendMode.enter") },
    { value: "ctrl-enter", label: t("general.sendMode.ctrlEnter") },
  ];
  return <div className="settings-form-stack"><SettingsCard icon="globe" title={t("general.languageRegion")}><SelectField id="settings-language" label={t("general.interfaceLanguage")} value={locale} options={localeOptions} onChange={(value) => { if (isLocale(value)) setLocale(value); }} /><SelectField id="settings-timezone" label={t("general.dateTime")} value={settings.timezone} options={timezoneOptions} onChange={(value) => onChange("timezone", value as DemoSettings["timezone"])} /></SettingsCard><SettingsCard icon="rocket" title={t("general.startupRegion")}><DemoSwitch checked={settings.newConversation} label={t("general.newConversation")} description={t("general.newConversationDescription")} onChange={(value) => onChange("newConversation", value)} /><DemoSwitch checked={settings.restoreConversation} label={t("general.restoreConversation")} description={t("general.restoreConversationDescription")} onChange={(value) => onChange("restoreConversation", value)} /><SelectField id="settings-send-mode" label={t("general.sendMessage")} value={settings.sendMode} options={sendModeOptions} onChange={(value) => onChange("sendMode", value as DemoSettings["sendMode"])} /></SettingsCard><SettingsCard icon="bell" title={t("general.notifications")}><DemoSwitch checked={settings.taskNotifications} label={t("general.taskNotifications")} onChange={(value) => onChange("taskNotifications", value)} /><DemoSwitch checked={settings.confirmNotifications} label={t("general.confirmNotifications")} onChange={(value) => onChange("confirmNotifications", value)} /><DemoSwitch checked={settings.sound} label={t("general.sound")} onChange={(value) => onChange("sound", value)} /></SettingsCard></div>;
}
