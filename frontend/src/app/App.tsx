import { useCallback, useEffect, useRef, useState } from "react";

import { agentChatErrorText, isIdentifier, listConversations, type ConversationSummary } from "../api/agentChat";
import { aiSettingsErrorText, getAiSettings, putAiSettings, type AiSettings, type ResponseMode } from "../api/aiSettings";
import { listProviderConnections, type ProviderSummary } from "../api/providerConnections";
import { ChatWorkspace } from "../features/chat/ChatWorkspace";
import {
  defaultDemoSettings,
  SettingsPage,
  type DemoSettings,
  type SettingsSection,
} from "../features/settings/SettingsPage";
import { localModelCatalog, modelLabel, type ModelSelection } from "../features/settings/modelCatalog";

type ModelChoice = { selection: ModelSelection; label: string };

function staticModelChoices(providers: ReadonlyArray<ProviderSummary>): ReadonlyArray<ModelChoice> {
  return providers.flatMap((provider) => provider.connected
    ? localModelCatalog[provider.id].map((model) => ({
      selection: { providerId: provider.id, modelId: model.id },
      label: model.label,
    }))
    : []);
}

function conversationIdFromHash(): string | null {
  if (!window.location.hash.startsWith("#chat=")) return null;
  const value = window.location.hash.slice("#chat=".length);
  return isIdentifier(value) ? value : null;
}

