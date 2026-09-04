import { DownOutlined, FolderOutlined, PlusOutlined, SettingOutlined } from "@ant-design/icons";
import { Button, Dropdown, type MenuProps } from "antd";

import type { WorkspaceController } from "./useWorkspaces";
import { workspaceErrorText } from "../../api/workspaces";
import { useI18n } from "../../i18n/I18nProvider";

export function workspaceName(kind: "unassigned" | "directory", name: string, unassigned: string): string {
  return kind === "unassigned" ? unassigned : name;
}

export function WorkspaceSwitcher({
  controller,
  collapsed,
  onActivate,
  onCreate,
  onManage,
}: {
  controller: WorkspaceController;
  collapsed: boolean;
  onActivate: (workspaceId: string) => void;
  onCreate: () => void;
  onManage: () => void;
}) {
  const { t } = useI18n();
  const active = controller.activeWorkspace;
  const displayName = active
    ? workspaceName(active.kind, active.name, t("workspaces.unassigned"))
    : t("workspaces.loading");
  const items: MenuProps["items"] = [
    ...(controller.catalog?.workspaces.map((item) => ({
      key: `workspace:${item.id}`,
      label: <span className="workspace-menu-label"><span className={`workspace-status-dot workspace-status-dot--${item.availability}`} aria-hidden="true" />{workspaceName(item.kind, item.name, t("workspaces.unassigned"))}</span>,
    })) ?? []),
    { type: "divider" as const },
    { key: "create", icon: <PlusOutlined />, label: t("workspaces.create") },
    { key: "manage", icon: <SettingOutlined />, label: t("workspaces.manage") },
  ];
  const select: MenuProps["onClick"] = ({ key }) => {
    if (key === "create") {
      onCreate();
      return;
    }
    if (key === "manage") {
      onManage();
      return;
    }
    if (key.startsWith("workspace:")) onActivate(key.slice("workspace:".length));
  };

  return <div className="workspace-switcher">
    <Dropdown menu={{ items, onClick: select, selectedKeys: active ? [`workspace:${active.id}`] : [] }} trigger={["click"]} disabled={!controller.catalog || controller.saving}>
      <Button className="workspace-switcher__button" aria-label={t("workspaces.switchLabel", { name: displayName })} title={active?.rootPath ?? displayName}>
        <FolderOutlined />
        <span className="workspace-switcher__name">{displayName}</span>
        {active?.availability === "unavailable" ? <span className="workspace-status-dot workspace-status-dot--unavailable" aria-label={t("workspaces.unavailable")} /> : null}
        {!collapsed ? <DownOutlined className="workspace-switcher__chevron" /> : null}
      </Button>
    </Dropdown>
    {controller.error ? <span className="workspace-switcher__error" role="status">{workspaceErrorText(controller.error, t)}</span> : null}
  </div>;
}
