import { FutureSettingRow, SettingsCard } from "./SettingsPrimitives";
import { Alert, Button, Collapse, Select, Switch } from "antd";
import { useRef } from "react";
import { isLocale, localeLabels, supportedLocales } from "../../i18n/catalog";
import { timeZones, type TimeZoneSetting } from "../../api/generalSettings";
import { useI18n } from "../../i18n/I18nProvider";
import type { GeneralSettingsController } from "../general-settings/useGeneralSettings";
import { sendBehaviors, startupViews, type SendBehavior, type StartupView } from "../../api/conversationSettings";
import type { ConversationSettingsController } from "../conversation-settings/useConversationSettings";

type SelectOption = { value: string; label: string };

function SelectField({ id, label, description, value, options, disabled = false, onChange, getPopupContainer }: { id: string; label: string; description?: string; value: string; options: ReadonlyArray<SelectOption>; disabled?: boolean; onChange: (value: string) => void; getPopupContainer: () => HTMLElement }) {
  return <div className="settings-select-row">
    <label htmlFor={id}><span className="settings-control-label">{label}</span>{description ? <span id={id + "-description"} className="settings-control-description">{description}</span> : null}</label>
    <Select id={id} aria-label={label} aria-describedby={description ? id + "-description" : undefined} value={value} disabled={disabled} options={[...options]} getPopupContainer={getPopupContainer} onChange={onChange} />
  </div>;
}

function ToggleField({ label, description, checked, disabled, onChange }: { label: string; description: string; checked: boolean; disabled: boolean; onChange: (checked: boolean) => void }) {
  return <div className="settings-toggle-row"><span><span className="settings-control-label">{label}</span><span className="settings-control-description">{description}</span></span><Switch aria-label={label} checked={checked} disabled={disabled} onChange={onChange} /></div>;
}

export function GeneralSettings({ generalSettings, conversationSettings }: { generalSettings: GeneralSettingsController; conversationSettings: ConversationSettingsController }) {
  const { t } = useI18n();
  const root = useRef<HTMLDivElement | null>(null);
  const getPopupContainer = () => root.current ?? document.body;
  const localeOptions = supportedLocales.map((value) => ({ value, label: localeLabels[value] }));
  const timezoneOptions = [
    { value: "system", label: t("general.timezone.system") },
    { value: "Asia/Taipei", label: t("general.timezone.taipei") },
    { value: "UTC", label: t("general.timezone.utc") },
  ];
  const controlsDisabled = !generalSettings.loaded || generalSettings.saving;
  const conversationControlsDisabled = !conversationSettings.loaded || conversationSettings.saving;
  const startupOptions = [
    { value: "new", label: t("general.startup.new") },
    { value: "recent", label: t("general.startup.recent") },
  ];
  const sendOptions = [
    { value: "enter", label: t("general.send.enterShort") },
    { value: "modifier-enter", label: t("general.send.modifierEnterShort") },
  ];
  return <div ref={root} className="settings-form-stack settings-general-layout">
    <SettingsCard icon="globe" title={t("general.languageTime")}>
      {!generalSettings.loaded && !generalSettings.error ? <p role="status" className="settings-helper-text">{t("general.loading")}</p> : null}
      <SelectField id="settings-language" label={t("general.interfaceLanguage")} value={generalSettings.settings.locale} options={localeOptions} disabled={controlsDisabled} getPopupContainer={getPopupContainer} onChange={(value) => { if (isLocale(value)) void generalSettings.saveLocale(value); }} />
      <SelectField id="settings-timezone" label={t("general.timeZone")} value={generalSettings.settings.timeZone} options={timezoneOptions} disabled={controlsDisabled} getPopupContainer={getPopupContainer} onChange={(value) => { if (timeZones.includes(value as TimeZoneSetting)) void generalSettings.saveTimeZone(value as TimeZoneSetting); }} />
      {generalSettings.error ? <Alert type="error" title={generalSettings.error} action={<Button disabled={generalSettings.saving} onClick={() => void generalSettings.reload()}>{t("general.reload")}</Button>} /> : null}
    </SettingsCard>
    <SettingsCard icon="rocket" title={t("general.conversationPreferences")}>
      {!conversationSettings.loaded && !conversationSettings.error ? <p role="status" className="settings-helper-text">{t("general.loading")}</p> : null}
      <SelectField id="settings-startup-view" label={t("general.startupView")} value={conversationSettings.settings.startupView} options={startupOptions} disabled={conversationControlsDisabled} getPopupContainer={getPopupContainer} onChange={(value) => { if (startupViews.includes(value as StartupView)) void conversationSettings.saveStartupView(value as StartupView); }} />
      <SelectField id="settings-send-behavior" label={t("general.sendBehavior")} description={t(conversationSettings.settings.sendBehavior === "enter" ? "general.send.enter" : "general.send.modifierEnter")} value={conversationSettings.settings.sendBehavior} options={sendOptions} disabled={conversationControlsDisabled} getPopupContainer={getPopupContainer} onChange={(value) => { if (sendBehaviors.includes(value as SendBehavior)) void conversationSettings.saveSendBehavior(value as SendBehavior); }} />
      <ToggleField label={t("general.autoScroll")} description={t("general.autoScrollDescription")} checked={conversationSettings.settings.autoScroll} disabled={conversationControlsDisabled} onChange={(checked) => void conversationSettings.saveAutoScroll(checked)} />
    </SettingsCard>
    <SettingsCard icon="info" title={t("general.executionPanel")}>
      <ToggleField label={t("general.executionPanelDefaultExpanded")} description={t("general.executionPanelHelp")} checked={conversationSettings.settings.executionPanelDefaultExpanded} disabled={conversationControlsDisabled} onChange={(checked) => void conversationSettings.saveExecutionPanelDefaultExpanded(checked)} />
    </SettingsCard>
    {conversationSettings.error ? <Alert type="error" title={t("general.conversationErrorScope")} description={conversationSettings.error} action={<Button disabled={conversationSettings.saving} onClick={() => void conversationSettings.reload()}>{t("general.reload")}</Button>} /> : null}
    <Collapse className="settings-general-planned" items={[{ key: "planned", label: t("general.planned"), children: <FutureSettingRow label={t("general.notificationPlan")} description={t("general.notificationPlanDescription")} /> }]} />
  </div>;
}
