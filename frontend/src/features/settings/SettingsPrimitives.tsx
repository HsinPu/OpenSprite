import { useId, type ReactNode } from "react";

import { useI18n } from "../../i18n/I18nProvider";

export type IconName = "settings" | "robot" | "connections" | "globe" | "openai" | "anthropic" | "openrouter";

export function Icon({ name }: { name: IconName }) {
  if (name === "openai") return <span className="settings-brand-icon settings-brand-icon--openai" aria-hidden="true">◎</span>;
  if (name === "anthropic") return <span className="settings-brand-icon settings-brand-icon--anthropic" aria-hidden="true">AI</span>;
  if (name === "openrouter") return <span className="settings-brand-icon settings-brand-icon--openrouter" aria-hidden="true">OR</span>;
  const paths: Record<Exclude<IconName, "openai" | "anthropic" | "openrouter">, string> = {
    settings: "M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Zm8.2 3.5 1.6-1.2-1.7-2.9-1.9.7a8.1 8.1 0 0 0-1.5-.9l-.3-2h-3.4l-.3 2a8 8 0 0 0-1.5.9l-1.9-.7-1.7 2.9 1.6 1.2a7.3 7.3 0 0 0 0 1.8l-1.6 1.2 1.7 2.9 1.9-.7c.5.4 1 .7 1.5.9l.3 2h3.4l.3-2c.5-.2 1-.5 1.5-.9l1.9.7 1.7-2.9-1.6-1.2a7.3 7.3 0 0 0 0-1.8Z",
    robot: "M8 8h8a4 4 0 0 1 4 4v5H4v-5a4 4 0 0 1 4-4Zm4-4v4m-5 9v2m10-2v2M9 13h.1M15 13h.1",
    connections: "M8 12h8m-9-4a3 3 0 1 1 0-6 3 3 0 0 1 0 6Zm10 10a3 3 0 1 1 0-6 3 3 0 0 1 0 6ZM6 21a3 3 0 1 1 0-6 3 3 0 0 1 0 6Zm3-9 7 3m-7-6 7-3",
    globe: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm-8.5-9h17M12 3c2 2.2 3 5.2 3 9s-1 6.8-3 9c-2-2.2-3-5.2-3-9s1-6.8 3-9Z",
  };
  return <svg className="settings-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>;
}

export function SaveStatus({ saved }: { saved: boolean }) {
  const { t } = useI18n();
  return <p className={`settings-save-status${saved ? " settings-save-status--saved" : ""}`} role="status" aria-live="polite"><span className="settings-save-dot" aria-hidden="true">{saved ? "✓" : "•"}</span>{saved ? t("settings.saved") : t("settings.saving")}</p>;
}

export function SettingsCard({ icon, title, children }: { icon: IconName; title: string; children: ReactNode }) {
  const headingId = `${useId()}-heading`;
  return <section className="settings-card" aria-labelledby={headingId}><h3 id={headingId} className="settings-card-title"><Icon name={icon} />{title}</h3><div className="settings-card-body">{children}</div></section>;
}
