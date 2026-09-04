import { useId, type ReactNode } from "react";

import { useI18n } from "../../i18n/I18nProvider";

export type IconName = "settings" | "folder" | "robot" | "database" | "connections" | "schedules" | "appearance" | "privacy" | "info" | "globe" | "rocket" | "bell" | "openai" | "anthropic" | "openrouter";

export function Icon({ name }: { name: IconName }) {
  if (name === "openai") return <span className="settings-brand-icon settings-brand-icon--openai" aria-hidden="true">◎</span>;
  if (name === "anthropic") return <span className="settings-brand-icon settings-brand-icon--anthropic" aria-hidden="true">AI</span>;
  if (name === "openrouter") return <span className="settings-brand-icon settings-brand-icon--openrouter" aria-hidden="true">OR</span>;
  const paths: Record<Exclude<IconName, "openai" | "anthropic" | "openrouter">, string> = {
    settings: "M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Zm8.2 3.5 1.6-1.2-1.7-2.9-1.9.7a8.1 8.1 0 0 0-1.5-.9l-.3-2h-3.4l-.3 2a8 8 0 0 0-1.5.9l-1.9-.7-1.7 2.9 1.6 1.2a7.3 7.3 0 0 0 0 1.8l-1.6 1.2 1.7 2.9 1.9-.7c.5.4 1 .7 1.5.9l.3 2h3.4l.3-2c.5-.2 1-.5 1.5-.9l1.9.7 1.7-2.9-1.6-1.2a7.3 7.3 0 0 0 0-1.8Z",
    folder: "M3 6h7l2 2h9v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6Zm0 4h18",
    robot: "M8 8h8a4 4 0 0 1 4 4v5H4v-5a4 4 0 0 1 4-4Zm4-4v4m-5 9v2m10-2v2M9 13h.1M15 13h.1",
    database: "M5 6c0-1.1 3.1-2 7-2s7 .9 7 2-3.1 2-7 2-7-.9-7-2Zm0 0v6c0 1.1 3.1 2 7 2s7-.9 7-2V6m-14 6v6c0 1.1 3.1 2 7 2s7-.9 7-2v-6",
    connections: "M8 12h8m-9-4a3 3 0 1 1 0-6 3 3 0 0 1 0 6Zm10 10a3 3 0 1 1 0-6 3 3 0 0 1 0 6ZM6 21a3 3 0 1 1 0-6 3 3 0 0 1 0 6Zm3-9 7 3m-7-6 7-3",
    schedules: "M7 3v3m10-3v3M4 9h16M5 5h14a1 1 0 0 1 1 1v14H4V6a1 1 0 0 1 1-1Zm7 7v4l3 2",
    appearance: "M12 3a9 9 0 0 0 0 18h1.2a1.8 1.8 0 0 0 1.7-2.4 1.8 1.8 0 0 1 1.7-2.4H19a2 2 0 0 0 2-2A9 9 0 0 0 12 3Zm-4 9h.1M8 8h.1m4-2h.1m4 3h.1",
    privacy: "M12 3 19 6v5c0 4.3-2.9 8.1-7 9-4.1-.9-7-4.7-7-9V6l7-3Zm-2 9 1.5 1.5L15 10",
    info: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-10v5m0-8h.1",
    globe: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm-8.5-9h17M12 3c2 2.2 3 5.2 3 9s-1 6.8-3 9c-2-2.2-3-5.2-3-9s1-6.8 3-9Z",
    rocket: "m14 4 6 6-3 1-4 4-1 3-3-3-3-1 4-4 1-3 3-3Zm-5 11-3 3m0-5-2 2m9-8h.1",
    bell: "M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9Zm-8 13h4",
  };
  return <svg className="settings-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>;
}

export function SaveStatus({ saved }: { saved: boolean }) {
  const { t } = useI18n();
  return <p className={`settings-save-status${saved ? " settings-save-status--saved" : ""}`} role="status" aria-live="polite"><span className="settings-save-dot" aria-hidden="true">{saved ? "✓" : "•"}</span>{saved ? t("settings.saved") : t("settings.saving")}</p>;
}

export function FutureSettingRow({ label, description }: { label: string; description: string }) {
  const { t } = useI18n();
  return <div className="settings-future-row" aria-label={t("settings.futureLabel", { label })}><span><span className="settings-control-label">{label}</span><span className="settings-control-description">{description}</span></span><span className="settings-future-badge">{t("settings.future")}</span></div>;
}

export function SettingsCard({ icon, title, children }: { icon: IconName; title: string; children: ReactNode }) {
  const headingId = `${useId()}-heading`;
  return <section className="settings-card" aria-labelledby={headingId}><h3 id={headingId} className="settings-card-title"><Icon name={icon} />{title}</h3><div className="settings-card-body">{children}</div></section>;
}
