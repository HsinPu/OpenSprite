import { SettingsCard } from "./SettingsPrimitives";
import type { DemoSettings } from "./settingsState";

type ChangeSetting = <K extends keyof DemoSettings>(key: K, value: DemoSettings[K]) => void;

function DemoSwitch({ checked, label, description, onChange }: { checked: boolean; label: string; description?: string; onChange: (checked: boolean) => void }) {
  return <label className="settings-switch-row"><span><span className="settings-control-label">{label}</span>{description ? <span className="settings-control-description">{description}</span> : null}</span><input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} /><span className="settings-switch" aria-hidden="true"><span /></span></label>;
}

function SelectField({ id, label, value, options, onChange }: { id: string; label: string; value: string; options: string[]; onChange: (value: string) => void }) {
  return <label className="settings-select-row" htmlFor={id}><span>{label}</span><select id={id} value={value} onChange={(event) => onChange(event.target.value)}>{options.map((option) => <option key={option}>{option}</option>)}</select></label>;
}

export function GeneralSettings({ settings, onChange }: { settings: DemoSettings; onChange: ChangeSetting }) {
  return <div className="settings-form-stack"><SettingsCard icon="globe" title="語言與地區"><SelectField id="settings-language" label="介面語言" value={settings.language} options={["繁體中文", "English", "日本語"]} onChange={(value) => onChange("language", value)} /><SelectField id="settings-timezone" label="日期與時間" value={settings.timezone} options={["依照系統設定", "Asia/Taipei (UTC+8)", "UTC"]} onChange={(value) => onChange("timezone", value)} /></SettingsCard><SettingsCard icon="rocket" title="啟動與對話"><DemoSwitch checked={settings.newConversation} label="開啟 OpenSprite 時建立新對話" description="每次啟動都從乾淨的對話開始" onChange={(value) => onChange("newConversation", value)} /><DemoSwitch checked={settings.restoreConversation} label="保留上次開啟的對話" description="回到上次使用中的對話" onChange={(value) => onChange("restoreConversation", value)} /><SelectField id="settings-send-mode" label="送出訊息" value={settings.sendMode} options={["Enter 送出，Shift + Enter 換行", "Ctrl + Enter 送出，Enter 換行"]} onChange={(value) => onChange("sendMode", value)} /></SettingsCard><SettingsCard icon="bell" title="通知"><DemoSwitch checked={settings.taskNotifications} label="任務完成時通知我" onChange={(value) => onChange("taskNotifications", value)} /><DemoSwitch checked={settings.confirmNotifications} label="需要我確認時通知我" onChange={(value) => onChange("confirmNotifications", value)} /><DemoSwitch checked={settings.sound} label="播放提示音" onChange={(value) => onChange("sound", value)} /></SettingsCard></div>;
}
