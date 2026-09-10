import { useRef, useState, type RefObject } from "react";
import { Dropdown } from "antd";
import { UserOutlined, SettingOutlined, InfoCircleOutlined, LogoutOutlined } from "@ant-design/icons";
import { useI18n } from "../i18n/I18nProvider";

export function UserMenu({ onSettings, onLogout, triggerRef }: {
  triggerRef?: RefObject<HTMLButtonElement | null>;
  onSettings: (section: "general" | "about", opener: HTMLButtonElement) => void;
  onLogout?: () => void;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const localTrigger = useRef<HTMLButtonElement>(null);
  const trigger = triggerRef ?? localTrigger;
  return <Dropdown open={open} onOpenChange={setOpen} trigger={["click"]} placement="topLeft"
    classNames={{ root: "user-menu-popup" }}
    getPopupContainer={(node) => node.parentElement ?? document.body}
    menu={{ items: [
      { key: "identity", label: t("app.user"), disabled: true },
      { type: "divider" },
      { key: "general", label: t("app.settings"), icon: <SettingOutlined aria-hidden="true" /> },
      { key: "about", label: t("settings.category.about"), icon: <InfoCircleOutlined aria-hidden="true" /> },
      ...(onLogout ? [{ type: "divider" as const }, { key: "logout", label: t("app.logout"), icon: <LogoutOutlined /> }] : []),
    ], onClick: ({ key }) => {
      setOpen(false);
      if (key === "logout") onLogout?.();
      else if ((key === "general" || key === "about") && trigger.current) onSettings(key, trigger.current);
    }, onKeyDown: (event) => {
      if (event.key === "Escape") { event.stopPropagation(); setOpen(false); trigger.current?.focus(); }
    } }}>
    <button ref={trigger} type="button" className="user-menu-trigger" aria-haspopup="menu" aria-expanded={open}>
      <UserOutlined aria-hidden="true" /><span>{t("app.user")}</span>
    </button>
  </Dropdown>;
}
