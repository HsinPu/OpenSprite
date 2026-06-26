import React, { CSSProperties, useEffect, useMemo, useState, useTransition } from "react";
import {
  Alert,
  App as AntdApp,
  Button,
  Card,
  Checkbox,
  ConfigProvider,
  Form,
  Input,
  InputNumber,
  Layout,
  Menu,
  Modal,
  Segmented,
  Space,
  Spin,
  Switch,
  Tag,
  Typography,
  theme,
} from "antd";
import {
  ApiOutlined,
  BranchesOutlined,
  CloseOutlined,
  EyeOutlined,
  HistoryOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  PlusOutlined,
  SendOutlined,
  SettingOutlined,
  StopOutlined,
  ToolOutlined,
} from "@ant-design/icons";
import { useReactiveStore } from "./lib/reactiveCompat";
import { useChatClient } from "./composables/useChatClient";
import { noticeTone, runStatusColor } from "./components/displayHelpers";
import { artifactStatusLabel, artifactTypeLabel, normalizeMessages } from "./components/messageData";
import { MessageTextRenderer } from "./components/messageMarkdown";
import { RunInspector } from "./components/runInspector";
import { ToastStack } from "./components/toastStack";
import { BrowserSettings } from "./settings/browserSettings";
import { ChannelSettings } from "./settings/channelSettings";
import { GeneralSettings } from "./settings/generalSettings";
import { LogSettings } from "./settings/logSettings";
import { McpSettings } from "./settings/mcpSettings";
import { ModelSettings } from "./settings/modelSettings";
import { NetworkSettings } from "./settings/networkSettings";
import { ProviderSettings } from "./settings/providerSettings";
import { ScheduleSettings } from "./settings/scheduleSettings";
import { SearchSettings } from "./settings/searchSettings";
import { SettingsCard, SettingsRow } from "./settings/settingsPrimitives";

type AnyRecord = Record<string, any>;
type Client = ReturnType<typeof useChatClient>;

const TRACE_WIDTH_STORAGE_KEY = "opensprite:web:traceInspectorWidth";
const SIDEBAR_WIDTH_STORAGE_KEY = "opensprite:web:sidebarWidth";
const SIDEBAR_WIDTH_DEFAULT = 268;
const SIDEBAR_WIDTH_MIN = 220;
const SIDEBAR_WIDTH_MAX = 440;
const SIDEBAR_COLLAPSED_WIDTH = 52;
const TRACE_WIDTH_MIN = 440;
const TRACE_CHAT_MIN = 520;

export default function App() {
  return (
    <ConfigProvider
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          borderRadius: 8,
          colorPrimary: "#2563eb",
          fontFamily:
            "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif",
        },
      }}
    >
      <AntdApp>
        <OpenSpriteShell />
      </AntdApp>
    </ConfigProvider>
  );
}

