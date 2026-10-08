import { useState } from "react";
import { createRoot } from "react-dom/client";
import { ConfigProvider } from "antd";
import { ChatWorkspace } from "../../src/features/chat/ChatWorkspace";
import { I18nProvider } from "../../src/i18n/I18nProvider";
import "../../src/app/app.css";

function Fixture() {
  const [target, setTarget] = useState<HTMLDivElement | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [changed, setChanged] = useState(false);
  return <ConfigProvider theme={{ token: { colorPrimary: "#ff6545", borderRadius: 12 } }}>
    <div className={`app-shell${collapsed ? " is-sidebar-collapsed" : ""}`}>
      <header className="mobile-header"><span>OpenSprite · isolated</span><div ref={setTarget} className="mobile-header-actions"/></header>
      <aside className="main-sidebar"><h2>OpenSprite</h2><button onClick={() => setCollapsed(!collapsed)}>切換側欄</button><button onClick={() => setChanged(!changed)}>模擬設定模型變更</button></aside>
      <main className="app-content">
        <ChatWorkspace conversationId={null} modelName={changed ? "Changed model" : "Original model"}
          modelSelection={{ providerId: "openrouter", modelId: changed ? "test/changed" : "test/original", contextBudget: "auto", outputBudget: "auto" }}
          modelChoices={[{ label: "Original model", selection: { providerId: "openrouter", modelId: "test/original", contextBudget: "auto", outputBudget: "auto" } }]}
          modelSelectionSaving={false} timeZone="system" sendBehavior="enter" autoScroll executionPanelDefaultExpanded
          mobileHeaderActionTarget={target} onConversationAccepted={() => undefined} onConversationUpdated={() => undefined} title="隔離測試對話"/>
      </main>
    </div>
  </ConfigProvider>;
}
createRoot(document.getElementById("root")!).render(<I18nProvider><Fixture/></I18nProvider>);
