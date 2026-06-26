import type { ReactNode } from "react";
import { Alert, Card, Typography } from "antd";

export function SettingsSectionTitle({ children }: { children: ReactNode }) {
  return <Typography.Title className="settings-section-title" level={5}>{children}</Typography.Title>;
}

export function SettingsCard({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <Card size="small" className={["settings-card", className].filter(Boolean).join(" ")}>{children}</Card>;
}

export function SettingsStatus({ message, type = "info" }: { message?: string; type?: "info" | "success" | "warning" | "error" }) {
  return message ? <Alert className="settings-inline-status" type={type} showIcon message={message} /> : null;
}

export function SettingsRow({
  title,
  description,
  children,
  className = "",
}: {
  title: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <div className={["settings-row", className].filter(Boolean).join(" ")}>
      <div className="settings-row__copy">
        <Typography.Text strong>{title}</Typography.Text>
        {description ? <Typography.Text type="secondary">{description}</Typography.Text> : null}
      </div>
      {children ? <div className="settings-row__control">{children}</div> : null}
    </div>
  );
}
