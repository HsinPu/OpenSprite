import { useCallback, useEffect, useRef, useState } from "react";
import { LeftOutlined, MoreOutlined, RightOutlined } from "@ant-design/icons";
import { Button, Dropdown, type MenuProps } from "antd";

import { agentChatErrorText, getConversation, isIdentifier, moveConversationToWorkspace, type ConversationSummary } from "../api/agentChat";
import { ChatWorkspace } from "../features/chat/ChatWorkspace";
import { UNASSIGNED_WORKSPACE_ID } from "../api/agentChat";
import { useConversations } from "../features/chat/useConversations";
import { modelLabel } from "../features/ai-settings/modelCatalog";
import { useAiSettings } from "../features/ai-settings/useAiSettings";
import { useProviderCatalog } from "../features/ai-settings/useProviderCatalog";
import { isTodayInTimeZone } from "../features/general-settings/dateTime";
import { useGeneralSettings } from "../features/general-settings/useGeneralSettings";
import { useConversationSettings } from "../features/conversation-settings/useConversationSettings";
import { useToolSettings } from "../features/tool-settings/useToolSettings";
import { useMcpConnections } from "../features/mcp-settings/useMcpConnections";
import { SettingsPage } from "../features/settings/SettingsPage";
import type { SettingsSection } from "../features/settings/settingsState";
import { useI18n } from "../i18n/I18nProvider";
import { useAuthentication } from "../features/auth/AuthGate";
import { useWorkspaces } from "../features/workspaces/useWorkspaces";
import { WorkspaceSwitcher, workspaceName } from "../features/workspaces/WorkspaceSwitcher";
import type { Workspace } from "../api/workspaces";

function conversationIdFromHash(): string | null {
  if (!window.location.hash.startsWith("#chat=")) return null;
  const value = window.location.hash.slice("#chat=".length);
  return isIdentifier(value) ? value : null;
}

function OpenSpriteMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <span />
    </span>
  );
}

function ConversationButton({
  conversation,
  active,
  onClick,
  workspaces,
  onMove,
}: {
  conversation: ConversationSummary;
  active: boolean;
  onClick: () => void;
  workspaces: readonly Workspace[];
  onMove: (workspaceId: string) => void;
}) {
  const { t } = useI18n();
  const targets = workspaces.filter((item) => item.id !== conversation.workspaceId);
  const items: MenuProps["items"] = conversation.workspaceManagedBySchedule
    ? [{ key: "managed", disabled: true, label: t("workspaces.moveManaged") }]
    : targets.map((item) => ({ key: item.id, label: workspaceName(item.kind, item.name, t("workspaces.unassigned")) }));
  return (
    <div className={`conversation-item${active ? " is-active" : ""}`}>
      <button className="conversation-link" type="button" onClick={onClick}>
        <span aria-hidden="true">◯</span>
        <span>{conversation.title}</span>
      </button>
      <Dropdown menu={{ items, onClick: ({ key }) => { if (key !== "managed") onMove(key); } }} trigger={["click"]} disabled={targets.length === 0 && !conversation.workspaceManagedBySchedule}>
        <button className="conversation-item__more" type="button" aria-label={t("workspaces.moveConversationLabel", { title: conversation.title })} title={conversation.workspaceManagedBySchedule ? t("workspaces.moveManaged") : t("workspaces.moveConversation")}><MoreOutlined /></button>
      </Dropdown>
    </div>
  );
}