function OpenSpriteShell() {
  const client = useReactiveStore(useChatClient);
  const copy = client.copy.value;
  const [sidebarWidth, setSidebarWidth] = useState(readStoredSidebarWidth);
  const [traceInspectorWidth, setTraceInspectorWidth] = useState(readStoredTraceWidth);
  const [confirmDialog, setConfirmDialog] = useState<AnyRecord>({
    open: false,
    eyebrow: "",
    title: "",
    message: "",
    detail: "",
    cancelLabel: "",
    confirmLabel: "",
    busy: false,
    action: null,
  });

  const appShellStyle = {
    "--sidebar-width": sidebarWidth ? `${sidebarWidth}px` : undefined,
    "--trace-sidebar-width": traceInspectorWidth ? `${traceInspectorWidth}px` : undefined,
  } as CSSProperties;

  function viewTraceForRun(runId: string) {
    client.selectRun(runId);
    if (client.traceInspectorCollapsed.value) {
      client.toggleTraceInspectorCollapsed();
    }
  }

  function closeConfirmDialog() {
    setConfirmDialog({
      open: false,
      eyebrow: "",
      title: "",
      message: "",
      detail: "",
      cancelLabel: "",
      confirmLabel: "",
      busy: false,
      action: null,
    });
  }

  async function confirmDialogAction() {
    if (typeof confirmDialog.action !== "function" || confirmDialog.busy) {
      return;
    }
    setConfirmDialog((dialog) => ({ ...dialog, busy: true }));
    try {
      await confirmDialog.action();
    } finally {
      closeConfirmDialog();
    }
  }

  function deleteSessions(sessions: AnyRecord[]) {
    const targets = Array.isArray(sessions) ? sessions.filter(Boolean) : [];
    if (!targets.length) {
      return;
    }
    setConfirmDialog({
      open: true,
      eyebrow: copy.sidebar.deleteChat,
      title: copy.sidebar.confirmDeleteTitle,
      message:
        targets.length === 1
          ? copy.sidebar.confirmDeleteChat(client.getSessionTitle(targets[0]))
          : copy.sidebar.confirmDeleteChats(targets.length),
      detail: copy.sidebar.confirmDeleteDetail,
      cancelLabel: copy.sidebar.cancelDelete,
      confirmLabel: copy.sidebar.confirmDeleteAction,
      busy: false,
      action: () => client.deleteSessions(targets),
    });
  }

  function clearWebSessions() {
    setConfirmDialog({
      open: true,
      eyebrow: copy.settings.general.clearWebChats.action,
      title: copy.settings.general.clearWebChats.confirmTitle,
      message: copy.settings.general.clearWebChats.confirm,
      detail: copy.settings.general.clearWebChats.confirmDescription(client.webSessionCount.value || 0),
      cancelLabel: copy.sidebar.cancelDelete,
      confirmLabel: copy.settings.general.clearWebChats.confirmAction,
      busy: false,
      action: () => client.clearWebSessions(),
    });
  }

  function currentSidebarGutter() {
    return client.sidebarCollapsed.value ? SIDEBAR_COLLAPSED_WIDTH : sidebarWidth || SIDEBAR_WIDTH_DEFAULT;
  }

  function clampSidebarWidth(width: number) {
    const viewportWidth = window.innerWidth || 0;
    const maxFromViewport = viewportWidth
      ? Math.max(
          SIDEBAR_WIDTH_MIN,
          viewportWidth - TRACE_CHAT_MIN - (client.traceInspectorCollapsed.value ? 0 : TRACE_WIDTH_MIN),
        )
      : SIDEBAR_WIDTH_MAX;
    const maxWidth = Math.min(SIDEBAR_WIDTH_MAX, maxFromViewport);
    return Math.round(Math.min(Math.max(width, SIDEBAR_WIDTH_MIN), maxWidth));
  }

  function clampTraceWidth(width: number) {
    const viewportWidth = window.innerWidth || 0;
    const fallbackMax = Math.max(TRACE_WIDTH_MIN, Math.round(viewportWidth * 0.78));
    const maxWidth = viewportWidth ? Math.max(TRACE_WIDTH_MIN, viewportWidth - currentSidebarGutter() - TRACE_CHAT_MIN) : fallbackMax;
    return Math.round(Math.min(Math.max(width, TRACE_WIDTH_MIN), maxWidth));
  }

  function beginSidebarResize(event: React.PointerEvent) {
    if (client.sidebarCollapsed.value || event.button !== 0) {
      return;
    }
    event.preventDefault();
    event.currentTarget.setPointerCapture?.(event.pointerId);
    const handlePointerMove = (moveEvent: PointerEvent) => {
      setSidebarWidth(clampSidebarWidth(moveEvent.clientX));
      if (!client.traceInspectorCollapsed.value && traceInspectorWidth) {
        setTraceInspectorWidth(clampTraceWidth(traceInspectorWidth));
      }
    };
    const stopResize = () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", stopResize);
      window.removeEventListener("pointercancel", stopResize);
      try {
        window.localStorage.setItem(SIDEBAR_WIDTH_STORAGE_KEY, String(sidebarWidth));
        if (traceInspectorWidth) {
          window.localStorage.setItem(TRACE_WIDTH_STORAGE_KEY, String(traceInspectorWidth));
        }
      } catch {
        // Keep resize functional even when storage is unavailable.
      }
    };
    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", stopResize, { once: true });
    window.addEventListener("pointercancel", stopResize, { once: true });
  }

  function beginTraceResize(event: React.PointerEvent) {
    if (client.traceInspectorCollapsed.value || event.button !== 0) {
      return;
    }
    event.preventDefault();
    event.currentTarget.setPointerCapture?.(event.pointerId);
    const handlePointerMove = (moveEvent: PointerEvent) => {
      setTraceInspectorWidth(clampTraceWidth(window.innerWidth - moveEvent.clientX));
    };
    const stopResize = () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", stopResize);
      window.removeEventListener("pointercancel", stopResize);
      try {
        window.localStorage.setItem(TRACE_WIDTH_STORAGE_KEY, String(traceInspectorWidth));
      } catch {
        // Keep resize functional even when storage is unavailable.
      }
    };
    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", stopResize, { once: true });
    window.addEventListener("pointercancel", stopResize, { once: true });
  }

  return (
    <>
      <div
        className={[
          "app-shell",
          client.sidebarCollapsed.value ? "app-shell--sidebar-collapsed" : "",
          client.traceInspectorCollapsed.value ? "app-shell--trace-collapsed" : "",
        ]
          .filter(Boolean)
          .join(" ")}
        style={appShellStyle}
      >
        <Button
          className="mobile-nav-toggle"
          aria-controls="sidebar"
          aria-expanded={client.sidebarOpen.value}
          icon={client.sidebarOpen.value ? <CloseOutlined /> : <MenuUnfoldOutlined />}
          onClick={client.toggleSidebar}
        >
          {client.sidebarOpen.value ? copy.timeline.collapse : copy.app.menu}
        </Button>
        {client.sidebarOpen.value ? (
          <Button className="mobile-nav-backdrop" type="text" aria-label="Close menu" onClick={client.toggleSidebar} />
        ) : null}

        <SidebarNav
          client={client}
          beginSidebarResize={beginSidebarResize}
          deleteSessions={deleteSessions}
        />

        <ChatPanel client={client} viewTraceForRun={viewTraceForRun} />

        <aside className="trace-sidebar" data-collapsed={client.traceInspectorCollapsed.value} aria-label="Run trace inspector">
          {!client.traceInspectorCollapsed.value ? (
            <>
              <Button
                className="trace-sidebar__resize"
                type="text"
                aria-label="Resize trace inspector"
                title="Drag to resize trace inspector"
                onPointerDown={beginTraceResize}
              />
              <div className="trace-sidebar__rail">
                <Button
                  className="trace-sidebar__toggle"
                  aria-expanded={!client.traceInspectorCollapsed.value}
                  aria-label="Close trace panel"
                  title="Close trace panel"
                  icon={<CloseOutlined />}
                  onClick={client.toggleTraceInspectorCollapsed}
                >
                  {copy.trace.collapse}
                </Button>
              </div>
              <RunInspector client={client} />
            </>
          ) : null}
        </aside>
      </div>

      <AuthGate client={client} />
      <SettingsModal client={client} clearWebSessions={clearWebSessions} />
      <Modal
        open={confirmDialog.open}
        title={confirmDialog.title}
        okText={confirmDialog.confirmLabel}
        cancelText={confirmDialog.cancelLabel}
        okButtonProps={{ danger: true, loading: confirmDialog.busy }}
        cancelButtonProps={{ disabled: confirmDialog.busy }}
        onOk={confirmDialogAction}
        onCancel={confirmDialog.busy ? undefined : closeConfirmDialog}
      >
        <Typography.Text type="secondary">{confirmDialog.eyebrow}</Typography.Text>
        <Typography.Paragraph>{confirmDialog.message}</Typography.Paragraph>
        {confirmDialog.detail ? <Alert type="warning" showIcon message={confirmDialog.detail} /> : null}
      </Modal>
      <ToastStack client={client} />
    </>
  );
}

