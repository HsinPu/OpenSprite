import { useEffect, useState } from "react";

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
  const [settings, setSettings] = useState<DemoSettings>(defaultDemoSettings);

  useEffect(() => {
    const syncHash = () => setView(viewFromHash());
    window.addEventListener("hashchange", syncHash);
    return () => window.removeEventListener("hashchange", syncHash);
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
    <div className="app-shell">
      <header className="mobile-header">
        <button
          className="mobile-menu-button"
          type="button"
          aria-label="開啟主選單"
          aria-expanded={menuOpen}
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

      <aside className={`main-sidebar${menuOpen ? " is-open" : ""}`}>
        <div className="brand">
          <OpenSpriteMark />
          <span>OpenSprite</span>
        </div>

        <button className="new-chat-button" type="button" onClick={startNewChat}>
          <span aria-hidden="true">＋</span>
          新對話
        </button>

        <nav className="conversation-nav" aria-label="對話紀錄">
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
            title="此功能將在後續 Demo 加入"
          >
            <span aria-hidden="true">⌘</span>
            工具與連線
          </button>
          <button
            className={view.kind === "settings" ? "is-active" : ""}
            type="button"
            onClick={() => openSettings()}
          >
            <span aria-hidden="true">⚙</span>
            設定
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