export function App() {
  const { t } = useI18n();
  const { mode: authMode, signOut } = useAuthentication();
  const [conversationId, setConversationId] = useState<string | null>(conversationIdFromHash);
  const workspaceController = useWorkspaces();
  const activeWorkspaceId = workspaceController.catalog?.activeWorkspaceId ?? UNASSIGNED_WORKSPACE_ID;
  const {
    conversations,
    loading: conversationsLoading,
    error: conversationsError,
    refresh: refreshConversations,
    hasMore: hasMoreConversations,
    loadingMore: conversationsLoadingMore,
    loadedWorkspaceId: conversationsLoadedWorkspaceId,
    loadMore: loadMoreConversations,
    recordAcceptedConversation,
  } = useConversations(activeWorkspaceId, workspaceController.loaded && workspaceController.catalog !== null);
  const [deepLinkedConversation, setDeepLinkedConversation] = useState<ConversationSummary | null>(null);
  const [workspaceActionError, setWorkspaceActionError] = useState<string | null>(null);
  const [chatRevision, setChatRevision] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const [mobileNavigation, setMobileNavigation] = useState(
    () => window.innerWidth <= 900,
  );
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const generalSettings = useGeneralSettings();
  const conversationSettings = useConversationSettings();
  const toolSettings = useToolSettings();
  const mcpConnections = useMcpConnections();
  const providerCatalog = useProviderCatalog();
  const {
    modelSelection,
    responseMode,
    outputContinuation,
    responseDelivery,
    logFullPrompts,
    loaded: aiSettingsLoaded,
    saving: aiSettingsSaving,
    error: aiSettingsError,
    reload: reloadAiSettings,
    saveModelSelection,
    saveResponseMode,
    saveOutputContinuation,
    saveResponseDelivery,
    saveLogFullPrompts,
  } = useAiSettings(providerCatalog.providers, providerCatalog.modelChoices);
  const { modelChoices } = providerCatalog;
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [providerModalOpen, setProviderModalOpen] = useState(false);
  const [scheduleOverlayOpen, setScheduleOverlayOpen] = useState(false);
  const [workspaceOverlayOpen, setWorkspaceOverlayOpen] = useState(false);
  const [workspaceCreateRequest, setWorkspaceCreateRequest] = useState(0);
  const [settingsSection, setSettingsSection] = useState<SettingsSection>("general");
  const [mobileHeaderActionTarget, setMobileHeaderActionTarget] = useState<HTMLDivElement | null>(null);
  const mobileMenuButtonRef = useRef<HTMLButtonElement>(null);
  const newChatButtonRef = useRef<HTMLButtonElement>(null);
  const settingsButtonRef = useRef<HTMLButtonElement>(null);
  const settingsDialogRef = useRef<HTMLDialogElement>(null);
  const settingsOpenerRef = useRef<HTMLElement | null>(null);
  const appContentRef = useRef<HTMLElement>(null);
  const scheduleConversationTargetRef = useRef<string | null>(null);
  const deepLinkResolutionRef = useRef<string | null>(null);
  const menuWasOpen = useRef(false);
  const startupResolvedRef = useRef(false);
  const activeConversation = conversations.find((conversation) => conversation.id === conversationId)
    ?? (deepLinkedConversation?.id === conversationId ? deepLinkedConversation : undefined);
  const currentWorkspace = workspaceController.catalog?.workspaces.find(
    (item) => item.id === (activeConversation?.workspaceId ?? activeWorkspaceId),
  );
  const chatTitle = conversationId === null ? t("app.newConversationTitle") : activeConversation?.title ?? t("app.conversationTitle");
  const todayConversations = conversations.filter((conversation) => isTodayInTimeZone(conversation.updatedAt, generalSettings.settings.timeZone));
  const earlierConversations = conversations.filter((conversation) => !isTodayInTimeZone(conversation.updatedAt, generalSettings.settings.timeZone));

  useEffect(() => {
    if (startupResolvedRef.current
      || !workspaceController.loaded
      || workspaceController.catalog === null
      || conversationsLoadedWorkspaceId !== activeWorkspaceId
      || conversationsLoading
      || (!conversationSettings.loaded && !conversationSettings.error)) return;

    const hash = window.location.hash;
    if (hash === "#new-chat" || conversationIdFromHash() !== null) {
      startupResolvedRef.current = true;
      return;
    }

    startupResolvedRef.current = true;
    const recentConversation = conversationSettings.error === null
      && conversationSettings.settings.startupView === "recent"
      ? conversations[0]
      : undefined;
    if (recentConversation) {
      setConversationId(recentConversation.id);
      window.history.replaceState(null, "", `#chat=${recentConversation.id}`);
      return;
    }

    setConversationId(null);
    window.history.replaceState(null, "", "#new-chat");
  }, [activeWorkspaceId, conversationSettings.error, conversationSettings.loaded, conversationSettings.settings.startupView, conversations, conversationsLoadedWorkspaceId, conversationsLoading, workspaceController.catalog, workspaceController.loaded]);

  useEffect(() => {
    const syncHash = () => {
      setConversationId(conversationIdFromHash());
      setDeepLinkedConversation(null);
      setMenuOpen(false);
    };
    window.addEventListener("hashchange", syncHash);
    return () => window.removeEventListener("hashchange", syncHash);
  }, []);

  useEffect(() => {
    if (conversationId === null) {
      deepLinkResolutionRef.current = null;
      setDeepLinkedConversation(null);
      return;
    }
    const listed = conversations.find((item) => item.id === conversationId);
    if (listed) {
      setDeepLinkedConversation(listed);
      return;
    }
    if (
      !workspaceController.loaded
      || workspaceController.catalog === null
      || deepLinkResolutionRef.current === conversationId
      || (deepLinkedConversation?.id === conversationId && deepLinkedConversation.workspaceId === activeWorkspaceId)
    ) return;
    let cancelled = false;
    deepLinkResolutionRef.current = conversationId;
    void getConversation(conversationId).then(async (item) => {
      if (cancelled) return;
      setDeepLinkedConversation(item);
      setWorkspaceActionError(null);
      if (item.workspaceId !== activeWorkspaceId) {
        await workspaceController.activate(item.workspaceId);
      }
    }).catch((error) => {
      if (!cancelled) setWorkspaceActionError(agentChatErrorText(error, t));
    }).finally(() => {
      if (deepLinkResolutionRef.current === conversationId) {
        deepLinkResolutionRef.current = null;
      }
    });
    return () => { cancelled = true; };
  }, [activeWorkspaceId, conversationId, conversations, deepLinkedConversation, t, workspaceController.activate, workspaceController.catalog, workspaceController.loaded]);

  useEffect(() => {
    const updateViewport = () => {
      const mobile = window.innerWidth <= 900;
      setMobileNavigation(mobile);
      if (!mobile) setMenuOpen(false);
    };
    window.addEventListener("resize", updateViewport);
    return () => window.removeEventListener("resize", updateViewport);
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

  const activateWorkspace = async (workspaceId: string) => {
    if (workspaceId === activeWorkspaceId) {
      startNewChat();
      return;
    }
    try {
      await workspaceController.activate(workspaceId);
      setWorkspaceActionError(null);
      startNewChat();
    } catch {
      // The Workspace controller owns the localized recovery state.
    }
  };

  const moveConversation = async (
    conversation: ConversationSummary,
    workspaceId: string,
  ) => {
    try {
      const moved = await moveConversationToWorkspace(
        conversation.id,
        workspaceId,
        conversation.revision,
      );
      setWorkspaceActionError(null);
      if (conversation.id === conversationId) {
        if (workspaceId !== activeWorkspaceId) {
          await workspaceController.activate(workspaceId);
          setDeepLinkedConversation(moved);
          return;
        }
        setDeepLinkedConversation(moved);
      }
      await refreshConversations();
    } catch (error) {
      setWorkspaceActionError(agentChatErrorText(error, t));
    }
  };

  const acceptConversation = useCallback((acceptedId: string, firstMessage: string) => {
    setConversationId(acceptedId);
    window.location.hash = `chat=${acceptedId}`;
    recordAcceptedConversation(acceptedId, firstMessage);
  }, [recordAcceptedConversation]);

  const conversationUpdated = useCallback(() => {
    void refreshConversations();
  }, [refreshConversations]);

  const workspaceActivated = (workspaceId: string) => {
    void workspaceId;
    setConversationId(null);
    setDeepLinkedConversation(null);
    setWorkspaceActionError(null);
    window.location.hash = "new-chat";
  };

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
  const closeSettings = () => {
    if (!providerModalOpen && !scheduleOverlayOpen && !workspaceOverlayOpen && !hasProviderModal()) {
      setSettingsOpen(false);
    }
  };

  const openScheduleConversation = (id: string) => {
    scheduleConversationTargetRef.current = id;
    setSettingsOpen(false);
  };

  return (
    <div className={`app-shell${sidebarCollapsed ? " is-sidebar-collapsed" : ""}`}>
      <header className="mobile-header">
        <button
          ref={mobileMenuButtonRef}
          className="mobile-menu-button"
          type="button"
          aria-label={menuOpen ? t("app.closeMenu") : t("app.openMenu")}
          aria-expanded={menuOpen}
          aria-controls="main-navigation-sidebar"
          title={menuOpen ? t("app.closeMenu") : t("app.openMenu")}
          onClick={() => setMenuOpen((open) => !open)}
        >
          ☰
        </button>
        <div className="brand brand--mobile">
          <OpenSpriteMark />
          <span>OpenSprite</span>
        </div>
        <div
          ref={setMobileHeaderActionTarget}
          className="mobile-header-actions"
          aria-hidden={menuOpen ? true : undefined}
          inert={menuOpen}
        />
      </header>

      {menuOpen ? (
        <button
          className="sidebar-backdrop"
          type="button"
          aria-label={t("app.closeMenu")}
          onClick={() => setMenuOpen(false)}
        />
      ) : null}

      {!mobileNavigation ? (
        <Button
          type="default"
          className="app-shell__sidebar-toggle"
          icon={sidebarCollapsed ? <RightOutlined /> : <LeftOutlined />}
          aria-expanded={!sidebarCollapsed}
          aria-controls="main-navigation-sidebar"
          aria-label={sidebarCollapsed ? t("app.expandSidebar") : t("app.collapseSidebar")}
          title={sidebarCollapsed ? t("app.expandSidebar") : t("app.collapseSidebar")}
          onClick={() => setSidebarCollapsed((collapsed) => !collapsed)}
        />
      ) : null}

      <aside
        id="main-navigation-sidebar"
        className={`main-sidebar${menuOpen ? " is-open" : ""}${sidebarCollapsed ? " is-collapsed" : ""}`}
        aria-label={t("app.mainMenu")}
        aria-hidden={mobileNavigation && !menuOpen ? true : undefined}
        inert={mobileNavigation && !menuOpen}
      >
        <div className="sidebar-header">
          <div className="brand">
            <OpenSpriteMark />
            <span>OpenSprite</span>
          </div>
        </div>

        <WorkspaceSwitcher
          controller={workspaceController}
          collapsed={sidebarCollapsed && !mobileNavigation}
          onActivate={(workspaceId) => void activateWorkspace(workspaceId)}
          onCreate={() => { setWorkspaceCreateRequest((value) => value + 1); openSettings("workspaces"); }}
          onManage={() => openSettings("workspaces")}
        />

        <button
          ref={newChatButtonRef}
          className="new-chat-button"
          type="button"
          aria-label={t("app.newConversation")}
          title={t("app.newConversation")}
          onClick={startNewChat}
        >
          <span aria-hidden="true">＋</span>
          <span className="new-chat-label">{t("app.newConversation")}</span>
        </button>

        <nav
          id="conversation-navigation"
          className="conversation-nav"
          aria-label={t("app.conversationHistory")}
        >
          {conversationsLoading ? <p className="conversation-nav__status">{t("app.loadingConversations")}</p> : null}
          {conversationsError ? <p className="conversation-nav__status" aria-live="polite">{conversationsError}</p> : null}
          {workspaceActionError ? <p className="conversation-nav__status conversation-nav__status--error" aria-live="polite">{workspaceActionError}</p> : null}
          {!conversationsLoading && conversations.length === 0 ? <p className="conversation-nav__status">{t("app.noConversations")}</p> : null}
          {todayConversations.length > 0 ? <p className="nav-group-label">{t("app.today")}</p> : null}
          {todayConversations.map((conversation) => (
            <ConversationButton
              key={conversation.id}
              conversation={conversation}
              active={conversationId === conversation.id}
              onClick={() => openChat(conversation)}
              workspaces={workspaceController.catalog?.workspaces ?? []}
              onMove={(workspaceId) => void moveConversation(conversation, workspaceId)}
            />
          ))}

          {todayConversations.length > 0 && earlierConversations.length > 0 ? <div className="nav-divider" /> : null}
          {earlierConversations.length > 0 ? <p className="nav-group-label">{t("app.earlier")}</p> : null}
          {earlierConversations.map((conversation) => (
            <ConversationButton
              key={conversation.id}
              conversation={conversation}
              active={conversationId === conversation.id}
              onClick={() => openChat(conversation)}
              workspaces={workspaceController.catalog?.workspaces ?? []}
              onMove={(workspaceId) => void moveConversation(conversation, workspaceId)}
            />
          ))}
          {hasMoreConversations ? (
            <button
              type="button"
              className="conversation-load-more"
              disabled={conversationsLoadingMore}
              onClick={() => void loadMoreConversations()}
            >
              {conversationsLoadingMore
                ? t("app.loadingMoreConversations")
                : t("app.loadMoreConversations")}
            </button>
          ) : null}
        </nav>

        <nav className="utility-nav" aria-label={t("app.features")}>
          <button
            ref={settingsButtonRef}
            className={settingsOpen ? "is-active" : ""}
            type="button"
            aria-label={t("app.settings")}
            title={t("app.settings")}
            aria-haspopup="dialog"
            aria-expanded={settingsOpen}
            onClick={(event) => openSettings("general", event.currentTarget)}
          >
            <span aria-hidden="true">⚙</span>
            <span className="utility-label">{t("app.settings")}</span>
          </button>
          {authMode === "password_required" ? <button type="button" aria-label={t("app.logout")} title={t("app.logout")} onClick={() => void signOut()}>
            <span aria-hidden="true">↪</span>
            <span className="utility-label">{t("app.logout")}</span>
          </button> : null}
        </nav>
      </aside>

      <main
        ref={appContentRef}
        tabIndex={-1}
        className="app-content"
        aria-hidden={mobileNavigation && menuOpen ? true : undefined}
        inert={mobileNavigation && menuOpen}
      >
        <ChatWorkspace
          key={`${conversationId ?? "new"}-${chatRevision}`}
          conversationId={conversationId}
          workspaceId={activeConversation?.workspaceId ?? activeWorkspaceId}
          workspaceName={currentWorkspace ? workspaceName(currentWorkspace.kind, currentWorkspace.name, t("workspaces.unassigned")) : undefined}
          workspaceUnavailable={currentWorkspace?.availability === "unavailable"}
          title={chatTitle}
          modelName={modelLabel(modelSelection, modelChoices.filter((choice) => choice.selection.providerId === "openrouter").map((choice) => ({ id: choice.selection.modelId, label: choice.label })), t)}
          modelSelection={modelSelection}
          modelChoices={modelChoices}
          modelSelectionSaving={aiSettingsSaving}
          responseDelivery={responseDelivery}
          timeZone={generalSettings.settings.timeZone}
          sendBehavior={conversationSettings.settings.sendBehavior}
          autoScroll={conversationSettings.settings.autoScroll}
          executionPanelDefaultExpanded={conversationSettings.settings.executionPanelDefaultExpanded}
          mobileHeaderActionTarget={mobileHeaderActionTarget}
          onModelSelectionChange={saveModelSelection}
          onConversationAccepted={acceptConversation}
          onConversationUpdated={conversationUpdated}
        />
      </main>

      <dialog
        ref={settingsDialogRef}
        className={`settings-dialog settings-dialog--${settingsSection}`}
        aria-labelledby="settings-page-title"
        onClose={() => {
          setSettingsOpen(false);
          const scheduleConversationId = scheduleConversationTargetRef.current;
          scheduleConversationTargetRef.current = null;
          if (scheduleConversationId !== null) {
            setConversationId(scheduleConversationId);
            window.location.hash = `chat=${scheduleConversationId}`;
            setMenuOpen(false);
            window.requestAnimationFrame(() => appContentRef.current?.focus());
            return;
          }
          const opener = settingsOpenerRef.current;
          if (mobileNavigation && opener?.closest(".main-sidebar")) {
            setMenuOpen(true);
          }
          window.requestAnimationFrame(() => {
            if (opener?.isConnected) opener.focus();
            else settingsButtonRef.current?.focus();
          });
        }}
        onCancel={(event) => {
          if (providerModalOpen || scheduleOverlayOpen || workspaceOverlayOpen || hasProviderModal()) event.preventDefault();
        }}
        onClick={(event) => {
          if (event.target === event.currentTarget) {
            closeSettings();
          }
        }}
      >
        <SettingsPage
          section={settingsSection}
          active={settingsOpen}
          onSectionChange={setSettingsSection}
          modelSelection={modelSelection}
          responseMode={responseMode}
          outputContinuation={outputContinuation}
          responseDelivery={responseDelivery}
          logFullPrompts={logFullPrompts}
          aiSettingsLoaded={aiSettingsLoaded}
          aiSettingsSaving={aiSettingsSaving}
          aiSettingsError={aiSettingsError}
          onAiSettingsReload={reloadAiSettings}
          onModelSelectionChange={saveModelSelection}
          onResponseModeChange={saveResponseMode}
          onOutputContinuationChange={saveOutputContinuation}
          onResponseDeliveryChange={saveResponseDelivery}
          onLogFullPromptsChange={saveLogFullPrompts}
          providerCatalog={providerCatalog}
          generalSettings={generalSettings}
          conversationSettings={conversationSettings}
          toolSettings={toolSettings}
          mcpConnections={mcpConnections}
          workspaces={workspaceController}
          onWorkspaceActivated={workspaceActivated}
          workspaceCreateRequest={workspaceCreateRequest}
          onWorkspaceCreateRequestHandled={() => setWorkspaceCreateRequest(0)}
          onWorkspaceOverlayChange={setWorkspaceOverlayOpen}
          onOpenScheduleConversation={openScheduleConversation}
          onClose={closeSettings}
          onProviderModalChange={setProviderModalOpen}
          onScheduleOverlayChange={setScheduleOverlayOpen}
        />
      </dialog>
    </div>
  );
}
