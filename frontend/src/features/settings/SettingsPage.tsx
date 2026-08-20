import { useEffect, useState, type ReactNode } from "react";

import "./settings.css";

export type SettingsSection = "general" | "models";

export type DemoSettings = {
  language: string;
  timezone: string;
  newConversation: boolean;
  restoreConversation: boolean;
  sendMode: string;
  taskNotifications: boolean;
  confirmNotifications: boolean;
  sound: boolean;
  defaultModel: string;
  responseSpeed: string;
  autoSelect: boolean;
  showNames: boolean;
  anthropicConnected: boolean;
};

export const defaultDemoSettings: DemoSettings = {
  language: "繁體中文",
  timezone: "依照系統設定",
  newConversation: true,
  restoreConversation: false,
  sendMode: "Enter 送出，Shift + Enter 換行",
  taskNotifications: true,
  confirmNotifications: true,
  sound: false,
  defaultModel: "OpenAI · GPT-5.6",
  responseSpeed: "平衡",
  autoSelect: true,
  showNames: true,
  anthropicConnected: false,
};

type SettingsPageProps = {
  section: SettingsSection;
  onSectionChange: (section: SettingsSection) => void;
  settings: DemoSettings;
  onSettingsChange: (next: DemoSettings) => void;
  onClose: () => void;
};

type IconName = "settings" | "robot" | "database" | "connections" | "appearance" | "privacy" | "info" | "globe" | "rocket" | "bell" | "openai" | "anthropic";

const categories: Array<{ id: SettingsSection | "memory" | "tools" | "appearance" | "privacy" | "about"; label: string; icon: IconName; enabled?: boolean }> = [
  { id: "general", label: "一般", icon: "settings", enabled: true },
  { id: "models", label: "AI 模型", icon: "robot", enabled: true },
  { id: "memory", label: "記憶與資料", icon: "database" },
  { id: "tools", label: "工具與連線", icon: "connections" },
  { id: "appearance", label: "外觀", icon: "appearance" },
  { id: "privacy", label: "隱私", icon: "privacy" },
  { id: "about", label: "關於", icon: "info" },
];

function Icon({ name }: { name: IconName }) {
  if (name === "openai") {
    return <span className="settings-brand-icon settings-brand-icon--openai" aria-hidden="true">◎</span>;
  }

  if (name === "anthropic") {
    return <span className="settings-brand-icon settings-brand-icon--anthropic" aria-hidden="true">AI</span>;
  }

  const paths: Record<Exclude<IconName, "openai" | "anthropic">, string> = {
    settings: "M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Zm8.2 3.5 1.6-1.2-1.7-2.9-1.9.7a8.1 8.1 0 0 0-1.5-.9l-.3-2h-3.4l-.3 2a8 8 0 0 0-1.5.9l-1.9-.7-1.7 2.9 1.6 1.2a7.3 7.3 0 0 0 0 1.8l-1.6 1.2 1.7 2.9 1.9-.7c.5.4 1 .7 1.5.9l.3 2h3.4l.3-2c.5-.2 1-.5 1.5-.9l1.9.7 1.7-2.9-1.6-1.2a7.3 7.3 0 0 0 0-1.8Z",
    robot: "M8 8h8a4 4 0 0 1 4 4v5H4v-5a4 4 0 0 1 4-4Zm4-4v4m-5 9v2m10-2v2M9 13h.1M15 13h.1",
    database: "M5 6c0-1.1 3.1-2 7-2s7 .9 7 2-3.1 2-7 2-7-.9-7-2Zm0 0v6c0 1.1 3.1 2 7 2s7-.9 7-2V6m-14 6v6c0 1.1 3.1 2 7 2s7-.9 7-2v-6",
    connections: "M8 12h8m-9-4a3 3 0 1 1 0-6 3 3 0 0 1 0 6Zm10 10a3 3 0 1 1 0-6 3 3 0 0 1 0 6ZM6 21a3 3 0 1 1 0-6 3 3 0 0 1 0 6Zm3-9 7 3m-7-6 7-3",
    appearance: "M12 3a9 9 0 0 0 0 18h1.2a1.8 1.8 0 0 0 1.7-2.4 1.8 1.8 0 0 1 1.7-2.4H19a2 2 0 0 0 2-2A9 9 0 0 0 12 3Zm-4 9h.1M8 8h.1m4-2h.1m4 3h.1",
    privacy: "M12 3 19 6v5c0 4.3-2.9 8.1-7 9-4.1-.9-7-4.7-7-9V6l7-3Zm-2 9 1.5 1.5L15 10",
    info: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-10v5m0-8h.1",
    globe: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm-8.5-9h17M12 3c2 2.2 3 5.2 3 9s-1 6.8-3 9c-2-2.2-3-5.2-3-9s1-6.8 3-9Z",
    rocket: "m14 4 6 6-3 1-4 4-1 3-3-3-3-1 4-4 1-3 3-3Zm-5 11-3 3m0-5-2 2m9-8h.1",
    bell: "M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9Zm-8 13h4",
  };

  return (
    <svg className="settings-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={paths[name]} />
    </svg>
  );
}

