import { useEffect, useState, useTransition } from "react";
import {
  ApiOutlined,
  BranchesOutlined,
  CloseOutlined,
  EyeOutlined,
  HistoryOutlined,
  SendOutlined,
  SettingOutlined,
  ToolOutlined,
} from "@ant-design/icons";
import { Button, Layout, Menu, Modal, Spin, Typography } from "antd";
import { BrowserSettings } from "./browserSettings";
import { ChannelSettings } from "./channelSettings";
import { GeneralSettings } from "./generalSettings";
import { LogSettings } from "./logSettings";
import { McpSettings } from "./mcpSettings";
import { ModelSettings } from "./modelSettings";
import { NetworkSettings } from "./networkSettings";
import { ProviderSettings } from "./providerSettings";
import { ScheduleSettings } from "./scheduleSettings";
import { SearchSettings } from "./searchSettings";
import { ShortcutSettings } from "./shortcutSettings";

type AnyRecord = Record<string, any>;

type SettingsModalClient = AnyRecord & {
  copy: { value: AnyRecord };
  settingsOpen: { value: boolean };
  settingsSection: { value: string };
  settingsTitle: { value: string };
  closeSettings: () => void;
  selectSettingsSection: (section: string) => void;
};

export function SettingsModal({ client, clearWebSessions }: { client: SettingsModalClient; clearWebSessions: () => void }) {
  const copy = client.copy.value;
  const isOpen = client.settingsOpen.value;
  const section = client.settingsSection.value;
  const [renderedSection, setRenderedSection] = useState(section);
  const [contentReady, setContentReady] = useState(false);
  const [contentPending, startSettingsTransition] = useTransition();

  useEffect(() => {
    if (!isOpen) {
      setContentReady(false);
      setRenderedSection(section);
      return undefined;
    }

    let cancelled = false;
    let frameId: number | null = null;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;
    const renderContent = () => {
      if (cancelled) {
        return;
      }
      startSettingsTransition(() => {
        setRenderedSection(section);
        setContentReady(true);
      });
    };

    if (typeof window !== "undefined" && typeof window.requestAnimationFrame === "function") {
      frameId = window.requestAnimationFrame(() => {
        timeoutId = window.setTimeout(renderContent, 0);
      });
    } else {
      timeoutId = setTimeout(renderContent, 0);
    }

    return () => {
      cancelled = true;
      if (frameId !== null && typeof window !== "undefined" && typeof window.cancelAnimationFrame === "function") {
        window.cancelAnimationFrame(frameId);
      }
      if (timeoutId !== null) {
        clearTimeout(timeoutId);
      }
    };
  }, [isOpen, section, startSettingsTransition]);

  if (!isOpen) {
    return null;
  }

  const showDeferredLoading = !contentReady || contentPending || renderedSection !== section;

  return (
    <Modal
      className="settings-modal settings-modal--ant"
      open={isOpen}
      centered
      width="min(960px, calc(100vw - 36px))"
      footer={null}
      closable={false}
      onCancel={client.closeSettings}
      styles={{ body: { padding: 0 } }}
    >
      <Layout className="settings-panel settings-panel--ant" role="dialog" aria-modal="true" aria-labelledby="settingsTitle">
        <Layout.Sider width={200} className="settings-nav" theme="light">
          <SettingsNav copy={copy} section={section} selectSection={client.selectSettingsSection} />
        </Layout.Sider>
        <Layout.Content className="settings-content">
          <header className="settings-content__header">
            <Typography.Title id="settingsTitle" level={4}>
              {client.settingsTitle.value}
            </Typography.Title>
            <Button className="settings-panel__close" type="text" aria-label={copy.settings.closeAria} icon={<CloseOutlined />} onClick={client.closeSettings}>
              {copy.settings.close}
            </Button>
          </header>
          {showDeferredLoading ? (
            <section className="settings-page settings-page--loading" aria-live="polite">
              <Spin />
              <span>{copy.settings?.loading || "Loading settings..."}</span>
            </section>
          ) : renderSettingsSection(renderedSection, client, clearWebSessions, copy)}
        </Layout.Content>
      </Layout>
    </Modal>
  );
}

function renderSettingsSection(
  section: string,
  client: SettingsModalClient,
  clearWebSessions: () => void,
  copy: AnyRecord,
) {
  const pageClient = client as any;
  switch (section) {
    case "providers":
      return <ProviderSettings client={pageClient} />;
    case "models":
      return <ModelSettings client={pageClient} />;
    case "channels":
      return <ChannelSettings client={pageClient} />;
    case "mcp":
      return <McpSettings client={pageClient} />;
    case "schedule":
      return <ScheduleSettings client={pageClient} />;
    case "network":
      return <NetworkSettings client={pageClient} />;
    case "search":
      return <SearchSettings client={pageClient} />;
    case "browser":
      return <BrowserSettings client={pageClient} />;
    case "log":
      return <LogSettings client={pageClient} />;
    case "shortcuts":
      return <ShortcutSettings copy={copy} />;
    case "general":
    default:
      return <GeneralSettings client={pageClient} clearWebSessions={clearWebSessions} />;
  }
}

function SettingsNav({
  copy,
  section,
  selectSection,
}: {
  copy: AnyRecord;
  section: string;
  selectSection: (section: string) => void;
}) {
  const groups = [
    {
      label: copy.settings.web,
      items: [
        { section: "general", icon: <SettingOutlined />, title: copy.settingsTitles.general },
        { section: "shortcuts", icon: <BranchesOutlined />, title: copy.settingsTitles.shortcuts },
      ],
    },
    {
      label: copy.settings.server,
      items: [
        { section: "providers", icon: <ApiOutlined />, title: copy.settingsTitles.providers },
        { section: "models", icon: <BranchesOutlined />, title: copy.settingsTitles.models },
        { section: "channels", icon: <SendOutlined />, title: copy.settingsTitles.channels },
        { section: "mcp", icon: <ToolOutlined />, title: copy.settingsTitles.mcp },
        { section: "schedule", icon: <HistoryOutlined />, title: copy.settingsTitles.schedule },
        { section: "network", icon: <BranchesOutlined />, title: copy.settingsTitles.network },
        { section: "search", icon: <EyeOutlined />, title: copy.settingsTitles.search },
        { section: "browser", icon: <EyeOutlined />, title: copy.settingsTitles.browser },
        { section: "log", icon: <HistoryOutlined />, title: copy.settingsTitles.log },
      ],
    },
  ];

  const menuItems = groups.map((group) => ({
    key: group.label,
    label: group.label,
    type: "group" as const,
    children: group.items.map((item) => ({
      key: item.section,
      icon: <span className="settings-nav__icon" aria-hidden="true">{item.icon}</span>,
      label: item.title,
    })),
  }));

  return (
    <div className="settings-nav__inner" aria-label="Settings sections">
      <Menu
        className="settings-nav__menu"
        mode="inline"
        selectedKeys={[section]}
        items={menuItems}
        onClick={({ key }) => selectSection(String(key))}
      />
      <div className="settings-nav__footer">
        <strong>OpenSprite Web</strong>
        <span>{copy.settings.version}</span>
      </div>
    </div>
  );
}