function isToday(timestamp: string): boolean {
  const value = new Date(timestamp);
  const now = new Date();
  return value.getFullYear() === now.getFullYear() && value.getMonth() === now.getMonth() && value.getDate() === now.getDate();
}

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
  const [conversationId, setConversationId] = useState<string | null>(conversationIdFromHash);
  const [conversations, setConversations] = useState<ReadonlyArray<ConversationSummary>>([]);
  const [conversationsLoading, setConversationsLoading] = useState(true);
  const [conversationsError, setConversationsError] = useState<string | null>(null);
  const [chatRevision, setChatRevision] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [settings, setSettings] = useState<DemoSettings>(defaultDemoSettings);
  const [modelSelection, setModelSelection] = useState<ModelSelection | null>(null);
  const [responseMode, setResponseMode] = useState<ResponseMode>("default");
  const [aiSettingsLoaded, setAiSettingsLoaded] = useState(false);
  const [aiSettingsSaving, setAiSettingsSaving] = useState(false);
  const [aiSettingsError, setAiSettingsError] = useState<string | null>(null);
  const [modelChoices, setModelChoices] = useState<ReadonlyArray<ModelChoice>>([]);
  const [providerCatalog, setProviderCatalog] = useState<ReadonlyArray<ProviderSummary> | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [providerModalOpen, setProviderModalOpen] = useState(false);
  const [settingsSection, setSettingsSection] = useState<SettingsSection>("general");
  const mobileMenuButtonRef = useRef<HTMLButtonElement>(null);
  const newChatButtonRef = useRef<HTMLButtonElement>(null);
  const settingsButtonRef = useRef<HTMLButtonElement>(null);
  const settingsDialogRef = useRef<HTMLDialogElement>(null);
  const settingsOpenerRef = useRef<HTMLElement | null>(null);
  const menuWasOpen = useRef(false);
  const modelLoadGenerationRef = useRef(0);
  const modelSaveGenerationRef = useRef(0);
  const modelSaveQueueRef = useRef(Promise.resolve());
  const activeConversation = conversations.find((conversation) => conversation.id === conversationId);
  const chatTitle = conversationId === null ? "新對話" : activeConversation?.title ?? "對話";
  const todayConversations = conversations.filter((conversation) => isToday(conversation.updatedAt));
  const earlierConversations = conversations.filter((conversation) => !isToday(conversation.updatedAt));

  const refreshConversations = useCallback(async () => {
    setConversationsLoading(true);
    try {
      const page = await listConversations();
      setConversations(page.conversations);
      setConversationsError(null);
    } catch (error) {
      setConversationsError(agentChatErrorText(error));
    } finally {
      setConversationsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshConversations();
  }, [refreshConversations]);

  useEffect(() => {
    const generation = modelLoadGenerationRef.current + 1;
    modelLoadGenerationRef.current = generation;
    void getAiSettings()
      .then((savedSettings) => {
        if (modelLoadGenerationRef.current !== generation) return;
        setModelSelection(savedSettings.model);
        setResponseMode(savedSettings.responseMode);
        setAiSettingsLoaded(true);
        setAiSettingsError(null);
      })
      .catch((error: unknown) => {
        if (modelLoadGenerationRef.current !== generation) return;
        setAiSettingsLoaded(false);
        setAiSettingsError(aiSettingsErrorText(error));
      });

    void listProviderConnections()
      .then((providers) => {
        setProviderCatalog(providers);
        setModelChoices(staticModelChoices(providers));
      })
      .catch(() => {
        setProviderCatalog(null);
        setModelChoices([]);
      });
  }, []);

  const saveAiSettings = useCallback((next: AiSettings): Promise<string | null> => {
    modelLoadGenerationRef.current += 1;
    const generation = modelSaveGenerationRef.current + 1;
    modelSaveGenerationRef.current = generation;
    setAiSettingsSaving(true);
    setAiSettingsError(null);
    const operation = modelSaveQueueRef.current.then(async () => {
      try {
        const saved = await putAiSettings(next);
        if ((saved.model?.providerId ?? null) !== (next.model?.providerId ?? null) || (saved.model?.modelId ?? null) !== (next.model?.modelId ?? null) || saved.responseMode !== next.responseMode) {
          throw new Error("ai_settings_response_mismatch");
        }
        if (modelSaveGenerationRef.current === generation) {
          setModelSelection(saved.model);
          setResponseMode(saved.responseMode);
          setAiSettingsError(null);
        }
        return null;
      } catch (error) {
        const message = aiSettingsErrorText(error);
        if (modelSaveGenerationRef.current === generation) setAiSettingsError(message);
        return message;
      } finally {
        if (modelSaveGenerationRef.current === generation) setAiSettingsSaving(false);
      }
    });
    modelSaveQueueRef.current = operation.then(() => undefined, () => undefined);
    return operation;
  }, []);

  const saveModelSelection = useCallback(
    (next: ModelSelection | null) => saveAiSettings({ model: next, responseMode }),
    [responseMode, saveAiSettings],
  );
  const saveResponseMode = useCallback(
    (next: ResponseMode) => saveAiSettings({ model: modelSelection, responseMode: next }),
    [modelSelection, saveAiSettings],
  );

  useEffect(() => {
    if (!aiSettingsLoaded || providerCatalog === null || aiSettingsSaving) return;
    const connectedProviders = providerCatalog.filter((provider) => provider.connected);
    if (modelSelection?.providerId === "openrouter") return;
    const selectionIsAvailable = modelSelection !== null && modelChoices.some((choice) => choice.selection.providerId === modelSelection.providerId && choice.selection.modelId === modelSelection.modelId);
    if (selectionIsAvailable) return;
    const fallback = modelChoices[0];
    if (fallback) {
      void saveModelSelection(fallback.selection);
    } else if (modelSelection !== null && connectedProviders.length === 0) {
      void saveModelSelection(null);
    }
  }, [aiSettingsLoaded, aiSettingsSaving, modelChoices, modelSelection, providerCatalog, saveModelSelection]);

  useEffect(() => {
    const syncHash = () => {
      setConversationId(conversationIdFromHash());
      setMenuOpen(false);
    };
    window.addEventListener("hashchange", syncHash);
    return () => window.removeEventListener("hashchange", syncHash);
  }, []);

  useEffect(() => {
    const dialog = settingsDialogRef.current;
    if (!dialog) return;

    if (settingsOpen && !dialog.open) {
      dialog.showModal();
    }

    if (!settingsOpen && dialog.open) {
      dialog.close();
    }
  }, [settingsOpen]);

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

  const openChat = (conversation: ConversationSummary) => {
    setConversationId(conversation.id);
    window.location.hash = `chat=${conversation.id}`;
    setMenuOpen(false);
  };

  const startNewChat = () => {
    setChatRevision((revision) => revision + 1);
    setConversationId(null);
    window.location.hash = "new-chat";
    setMenuOpen(false);
  };

  const acceptConversation = useCallback((acceptedId: string, firstMessage: string) => {
    setConversationId(acceptedId);
    window.location.hash = `chat=${acceptedId}`;
    const now = new Date().toISOString();
    setConversations((current) => current.some((conversation) => conversation.id === acceptedId) ? current : [{
      id: acceptedId,
      title: firstMessage.slice(0, 160),
      latestMessagePreview: firstMessage.slice(0, 280),
      createdAt: now,
      updatedAt: now,
    }, ...current]);
    void refreshConversations();
  }, [refreshConversations]);

  const conversationUpdated = useCallback(() => {
    void refreshConversations();
  }, [refreshConversations]);

  const openSettings = (section: SettingsSection = "general", opener?: HTMLElement) => {
    const activeElement = opener ?? document.activeElement;
    settingsOpenerRef.current = activeElement instanceof HTMLElement
      ? activeElement
      : settingsButtonRef.current;
    setSettingsSection(section);
    setSettingsOpen(true);
    setMenuOpen(false);
  };

  const hasProviderModal = () => document.querySelector(".provider-connection-modal") !== null;
  const closeSettings = () => { if (!providerModalOpen && !hasProviderModal()) setSettingsOpen(false); };

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
          {conversationsLoading ? <p className="conversation-nav__status">正在讀取對話…</p> : null}
          {conversationsError ? <p className="conversation-nav__status" aria-live="polite">{conversationsError}</p> : null}
          {!conversationsLoading && conversations.length === 0 ? <p className="conversation-nav__status">還沒有對話。</p> : null}
          {todayConversations.length > 0 ? <p className="nav-group-label">今天</p> : null}
          {todayConversations.map((conversation) => (
            <ConversationButton
              key={conversation.id}
              title={conversation.title}
              active={conversationId === conversation.id}
              onClick={() => openChat(conversation)}
            />
          ))}

          {todayConversations.length > 0 && earlierConversations.length > 0 ? <div className="nav-divider" /> : null}
          {earlierConversations.length > 0 ? <p className="nav-group-label">較早</p> : null}
          {earlierConversations.map((conversation) => (
            <ConversationButton
              key={conversation.id}
              title={conversation.title}
              active={conversationId === conversation.id}
              onClick={() => openChat(conversation)}
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
            ref={settingsButtonRef}
            className={settingsOpen ? "is-active" : ""}
            type="button"
            aria-label="設定"
            title="設定"
            aria-haspopup="dialog"
            aria-expanded={settingsOpen}
            onClick={(event) => openSettings("general", event.currentTarget)}
          >
            <span aria-hidden="true">⚙</span>
            <span className="utility-label">設定</span>
          </button>
        </nav>
      </aside>

      <main className="app-content">
        <ChatWorkspace
          key={`${conversationId ?? "new"}-${chatRevision}`}
          conversationId={conversationId}
          title={chatTitle}
          modelName={modelLabel(modelSelection, modelChoices.filter((choice) => choice.selection.providerId === "openrouter").map((choice) => ({ id: choice.selection.modelId, label: choice.label })))}
          modelSelection={modelSelection}
          modelChoices={modelChoices}
          modelSelectionSaving={aiSettingsSaving}
          onModelSelectionChange={saveModelSelection}
          onConversationAccepted={acceptConversation}
          onConversationUpdated={conversationUpdated}
        />
      </main>

      <dialog
        ref={settingsDialogRef}
        className="settings-dialog"
        aria-labelledby="settings-page-title"
        onClose={() => {
          setSettingsOpen(false);
          window.requestAnimationFrame(() => {
            const opener = settingsOpenerRef.current;
            if (opener?.isConnected) opener.focus();
            else settingsButtonRef.current?.focus();
          });
        }}
        onCancel={(event) => {
          if (providerModalOpen || hasProviderModal()) event.preventDefault();
        }}
        onClick={(event) => {
          if (event.target === event.currentTarget) {
            closeSettings();
          }
        }}
      >
        <SettingsPage
          section={settingsSection}
          onSectionChange={setSettingsSection}
          settings={settings}
          onSettingsChange={setSettings}
          modelSelection={modelSelection}
          responseMode={responseMode}
          aiSettingsSaving={aiSettingsSaving}
          aiSettingsError={aiSettingsError}
          onModelSelectionChange={saveModelSelection}
          onResponseModeChange={saveResponseMode}
          onModelChoicesChange={setModelChoices}
          onClose={closeSettings}
          onProviderModalChange={setProviderModalOpen}
        />
      </dialog>
    </div>
  );
}