function SaveStatus({ saved }: { saved: boolean }) {
  return (
    <p className={`settings-save-status${saved ? " settings-save-status--saved" : ""}`} role="status" aria-live="polite">
      <span className="settings-save-dot" aria-hidden="true">{saved ? "✓" : "•"}</span>
      {saved ? "已儲存" : "儲存中…"}
    </p>
  );
}

function DemoSwitch({ checked, label, description, onChange }: { checked: boolean; label: string; description?: string; onChange: (checked: boolean) => void }) {
  return (
    <label className="settings-switch-row">
      <span>
        <span className="settings-control-label">{label}</span>
        {description ? <span className="settings-control-description">{description}</span> : null}
      </span>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span className="settings-switch" aria-hidden="true"><span /></span>
    </label>
  );
}

function SelectField({ id, label, value, options, onChange }: { id: string; label: string; value: string; options: string[]; onChange: (value: string) => void }) {
  return (
    <label className="settings-select-row" htmlFor={id}>
      <span>{label}</span>
      <select id={id} value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => <option key={option}>{option}</option>)}
      </select>
    </label>
  );
}

function SettingsCard({ icon, title, children }: { icon: IconName; title: string; children: ReactNode }) {
  return (
    <section className="settings-card" aria-labelledby={`${title}-heading`}>
      <h3 id={`${title}-heading`} className="settings-card-title"><Icon name={icon} />{title}</h3>
      <div className="settings-card-body">{children}</div>
    </section>
  );
}

function GeneralSettings({ settings, onChange }: { settings: DemoSettings; onChange: <K extends keyof DemoSettings>(key: K, value: DemoSettings[K]) => void }) {

  return (
    <div className="settings-form-stack">
      <SettingsCard icon="globe" title="語言與地區">
        <SelectField id="settings-language" label="介面語言" value={settings.language} options={["繁體中文", "English", "日本語"]} onChange={(value) => onChange("language", value)} />
        <SelectField id="settings-timezone" label="日期與時間" value={settings.timezone} options={["依照系統設定", "Asia/Taipei (UTC+8)", "UTC"]} onChange={(value) => onChange("timezone", value)} />
      </SettingsCard>

      <SettingsCard icon="rocket" title="啟動與對話">
        <DemoSwitch checked={settings.newConversation} label="開啟 OpenSprite 時建立新對話" description="每次啟動都從乾淨的對話開始" onChange={(value) => onChange("newConversation", value)} />
        <DemoSwitch checked={settings.restoreConversation} label="保留上次開啟的對話" description="回到上次使用中的對話" onChange={(value) => onChange("restoreConversation", value)} />
        <SelectField id="settings-send-mode" label="送出訊息" value={settings.sendMode} options={["Enter 送出，Shift + Enter 換行", "Ctrl + Enter 送出，Enter 換行"]} onChange={(value) => onChange("sendMode", value)} />
      </SettingsCard>

      <SettingsCard icon="bell" title="通知">
        <DemoSwitch checked={settings.taskNotifications} label="任務完成時通知我" onChange={(value) => onChange("taskNotifications", value)} />
        <DemoSwitch checked={settings.confirmNotifications} label="需要我確認時通知我" onChange={(value) => onChange("confirmNotifications", value)} />
        <DemoSwitch checked={settings.sound} label="播放提示音" onChange={(value) => onChange("sound", value)} />
      </SettingsCard>
    </div>
  );
}

