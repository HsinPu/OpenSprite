import { useEffect, useRef, useState } from "react";

import { ChatWorkspace } from "../features/chat/ChatWorkspace";
import {
  defaultDemoSettings,
  SettingsPage,
  type DemoSettings,
  type SettingsSection,
} from "../features/settings/SettingsPage";

type AppView =
  | { kind: "chat"; title: string }
  | { kind: "settings"; section: SettingsSection };

function viewFromHash(): AppView {
  if (window.location.hash === "#settings-models") {
    return { kind: "settings", section: "models" };
  }

  if (window.location.hash === "#settings-general") {
    return { kind: "settings", section: "general" };
  }

  if (window.location.hash === "#new-chat") {
    return { kind: "chat", title: "新對話" };
  }

  if (window.location.hash.startsWith("#chat=")) {
    const encodedTitle = window.location.hash.slice("#chat=".length);
    try {
      return { kind: "chat", title: decodeURIComponent(encodedTitle) };
    } catch {
      return { kind: "chat", title: recentConversations[0] };
    }
  }

  return { kind: "chat", title: recentConversations[0] };
}

const recentConversations = [
  "整理今天的工作",
  "規劃下週專案時程",
  "整理會議重點",
  "產品需求優先級評估",
  "撰寫專案進度報告",
];

const olderConversations = [
  "行銷活動成效分析",
  "客戶回饋整理",
  "學習筆記：Prompt 技巧",
];

function OpenSpriteMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <span />
    </span>
  );
}

function ConversationButton({
  title,
  active,
  onClick,
}: {
  title: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      className={`conversation-link${active ? " is-active" : ""}`}
      type="button"
      onClick={onClick}
    >
      <span aria-hidden="true">◯</span>
      <span>{title}</span>
    </button>
  );
}

export function App() {
  const [view, setView] = useState<AppView>(viewFromHash);
  const [chatRevision, setChatRevision] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [settings, setSettings] = useState<DemoSettings>(defaultDemoSettings);
  const mobileMenuButtonRef = useRef<HTMLButtonElement>(null);
  const newChatButtonRef = useRef<HTMLButtonElement>(null);
  const menuWasOpen = useRef(false);

  useEffect(() => {
    const syncHash = () => {
      setView(viewFromHash());
      setMenuOpen(false);
    };
    window.addEventListener("hashchange", syncHash);
    return () => window.removeEventListener("hashchange", syncHash);
  }, []);

  useEffect(() => {
    if (menuOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }

    if (!menuWasOpen.current && menuOpen && window.innerWidth <= 900) {
      newChatButtonRef.current?.focus();
    }

    if (menuWasOpen.current && !menuOpen) {
      mobileMenuButtonRef.current?.focus();
    }
    menuWasOpen.current = menuOpen;

    return () => {
      document.body.style.overflow = "";
    };
  }, [menuOpen]);

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMenuOpen(false);
      }
    };

    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, []);

  const openChat = (title: string) => {
    setView({ kind: "chat", title });
    window.location.hash =
      title === "新對話" ? "new-chat" : `chat=${encodeURIComponent(title)}`;
    setMenuOpen(false);
  };

  const startNewChat = () => {
    setChatRevision((revision) => revision + 1);
    openChat("新對話");
  };

  const openSettings = (section: SettingsSection = "general") => {
    setView({ kind: "settings", section });
    window.location.hash = `settings-${section}`;
    setMenuOpen(false);
  };

  return (
    <div className={`app-shell${sidebarCollapsed ? " is-sidebar-collapsed" : ""}`}>
      <header className="mobile-header">
        <button
          ref={mobileMenuButtonRef}
          className="mobile-menu-button"
          type="button"
          aria-label={menuOpen ? "關閉主選單" : "開啟主選單"}
          aria-expanded={menuOpen}
          aria-controls="main-navigation-sidebar"
          title={menuOpen ? "關閉主選單" : "開啟主選單"}
          onClick={() => setMenuOpen((open) => !open)}
        >
          ☰
        </button>
        <div className="brand brand--mobile">
          <OpenSpriteMark />
          <span>OpenSprite</span>
        </div>
      </header>

      {menuOpen ? (
        <button
          className="sidebar-backdrop"
          type="button"
          aria-label="關閉主選單"
          onClick={() => setMenuOpen(false)}
        />
      ) : null}

      <aside
        id="main-navigation-sidebar"
        className={`main-sidebar${menuOpen ? " is-open" : ""}${sidebarCollapsed ? " is-collapsed" : ""}`}
        aria-label="主選單"
      >
        <div className="sidebar-header">
          <div className="brand">
            <OpenSpriteMark />
            <span>OpenSprite</span>
          </div>
          <button
            className="sidebar-collapse-button"
            type="button"
            aria-label={sidebarCollapsed ? "展開側邊欄" : "收合側邊欄"}
            aria-expanded={!sidebarCollapsed}
            aria-controls="conversation-navigation"
            title={sidebarCollapsed ? "展開側邊欄" : "收合側邊欄"}
            onClick={() => setSidebarCollapsed((collapsed) => !collapsed)}
          >
            <span
              className={`sidebar-chevron ${sidebarCollapsed ? "is-right" : "is-left"}`}
              aria-hidden="true"
            />
          </button>
        </div>

        <button
          ref={newChatButtonRef}
          className="new-chat-button"
          type="button"
          aria-label="新對話"
          title="新對話"
          onClick={startNewChat}
        >
          <span aria-hidden="true">＋</span>
          <span className="new-chat-label">新對話</span>
        </button>

        <nav
          id="conversation-navigation"
          className="conversation-nav"
          aria-label="對話紀錄"
        >
          <p className="nav-group-label">今天</p>
          {recentConversations.map((title) => (
            <ConversationButton
              key={title}
              title={title}
              active={view.kind === "chat" && view.title === title}
              onClick={() => openChat(title)}
            />
          ))}

          <div className="nav-divider" />
          <p className="nav-group-label">昨天</p>
          {olderConversations.map((title) => (
            <ConversationButton
              key={title}
              title={title}
              active={view.kind === "chat" && view.title === title}
              onClick={() => openChat(title)}
            />
          ))}
        </nav>

        <nav className="utility-nav" aria-label="應用程式功能">
          <button
            type="button"
            disabled
            aria-label="工具與連線"
            title="此功能將在後續 Demo 加入"
          >
            <span aria-hidden="true">⌘</span>
            <span className="utility-label">工具與連線</span>
          </button>
          <button
            className={view.kind === "settings" ? "is-active" : ""}
            type="button"
            aria-label="設定"
            title="設定"
            onClick={() => openSettings()}
          >
            <span aria-hidden="true">⚙</span>
            <span className="utility-label">設定</span>
          </button>
        </nav>
      </aside>

      <main className="app-content">
        {view.kind === "chat" ? (
          <ChatWorkspace
            key={`${view.title}-${chatRevision}`}
            title={view.title}
            initiallyEmpty={view.title === "新對話"}
            modelName={settings.defaultModel.replace("OpenAI · ", "")}
          />
        ) : (
          <SettingsPage
            section={view.section}
            onSectionChange={(section) => openSettings(section)}
            settings={settings}
            onSettingsChange={setSettings}
          />
        )}
      </main>
    </div>
  );
}