function SidebarNav({
  client,
  beginSidebarResize,
  deleteSessions,
}: {
  client: Client;
  beginSidebarResize: (event: React.PointerEvent) => void;
  deleteSessions: (sessions: AnyRecord[]) => void;
}) {
  const copy = client.copy.value;
  const [deleteMode, setDeleteMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const sessions = client.sidebarSessions.value || [];
  const selectedSessions = sessions.filter((session: AnyRecord) => selectedIds.includes(sessionSelectionKey(session)));

  function sessionSelectionKey(session: AnyRecord) {
    return String(session?.sessionId || session?.externalChatId || "");
  }

  function toggleSelected(session: AnyRecord, checked: boolean) {
    const key = sessionSelectionKey(session);
    if (!key) {
      return;
    }
    setSelectedIds((current) => {
      if (checked) {
        return current.includes(key) ? current : [...current, key];
      }
      return current.filter((id) => id !== key);
    });
  }

  function beginDeleteMode() {
    if (!sessions.length) {
      return;
    }
    setSelectedIds([]);
    setDeleteMode(true);
  }

  function cancelDeleteMode() {
    setSelectedIds([]);
    setDeleteMode(false);
  }

  function deleteSelectedSessions() {
    if (!selectedSessions.length) {
      return;
    }
    deleteSessions(selectedSessions);
    cancelDeleteMode();
  }

  return (
    <aside id="sidebar" className="sidebar" aria-label={copy.sidebar.ariaLabel}>
      <div className="sidebar__top">
        <div className="brand-row">
          <Button
            className="brand-mark brand-mark--button"
            type="text"
            aria-label={client.sidebarCollapsed.value ? copy.sidebar.expand : "OpenSprite"}
            title={client.sidebarCollapsed.value ? copy.sidebar.expand : "OpenSprite"}
            disabled={!client.sidebarCollapsed.value}
            onClick={() => {
              if (client.sidebarCollapsed.value) {
                client.toggleSidebarCollapsed();
              }
            }}
          >
            <span className="brand-mark__initial" aria-hidden="true">OS</span>
            <span className="brand-mark__expand" aria-hidden="true" />
          </Button>
          <div className="brand-row__copy">
            <strong>OpenSprite</strong>
            <span>{copy.sidebar.brandSubtitle}</span>
          </div>
          <Button
            className="sidebar-collapse-button"
            type="text"
            aria-label={client.sidebarCollapsed.value ? copy.sidebar.expand : copy.sidebar.collapse}
            title={client.sidebarCollapsed.value ? copy.sidebar.expand : copy.sidebar.collapse}
            aria-pressed={client.sidebarCollapsed.value}
            icon={client.sidebarCollapsed.value ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={client.toggleSidebarCollapsed}
          />
        </div>

        <Button
          className="new-chat-button"
          type="primary"
          title={copy.sidebar.newChat}
          icon={<PlusOutlined />}
          onClick={client.createNewChat}
        >
          <span className="new-chat-button__label">{copy.sidebar.newChat}</span>
        </Button>

        <section className="sidebar__section">
          <div className="sidebar__section-head">
            <span>{copy.sidebar.chats}</span>
            <span className="sidebar__section-meta">
              <small>{sessions.length}/{client.sidebarSessionTotal.value}</small>
              <span className="sidebar__section-actions">
                {!deleteMode ? (
                  <Button
                    className="sidebar__manage-button"
                    type="text"
                    size="small"
                    disabled={!sessions.length}
                    title={copy.sidebar.deleteChat}
                    onClick={beginDeleteMode}
                  >
                    {copy.sidebar.deleteChat}
                  </Button>
                ) : (
                  <>
                    <Button className="sidebar__manage-button" type="text" size="small" onClick={cancelDeleteMode}>
                      {copy.sidebar.cancelDelete}
                    </Button>
                    <Button
                      className="sidebar__manage-button sidebar__manage-button--danger"
                      type="text"
                      size="small"
                      danger
                      disabled={!selectedSessions.length}
                      onClick={deleteSelectedSessions}
                    >
                      {copy.sidebar.deleteSelectedChats(selectedSessions.length)}
                    </Button>
                  </>
                )}
              </span>
            </span>
          </div>

          <Segmented
            className="session-filter"
            aria-label={copy.sidebar.chats}
            value={client.sessionChannelFilter.value}
            options={[
              { value: "all", label: copy.sidebar.filters.all },
              { value: "web", label: copy.sidebar.filters.web },
            ]}
            onChange={(value) => client.setSessionChannelFilter(String(value))}
          />

          <label className="session-history-toggle" title={copy.sidebar.showHiddenSessionsTitle}>
            <Switch
              size="small"
              checked={client.showHiddenSessions.value}
              onChange={(checked) => client.setShowHiddenSessions(checked)}
            />
            <strong>{copy.sidebar.showHiddenSessions}</strong>
          </label>

          <div className="session-list">
            {sessions.map((session: AnyRecord) => {
              const key = sessionSelectionKey(session);
              const active = session.externalChatId === client.state.activeExternalChatId;
              return (
                <div
                  key={key || session.externalChatId}
                  className={[
                    "session-tile-wrap",
                    active ? "session-tile--active" : "",
                    deleteMode ? "session-tile-wrap--selecting" : "",
                  ].filter(Boolean).join(" ")}
                >
                  {deleteMode ? (
                    <Checkbox
                      className="session-tile__select"
                      aria-label={copy.sidebar.selectChat(client.getSessionTitle(session))}
                      checked={selectedIds.includes(key)}
                      onClick={(event) => event.stopPropagation()}
                      onChange={(event) => toggleSelected(session, event.target.checked)}
                    />
                  ) : null}
                  <Button
                    className="session-tile"
                    type="text"
                    title={`${client.getSessionTitle(session)} · ${client.getSessionDisplayId(session)}`}
                    onClick={() => client.setActiveSession(session.externalChatId)}
                  >
                    <span className="session-tile__initial" aria-hidden="true">
                      {client.getSessionTitle(session).slice(0, 1)}
                    </span>
                    <span className="session-tile__heading">
                      <strong>{client.getSessionTitle(session)}</strong>
                      {session.channel && session.channel !== "web" ? (
                        <span className="session-tile__channel">{copy.sidebar.historySessionLabel(session.channel)}</span>
                      ) : null}
                    </span>
                    <span className="session-tile__id">{client.getSessionDisplayId(session)}</span>
                  </Button>
                </div>
              );
            })}
          </div>
        </section>
      </div>

      <div className="sidebar__bottom">
        <Button className="settings-button" type="text" title={copy.sidebar.settings} onClick={() => client.openSettings("general")}>
          <span className="settings-button__avatar" aria-hidden="true">OS</span>
          <span className="settings-button__copy">
            <strong>{copy.sidebar.settings}</strong>
            <small>{copy.sidebar.settingsSubtitle}</small>
          </span>
        </Button>
      </div>
      {!client.sidebarCollapsed.value ? (
        <Button
          className="sidebar__resize"
          type="text"
          aria-label={copy.sidebar.resizeSidebar}
          title={copy.sidebar.resizeSidebar}
          onPointerDown={beginSidebarResize}
        />
      ) : null}
    </aside>
  );
}

function ChatPanel({ client, viewTraceForRun }: { client: Client; viewTraceForRun: (runId: string) => void }) {
  const copy = client.copy.value;
  const prompts = client.prompts.value || [];
  const notice = client.state.notice;

  return (
    <main className="chat-panel">
      <header className="topbar">
        <div className="topbar__title">
          <strong>{copy.chat.title}</strong>
          <span>{client.sessionMeta.value}</span>
        </div>
      </header>

      {notice?.text ? (
        <Alert className="notice-banner" role="status" type={noticeTone(notice.tone || "info")} showIcon message={notice.text} data-tone={notice.tone || "info"} />
      ) : null}

      <section ref={client.setMessageStageRef} className="message-stage" aria-live="polite">
        <div className="conversation-wrap">
          {!client.currentEntries.value.length && !client.currentMessages.value.length ? (
            <EmptyState copy={copy} prompts={prompts} applyPrompt={client.applyPrompt} />
          ) : null}
          <MessageList
            copy={copy}
            entries={client.currentEntries.value}
            messages={client.currentMessages.value}
            runs={client.currentRuns.value}
            displayName={client.state.displayName}
            viewTraceForRun={viewTraceForRun}
          />
        </div>
      </section>

      <form className="composer" onSubmit={client.submitMessage}>
        {client.commandHints.value?.length ? (
          <div className="composer__commands" aria-label={copy.composer.commandSuggestions}>
            {client.commandHints.value.map((command: AnyRecord) => (
              <Button
                key={command.name || command.command || command.usage}
                type="text"
                className="composer__command"
                onClick={() => client.applyCommandHint(command)}
              >
                <code>{command.usage || command.command}</code>
                <span>{command.description}</span>
              </Button>
            ))}
          </div>
        ) : null}
        <div className="composer__box">
          <Input.TextArea
            className="composer__input"
            id="messageInput"
            ref={(input) => client.setMessageInputRef(input?.resizableTextArea?.textArea || null)}
            value={client.messageText.value}
            rows={1}
            placeholder={copy.composer.placeholder}
            readOnly={client.currentSessionReadOnly.value}
            autoComplete="off"
            autoSize={false}
            onChange={(event) => {
              client.setMessageText(event.target.value);
              client.resizeComposer();
            }}
            onKeyDown={client.handleComposerKeydown}
          />
          <Button
            className="send-button"
            type="primary"
            htmlType="submit"
            aria-label={copy.composer.sendAria}
            disabled={client.sendDisabled.value}
            icon={<SendOutlined />}
          >
            {copy.composer.send}
          </Button>
        </div>
        <div className="composer__footer">
          <span>{copy.composer.disclaimer}</span>
          <span>{client.composerHint.value}</span>
        </div>
      </form>
    </main>
  );
}

function EmptyState({ copy, prompts, applyPrompt }: { copy: AnyRecord; prompts: AnyRecord[]; applyPrompt: (text: string) => void }) {
  return (
    <section className="empty-state" aria-label={copy.empty.ariaLabel}>
      <div className="empty-state__mark" aria-hidden="true">OS</div>
      <h1>{copy.empty.title}</h1>
      <p>{copy.empty.description}</p>
      <div className="prompt-grid">
        {prompts.map((prompt) => (
          <Button key={prompt.title} className="prompt-card" type="text" onClick={() => applyPrompt(prompt.text)}>
            <strong>{prompt.title}</strong>
            <span>{prompt.description}</span>
          </Button>
        ))}
      </div>
    </section>
  );
}

function MessageList({
  copy,
  entries,
  messages,
  runs,
  displayName,
  viewTraceForRun,
}: {
  copy: AnyRecord;
  entries: AnyRecord[];
  messages: AnyRecord[];
  runs: AnyRecord[];
  displayName: string;
  viewTraceForRun: (runId: string) => void;
}) {
  const renderedMessages = useMemo(
    () => normalizeMessages({ copy, entries, messages, runs, displayName }),
    [copy, entries, messages, runs, displayName],
  );

  return (
    <div className="message-list">
      {renderedMessages.map((message) => (
        <article key={message.id} className={`message message--${message.role}`}>
          <div className="message__avatar">{message.role === "user" ? copy.message.userAvatar : copy.message.assistantAvatar}</div>
          <div className="message__content">
            <div className="message__meta">
              <span>{message.meta || (message.role === "user" ? displayName : "OpenSprite")}</span>
              {message.timeLabel ? (
                <time className="message__time" dateTime={message.isoTime} title={message.fullTimeLabel}>
                  {message.timeLabel}
                </time>
              ) : null}
              {message.traceRunId ? (
                <Button
                  className="message__trace-button"
                  size="small"
                  icon={<EyeOutlined />}
                  onClick={() => viewTraceForRun(message.traceRunId)}
                >
                  {copy.message.viewTrace}
                </Button>
              ) : null}
            </div>
            {message.textBlocks.length ? (
              <div className="message__bubble">
                <MessageTextRenderer blocks={message.textBlocks} copy={copy} />
              </div>
            ) : null}
            {message.content?.length ? (
              <div className="message__parts">
                {message.content.map((part: AnyRecord) =>
                  part.type === "text" ? (
                    <div key={part.id} className="message__bubble">
                      <MessageTextRenderer blocks={part.textBlocks} copy={copy} />
                    </div>
                  ) : (
                    <Card key={part.id} size="small" className="message__artifact">
                      <Space>
                        <Tag>{artifactTypeLabel(copy, part.type)}</Tag>
                        {part.status ? <Tag color={runStatusColor(part.status)}>{artifactStatusLabel(copy, part.status)}</Tag> : null}
                      </Space>
                      <Typography.Title level={5}>{part.title || artifactTypeLabel(copy, part.type)}</Typography.Title>
                      {part.detail ? <Typography.Paragraph>{part.detail}</Typography.Paragraph> : null}
                    </Card>
                  ),
                )}
              </div>
            ) : null}
          </div>
        </article>
      ))}
    </div>
  );
}

function AuthGate({ client }: { client: Client }) {
  const copy = client.copy.value;
  if (!client.state.authRequired) {
    return null;
  }
  return (
    <section className="auth-gate" aria-labelledby="authGateTitle">
      <form className="auth-gate__card" onSubmit={client.submitAccessToken}>
        <span className="auth-gate__mark" aria-hidden="true">OS</span>
        <Typography.Title id="authGateTitle">{copy.auth.title}</Typography.Title>
        <Typography.Paragraph>{copy.auth.description}</Typography.Paragraph>
        <Form layout="vertical">
          <Form.Item label={copy.auth.tokenLabel}>
            <Input.Password
              value={client.settingsForm.accessToken}
              autoFocus
              onChange={(event) => {
                client.settingsForm.accessToken = event.target.value;
              }}
            />
          </Form.Item>
        </Form>
        {client.state.authError ? <Alert type="error" message={client.state.authError} /> : null}
        <Space>
          <Button type="primary" htmlType="submit">{copy.auth.submit}</Button>
          <Button onClick={() => client.openSettings("general")}>{copy.auth.settings}</Button>
        </Space>
      </form>
    </section>
  );
}

function SettingsModal({ client, clearWebSessions }: { client: Client; clearWebSessions: () => void }) {
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
  client: Client,
  clearWebSessions: () => void,
  copy: AnyRecord,
) {
  switch (section) {
    case "providers":
      return <ProviderSettings client={client} />;
    case "models":
      return <ModelSettings client={client} />;
    case "channels":
      return <ChannelSettings client={client} />;
    case "mcp":
      return <McpSettings client={client} />;
    case "schedule":
      return <ScheduleSettings client={client} />;
    case "network":
      return <NetworkSettings client={client} />;
    case "search":
      return <SearchSettings client={client} />;
    case "browser":
      return <BrowserSettings client={client} />;
    case "log":
      return <LogSettings client={client} />;
    case "shortcuts":
      return <ShortcutSettings copy={copy} />;
    case "general":
    default:
      return <GeneralSettings client={client} clearWebSessions={clearWebSessions} />;
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


function ShortcutSettings({ copy }: { copy: AnyRecord }) {
  return (
    <section className="settings-page">
      <SettingsCard>
        <SettingsRow title={copy.settings.shortcuts?.openSettings || "Open settings"} description={copy.settings.shortcuts?.openSettingsDescription || ""}>
          <div className="shortcut-keys"><kbd>Ctrl</kbd><kbd>,</kbd></div>
        </SettingsRow>
        <SettingsRow title={copy.settings.shortcuts?.sendMessage || "Send message"} description={copy.settings.shortcuts?.sendMessageDescription || ""}>
          <div className="shortcut-keys"><kbd>Enter</kbd></div>
        </SettingsRow>
      </SettingsCard>
    </section>
  );
}

function copyText(value: any, fallback: string) {
  if (typeof value === "string" && value.trim()) {
    return value;
  }
  if (value && typeof value === "object") {
    if (typeof value.title === "string" && value.title.trim()) {
      return value.title;
    }
    if (typeof value.label === "string" && value.label.trim()) {
      return value.label;
    }
    if (typeof value.action === "string" && value.action.trim()) {
      return value.action;
    }
  }
  return fallback;
}

function readStoredTraceWidth() {
  try {
    const value = Number.parseInt(window.localStorage.getItem(TRACE_WIDTH_STORAGE_KEY) || "", 10);
    return Number.isFinite(value) ? Math.max(TRACE_WIDTH_MIN, value) : 0;
  } catch {
    return 0;
  }
}

function readStoredSidebarWidth() {
  try {
    const value = Number.parseInt(window.localStorage.getItem(SIDEBAR_WIDTH_STORAGE_KEY) || "", 10);
    return Number.isFinite(value) ? Math.min(Math.max(value, SIDEBAR_WIDTH_MIN), SIDEBAR_WIDTH_MAX) : SIDEBAR_WIDTH_DEFAULT;
  } catch {
    return SIDEBAR_WIDTH_DEFAULT;
  }
}