function ModelsSettings({ settings, onChange }: { settings: DemoSettings; onChange: <K extends keyof DemoSettings>(key: K, value: DemoSettings[K]) => void }) {
  const [testStatus, setTestStatus] = useState<"idle" | "testing" | "success">("idle");

  const testConnection = () => {
    setTestStatus("testing");
    window.setTimeout(() => setTestStatus("success"), 500);
  };

  return (
    <div className="settings-form-stack">
      <section className="settings-model-section" aria-labelledby="default-model-heading">
        <h3 id="default-model-heading" className="settings-subheading">預設模型</h3>
        <label className="settings-model-select" htmlFor="settings-default-model">
          <span className="settings-model-select-main"><Icon name="openai" /><span>{settings.defaultModel}</span></span>
          <span className="settings-connected-badge">已連線</span>
          <select id="settings-default-model" value={settings.defaultModel} onChange={(event) => onChange("defaultModel", event.target.value)} aria-label="選擇預設模型">
            <option>OpenAI · GPT-5.6</option>
            <option>OpenAI · GPT-5.6 mini</option>
          </select>
        </label>
        <p className="settings-helper-text">新對話會優先使用這個模型</p>
      </section>

      <section className="settings-model-section" aria-labelledby="connected-services-heading">
        <h3 id="connected-services-heading" className="settings-subheading">已連接的服務</h3>
        <div className="settings-service-list">
          <div className="settings-service-card">
            <div className="settings-service-identity"><Icon name="openai" /><span><strong>OpenAI</strong><span className="settings-online"><i aria-hidden="true" />已連線</span><small>API Key ·••••••••8K2</small></span></div>
            <div className="settings-service-actions">
              <button type="button" className="settings-secondary-button" disabled title="Demo 版本尚未提供連線管理">管理</button>
              <button type="button" className="settings-secondary-button" onClick={testConnection} disabled={testStatus === "testing"}>{testStatus === "testing" ? "測試中…" : "測試連線"}</button>
              {testStatus === "success" ? <span className="settings-action-status" role="status">連線成功</span> : null}
            </div>
          </div>
          <div className="settings-service-card settings-service-card--disconnected">
            <div className="settings-service-identity"><Icon name="anthropic" /><span><strong>Anthropic</strong>{settings.anthropicConnected ? <span className="settings-online" role="status"><i aria-hidden="true" />已連線</span> : <span className="settings-offline"><i aria-hidden="true" />尚未連線</span>}</span></div>
            <button type="button" className="settings-outline-button" onClick={() => onChange("anthropicConnected", true)} disabled={settings.anthropicConnected}>{settings.anthropicConnected ? "已連線" : "連接"}</button>
          </div>
        </div>
        <button type="button" className="settings-add-link" disabled title="Demo 版本尚未提供新增服務"><span aria-hidden="true">＋</span>新增其他服務</button>
      </section>

      <section className="settings-card settings-preferences" aria-labelledby="model-preferences-heading">
        <h3 id="model-preferences-heading" className="settings-subheading">模型偏好</h3>
        <div className="settings-preference-row"><span>回應速度</span><div className="settings-segmented" role="group" aria-label="回應速度">{["快速", "平衡", "深入"].map((option) => <button key={option} type="button" className={settings.responseSpeed === option ? "is-selected" : ""} aria-pressed={settings.responseSpeed === option} onClick={() => onChange("responseSpeed", option)}>{option}</button>)}</div></div>
        <DemoSwitch checked={settings.autoSelect} label="自動選擇可用模型" onChange={(value) => onChange("autoSelect", value)} />
        <DemoSwitch checked={settings.showNames} label="顯示模型名稱" onChange={(value) => onChange("showNames", value)} />
      </section>
    </div>
  );
}

export function SettingsPage({ section, onSectionChange, settings, onSettingsChange, onClose }: SettingsPageProps) {
  const [saved, setSaved] = useState(true);

  useEffect(() => {
    if (saved) return;
    const timeout = window.setTimeout(() => setSaved(true), 650);
    return () => window.clearTimeout(timeout);
  }, [saved]);

  const markChanged = () => setSaved(false);
  const updateSetting = <K extends keyof DemoSettings>(key: K, value: DemoSettings[K]) => {
    onSettingsChange({ ...settings, [key]: value });
    markChanged();
  };

  return (
    <section className="settings-page" aria-labelledby="settings-page-title">
      <header className="settings-header">
        <div><h1 id="settings-page-title">設定</h1><p>調整 OpenSprite 的使用方式</p></div>
        <div className="settings-header-actions">
          <SaveStatus saved={saved} />
          <button className="settings-close-button" type="button" onClick={onClose} aria-label="關閉設定" title="關閉設定">
            <span aria-hidden="true">×</span>
          </button>
        </div>
      </header>
      <div className="settings-layout">
        <nav className="settings-category-rail" aria-label="設定分類">
          {categories.map((category) => {
            const isSelected = category.id === section;
            const isEnabled = category.enabled === true;
            return <button key={category.id} type="button" className={`settings-category${isSelected ? " is-selected" : ""}${!isEnabled ? " is-disabled" : ""}`} onClick={() => { if (isEnabled) onSectionChange(category.id as SettingsSection); }} disabled={!isEnabled} aria-current={isSelected ? "page" : undefined}>
              <Icon name={category.icon} /><span>{category.label}</span>{!isEnabled ? <small>Demo</small> : null}
            </button>;
          })}
          <p className="settings-rail-note">其他分類將在完整版本提供</p>
        </nav>
        <div className="settings-content">
          {section === "general" ? <><div className="settings-intro"><h2>一般</h2><p>設定語言、啟動方式與日常使用偏好。</p></div><GeneralSettings settings={settings} onChange={updateSetting} /></> : <><div className="settings-intro"><h2>AI 模型</h2><p>連接你要使用的 AI 服務，並選擇預設模型。</p></div><ModelsSettings settings={settings} onChange={updateSetting} /></>}
          <p className="settings-demo-note">Demo 設定會在本次工作階段暫存，不會連接或儲存任何真實帳號資料。</p>
        </div>
      </div>
    </section>
  );
}

export default SettingsPage;
