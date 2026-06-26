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
  List,
  Menu,
  Modal,
  Segmented,
  Select,
  Space,
  Spin,
  Switch,
  Tag,
  Typography,
  theme,
} from "antd";
import {
  ApiOutlined,
  ArrowLeftOutlined,
  BranchesOutlined,
  CloseOutlined,
  DeleteOutlined,
  EyeOutlined,
  HistoryOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  PlusOutlined,
  ReloadOutlined,
  SaveOutlined,
  SendOutlined,
  SettingOutlined,
  StopOutlined,
  ToolOutlined,
} from "@ant-design/icons";
import { useReactiveStore } from "./lib/reactiveCompat";
import { useChatClient } from "./composables/useChatClient";
import { connectionLabel, noticeTone, runStatusColor } from "./components/displayHelpers";
import { artifactStatusLabel, artifactTypeLabel, normalizeMessages } from "./components/messageData";
import { MessageTextRenderer } from "./components/messageMarkdown";
import { RunInspector } from "./components/runInspector";
import { ToastStack } from "./components/toastStack";
import { ChannelSettings } from "./settings/channelSettings";
import { LogSettings } from "./settings/logSettings";
import { McpSettings } from "./settings/mcpSettings";
import { ModelSettings } from "./settings/modelSettings";
import { NetworkSettings } from "./settings/networkSettings";
import { ProviderSettings } from "./settings/providerSettings";
import {
  browserBackendOptions,
  browserDoctorCheckSummary,
  browserDoctorSummary,
  browserRuntimeStatus,
  browserSummary,
  browserTestSummary,
  mergeSelectedSearchOptions,
  searxngEngineMeta,
  selectedBrowserBackend,
  selectedBrowserBackendLabel,
  webSearchCredentialStatus,
  webSearchFreshnessOptions,
  webSearchProviderOptions,
  webSearchSummary,
} from "./settings/searchBrowserHelpers";
import { scheduleTimezoneOptions } from "./settings/scheduleNetworkHelpers";
import { SettingsCard, SettingsRow, SettingsSectionTitle, SettingsStatus } from "./settings/settingsPrimitives";

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

function GeneralSettings({ client, clearWebSessions }: { client: Client; clearWebSessions: () => void }) {
  const copy = client.copy.value;
  const state = client.settingsState;
  const form = client.settingsForm;
  const general = copy.settings.general || {};
  const webSessionCount = Number(client.webSessionCount?.value || 0);
  const connectionSwitchChecked = client.state.connectionState === "connected" || client.state.connectionState === "connecting";
  const connectionSwitchLabel = (() => {
    if (client.state.connectionState === "connecting") {
      return general.gateway?.connecting || "Connecting";
    }
    if (client.state.connectionState === "connected") {
      return general.gateway?.connected || connectionLabel(copy, "connected");
    }
    return general.gateway?.disconnected || connectionLabel(copy, "disconnected");
  })();
  const updateStatus: AnyRecord = state.updateStatus || {};
  const updateStatusLabel = (() => {
    if (state.updateLoading) {
      return general.update?.checking || "Checking for updates...";
    }
    if (!updateStatus.supported) {
      return general.update?.unsupported || "Update is not supported in this install.";
    }
    if (updateStatus.dirty) {
      return general.update?.dirty || "Working tree has local changes.";
    }
    if (updateStatus.update_available) {
      return typeof general.update?.available === "function"
        ? general.update.available(updateStatus.commits_behind || 0)
        : `${updateStatus.commits_behind || 0} commits behind`;
    }
    return general.update?.current || "Current";
  })();
  const runPanelRows = [
    ["showWorkState", general.workState, form.showWorkState],
    ["showRunHistory", general.runHistory, form.showRunHistory],
    ["showRunTimeline", general.runTimeline, form.showRunTimeline],
    ["showRunSummary", general.runSummary, form.showRunSummary],
    ["showRunTrace", general.runTrace, form.showRunTrace],
  ];

  return (
    <section className="settings-page">
      <SettingsCard>
        <SettingsRow title={general.language?.title || "Language"} description={general.language?.description || "Display language."}>
          <Select
            className="settings-control"
            value={form.language}
            aria-label={general.language?.title || "Language"}
            options={[
              { value: "zh-TW", label: general.language?.options?.zhTW || "Traditional Chinese" },
              { value: "en", label: general.language?.options?.en || "English" },
            ]}
            onChange={(value) => (form.language = value)}
          />
        </SettingsRow>

        {runPanelRows.map(([key, item, checked]: any[]) => (
          <SettingsRow key={key} title={item?.title || key} description={item?.description || ""}>
            <Switch aria-label={item?.title || key} checked={Boolean(checked)} onChange={(checkedValue) => (form[key] = checkedValue)} />
          </SettingsRow>
        ))}
      </SettingsCard>

      <SettingsSectionTitle>{general.connectionTitle || "Connection"}</SettingsSectionTitle>
      <SettingsCard className="settings-card--form">
        <SettingsRow title={general.wsUrl?.title || "WebSocket URL"} description={general.wsUrl?.description || "Local gateway WebSocket endpoint."} className="settings-row--field">
          <Input value={form.wsUrl} spellCheck={false} onChange={(event) => (form.wsUrl = event.target.value)} />
        </SettingsRow>
        <SettingsRow title={general.accessToken?.title || copy.auth.tokenLabel || "Access token"} description={general.accessToken?.description || ""} className="settings-row--field">
          <Input.Password value={form.accessToken} autoComplete="current-password" spellCheck={false} onChange={(event) => (form.accessToken = event.target.value)} />
        </SettingsRow>
        <SettingsRow title={general.displayName?.title || "Display name"} description={general.displayName?.description || ""} className="settings-row--field">
          <Input value={form.displayName} maxLength={60} onChange={(event) => (form.displayName = event.target.value)} />
        </SettingsRow>
        <SettingsRow title={general.externalChatId?.title || "External chat ID"} description={general.externalChatId?.description || ""} className="settings-row--field">
          <Input value={form.externalChatId} spellCheck={false} onChange={(event) => (form.externalChatId = event.target.value)} />
        </SettingsRow>
        <SettingsRow title={general.gateway?.title || "Gateway"} description={connectionSwitchLabel}>
          <Switch
            aria-label={general.gateway?.title || "Gateway"}
            checked={connectionSwitchChecked}
            disabled={client.state.connectionState === "connecting"}
            onChange={client.toggleSettingsConnection}
          />
        </SettingsRow>
        <SettingsRow title={general.connectionTitle || "Current connection"} description={connectionLabel(copy, client.state.connectionState)}>
          <Button icon={<SaveOutlined />} onClick={client.saveConnectionSettings}>
            {general.saveConnection || copy.settings.save || "Save"}
          </Button>
        </SettingsRow>
      </SettingsCard>

      <SettingsSectionTitle>{general.appearanceTitle || "Appearance"}</SettingsSectionTitle>
      <SettingsCard>
        <SettingsRow title={general.colorScheme?.title || "Theme"} description={general.colorScheme?.description || ""}>
          <Segmented
            value={form.colorScheme}
            options={[
              { value: "system", label: general.colorScheme?.options?.system || "System" },
              { value: "light", label: general.colorScheme?.options?.light || "Light" },
              { value: "dark", label: general.colorScheme?.options?.dark || "Dark" },
            ]}
            onChange={(value) => (form.colorScheme = String(value))}
          />
        </SettingsRow>
      </SettingsCard>

      <SettingsSectionTitle>{general.conversationsTitle || "Conversations"}</SettingsSectionTitle>
      <SettingsCard>
        <SettingsRow
          title={general.clearWebChats?.title || "Clear Web chats"}
          description={typeof general.clearWebChats?.description === "function" ? general.clearWebChats.description(webSessionCount) : `${webSessionCount} Web conversations`}
          className="settings-row--update"
        >
          <Space>
            <Button danger disabled={webSessionCount === 0} icon={<DeleteOutlined />} onClick={clearWebSessions}>
              {general.clearWebChats?.action || "Clear Web chats"}
            </Button>
          </Space>
        </SettingsRow>
      </SettingsCard>

      <SettingsSectionTitle>{general.update?.title || "Update"}</SettingsSectionTitle>
      <SettingsStatus message={state.updateNotice} />
      <SettingsStatus message={state.updateError} type="error" />
      <SettingsCard>
        <SettingsRow title={updateStatusLabel} className="settings-row--update">
          <Space wrap>
            <Button icon={<ReloadOutlined />} loading={state.updateLoading} disabled={state.updateLoading} onClick={client.loadUpdateStatus}>
              {general.update?.check || "Check"}
            </Button>
            <Button
              type="primary"
              disabled={state.updateLoading || !updateStatus.supported || updateStatus.dirty}
              loading={state.updateLoading}
              onClick={client.runUpdate}
            >
              {general.update?.apply || "Apply"}
            </Button>
          </Space>
        </SettingsRow>
      </SettingsCard>
    </section>
  );
}

function ScheduleSettings({ client }: { client: Client }) {
  const state = client.settingsState;
  const copy = client.copy.value;
  const scheduleCopy = copy.settings.schedule || {};
  const timezones = scheduleTimezoneOptions(state);
  const form = state.cronJobForm;

  return (
    <section className="settings-page">
      <SettingsStatus message={state.scheduleLoading ? scheduleCopy.loading || "Loading schedule settings..." : ""} />
      <SettingsStatus message={state.scheduleNotice} />
      <SettingsStatus message={state.scheduleError} type="error" />

      <SettingsSectionTitle>{scheduleCopy.defaultsTitle || "Schedule defaults"}</SettingsSectionTitle>
      <SettingsCard className="settings-card--form">
        <SettingsRow title={scheduleCopy.defaultTimezone?.title || "Default timezone"} description={scheduleCopy.defaultTimezone?.description || ""} className="settings-row--field">
          <Select
            value={state.scheduleForm.defaultTimezone}
            aria-label={scheduleCopy.defaultTimezone?.title || "Default timezone"}
            disabled={state.scheduleLoading}
            options={timezones.map((timezone) => ({ value: timezone, label: timezone }))}
            onChange={(value) => (state.scheduleForm.defaultTimezone = value)}
          />
        </SettingsRow>
        <SettingsRow title={scheduleCopy.currentTitle || "Currently active"} description={state.schedule.default_timezone || "UTC"}>
          <Button icon={<SaveOutlined />} loading={state.scheduleLoading} disabled={state.scheduleLoading} onClick={client.saveScheduleSettings}>
            {scheduleCopy.save || "Save"}
          </Button>
        </SettingsRow>
      </SettingsCard>

      <div className="schedule-list-screen__header">
        <SettingsSectionTitle>{scheduleCopy.manageTitle || "Manage schedules"}</SettingsSectionTitle>
        <Button type="primary" icon={<PlusOutlined />} onClick={client.beginCronJobCreate}>
          {scheduleCopy.openAdd || "Create schedule"}
        </Button>
      </div>
      <SettingsStatus message={state.cronJobsError} type="error" />

      <SettingsSectionTitle>{scheduleCopy.jobsTitle || "Schedules"}</SettingsSectionTitle>
      <SettingsStatus message={state.cronJobsLoading ? scheduleCopy.jobsLoading || "Loading schedules..." : ""} />
      <SettingsCard className="provider-card">
        <List
          className="provider-row-list schedule-job-list"
          dataSource={state.cronJobs || []}
          locale={{
            emptyText: (
              <div className="provider-row provider-row--empty">
                <div>
                  <strong>{scheduleCopy.noJobsTitle || "No schedules yet"}</strong>
                  <span>{scheduleCopy.noJobsDescription || ""}</span>
                </div>
              </div>
            ),
          }}
          renderItem={(job: AnyRecord) => (
            <List.Item key={job.id} className="schedule-job-row">
              <div className="schedule-job-row__main">
                <div className="provider-row__title">
                  <strong>{job.name || job.id}</strong>
                  <Tag className="provider-row__badge">{job.enabled ? scheduleCopy.enabled || "Enabled" : scheduleCopy.paused || "Paused"}</Tag>
                </div>
                <span>{job.schedule?.display || job.cron_expr || job.every_seconds || ""}</span>
                {job.session_id ? <span>{typeof scheduleCopy.sessionLabel === "function" ? scheduleCopy.sessionLabel(job.session_id) : job.session_id}</span> : null}
                {job.state?.next_run_display ? <span>{typeof scheduleCopy.nextRun === "function" ? scheduleCopy.nextRun(job.state.next_run_display) : job.state.next_run_display}</span> : null}
                <p>{job.payload?.message || job.message || ""}</p>
              </div>
              <Space className="schedule-job-row__actions" wrap>
                <Button onClick={() => client.beginCronJobEdit(job)}>{scheduleCopy.edit || "Edit"}</Button>
                <Button disabled={state.cronJobsLoading} onClick={() => client.runCronJobAction(job, job.enabled ? "pause" : "enable")}>
                  {job.enabled ? scheduleCopy.pause || "Pause" : scheduleCopy.enable || "Enable"}
                </Button>
                <Button disabled={state.cronJobsLoading} onClick={() => client.runCronJobAction(job, "run")}>{scheduleCopy.runNow || "Run now"}</Button>
                <Button danger disabled={state.cronJobsLoading} onClick={() => client.runCronJobAction(job, "remove")}>{scheduleCopy.remove || "Remove"}</Button>
              </Space>
            </List.Item>
          )}
        />
      </SettingsCard>

      <SettingsSectionTitle>{scheduleCopy.usageTitle || "Usage"}</SettingsSectionTitle>
      <SettingsCard>
        <SettingsRow title={scheduleCopy.usageCron?.title || "Create scheduled jobs"} description={scheduleCopy.usageCron?.description || ""} />
        <SettingsRow title={scheduleCopy.usageExisting?.title || "Existing jobs"} description={scheduleCopy.usageExisting?.description || ""} />
      </SettingsCard>

      {form.showEditor ? (
        <div className="provider-connect-dialog" role="dialog" aria-modal="true">
          <header className="provider-connect-dialog__top">
            <Button type="text" aria-label={scheduleCopy.backToList || "Back"} icon={<ArrowLeftOutlined />} onClick={client.cancelCronJobEdit} />
            <Button type="text" aria-label={copy.settings.closeAria || "Close"} icon={<CloseOutlined />} onClick={client.cancelCronJobEdit} />
          </header>
          <Form className="provider-connect-dialog__body" layout="vertical" onFinish={() => client.saveCronJob()}>
            <div className="provider-connect-dialog__title">
              <span className="provider-row__mark" aria-hidden="true">SC</span>
              <h3>{form.jobId ? scheduleCopy.editJobTitle || "Edit schedule" : scheduleCopy.newJobTitle || "Create schedule"}</h3>
            </div>
            <p>{scheduleCopy.newJobDescription || ""}</p>
            <Form.Item className="provider-connect-field" label={scheduleCopy.jobName || "Name"}>
              <Input value={form.name} autoComplete="off" onChange={(event) => (form.name = event.target.value)} />
            </Form.Item>
            <Form.Item className="provider-connect-field" label={scheduleCopy.jobType || "Type"}>
              <Select
                value={form.mode}
                options={[
                  { value: "cron", label: scheduleCopy.jobTypes?.cron || "Cron expression" },
                  { value: "every", label: scheduleCopy.jobTypes?.every || "Fixed interval" },
                  { value: "at", label: scheduleCopy.jobTypes?.at || "Run once" },
                ]}
                onChange={(value) => (form.mode = value)}
              />
            </Form.Item>
            {form.mode === "every" ? (
              <Form.Item className="provider-connect-field" label={scheduleCopy.everySeconds || "Interval seconds"}>
                <InputNumber className="settings-control" value={Number(form.everySeconds || 3600)} min={1} step={1} onChange={(value) => (form.everySeconds = String(value || 3600))} />
              </Form.Item>
            ) : null}
            {form.mode === "cron" ? (
              <>
                <Form.Item className="provider-connect-field" label={scheduleCopy.cronExpression || "Cron expression"}>
                  <Input value={form.cronExpr} spellCheck={false} autoComplete="off" onChange={(event) => (form.cronExpr = event.target.value)} />
                </Form.Item>
                <Form.Item className="provider-connect-field" label={scheduleCopy.timezone || "Timezone"}>
                  <Select value={form.timezone} options={timezones.map((timezone) => ({ value: timezone, label: timezone }))} onChange={(value) => (form.timezone = value)} />
                </Form.Item>
              </>
            ) : null}
            {form.mode === "at" ? (
              <Form.Item className="provider-connect-field" label={scheduleCopy.runAt || "Run at"}>
                <Input value={form.at} type="datetime-local" onChange={(event) => (form.at = event.target.value)} />
              </Form.Item>
            ) : null}
            <Form.Item className="provider-connect-field" label={scheduleCopy.message || "Message"}>
              <Input.TextArea value={form.message} rows={3} spellCheck={false} onChange={(event) => (form.message = event.target.value)} />
            </Form.Item>
            <SettingsRow title={scheduleCopy.deliver?.title || "Send back to chat"} description={scheduleCopy.deliver?.description || ""} className="schedule-editor__deliver">
              <Switch aria-label={scheduleCopy.deliver?.title || "Deliver"} checked={Boolean(form.deliver)} onChange={(checked) => (form.deliver = checked)} />
            </SettingsRow>
            <Button className="provider-connect-dialog__submit" type="primary" htmlType="submit" loading={state.cronJobsLoading} disabled={state.cronJobsLoading}>
              {form.jobId ? scheduleCopy.updateJob || "Update schedule" : scheduleCopy.createJob || "Create schedule"}
            </Button>
          </Form>
        </div>
      ) : null}
    </section>
  );
}

function SearchSettings({ client }: { client: Client }) {
  const state = client.settingsState;
  const copy = client.copy.value;
  const [searxngOptionsExpanded, setSearxngOptionsExpanded] = useState(false);
  const searchCopy = copy.settings.search || {};
  const form = state.searchForm;
  const providerOptions = webSearchProviderOptions(copy, state);
  const freshnessOptions = webSearchFreshnessOptions(copy, state);
  const engineOptions = mergeSelectedSearchOptions(state.search?.searxng_options?.engines, form.searxngEngines);
  const categoryOptions = mergeSelectedSearchOptions(state.search?.searxng_options?.categories, form.searxngCategories);
  const summary = webSearchSummary(copy, state);
  const toggleSearchSelection = (field: "searxngEngines" | "searxngCategories", value: string, checked: boolean) => {
    const current = Array.isArray(form[field]) ? form[field] : [];
    form[field] = checked ? Array.from(new Set([...current, value])) : current.filter((item: string) => item !== value);
  };

  return (
    <section className="settings-page">
      <SettingsStatus message={state.searchLoading ? searchCopy.loading || "Loading search settings..." : ""} />
      <SettingsStatus message={state.searchNotice} />
      <SettingsStatus message={state.searchError} type="error" />

      <SettingsSectionTitle>{searchCopy.title || "Web search"}</SettingsSectionTitle>
      <SettingsCard className="settings-card--form">
        <SettingsRow title={searchCopy.provider?.title || "Provider"} description={searchCopy.provider?.description || ""} className="settings-row--field">
          <Select value={form.provider} disabled={state.searchLoading} options={providerOptions.map((provider) => ({ value: provider.id, label: provider.label }))} onChange={(value) => (form.provider = value)} />
        </SettingsRow>
        <SettingsRow title={searchCopy.freshness?.title || "Freshness"} description={searchCopy.freshness?.description || ""} className="settings-row--field">
          <Select value={form.freshness} disabled={state.searchLoading} options={freshnessOptions.map((freshness) => ({ value: freshness.id, label: freshness.label }))} onChange={(value) => (form.freshness = value)} />
        </SettingsRow>
        <SettingsRow title={searchCopy.maxResults?.title || "Max results"} description={searchCopy.maxResults?.description || ""} className="settings-row--field">
          <InputNumber className="settings-control" value={Number(form.maxResults || 25)} min={1} max={100} disabled={state.searchLoading} onChange={(value) => (form.maxResults = Number(value || 25))} />
        </SettingsRow>
        <SettingsRow title={searchCopy.duckduckgoMaxPages?.title || "DuckDuckGo max pages"} description={searchCopy.duckduckgoMaxPages?.description || ""} className="settings-row--field">
          <InputNumber className="settings-control" value={Number(form.duckduckgoMaxPages || 10)} min={1} max={50} disabled={state.searchLoading} onChange={(value) => (form.duckduckgoMaxPages = Number(value || 10))} />
        </SettingsRow>
        <SettingsRow title={searchCopy.searxngMaxPages?.title || "SearXNG max pages"} description={searchCopy.searxngMaxPages?.description || ""} className="settings-row--field">
          <InputNumber className="settings-control" value={Number(form.searxngMaxPages || 5)} min={1} max={50} disabled={state.searchLoading} onChange={(value) => (form.searxngMaxPages = Number(value || 5))} />
        </SettingsRow>
        <SettingsRow title={searchCopy.searxngUrl?.title || "SearXNG URL"} description={searchCopy.searxngUrl?.description || ""} className="settings-row--field">
          <Input value={form.searxngUrl} placeholder={searchCopy.searxngUrl?.placeholder || "https://searx.be"} disabled={state.searchLoading} onChange={(event) => (form.searxngUrl = event.target.value)} />
        </SettingsRow>

        <SettingsRow title={searchCopy.searxngOptions?.title || "SearXNG options"} description={searchCopy.searxngOptions?.description || ""}>
          <Button
            aria-expanded={searxngOptionsExpanded}
            onClick={() => {
              const next = !searxngOptionsExpanded;
              setSearxngOptionsExpanded(next);
              const hasOptions = Boolean(state.search?.searxng_options?.engines?.length || state.search?.searxng_options?.categories?.length);
              if (next && !hasOptions && !state.searchOptionsLoading) {
                client.loadSearxngOptions();
              }
            }}
          >
            {searxngOptionsExpanded ? searchCopy.searxngOptions?.collapse || "Collapse" : searchCopy.searxngOptions?.expand || "Expand"}
          </Button>
        </SettingsRow>

        {searxngOptionsExpanded ? (
          <div className="settings-collapsible-section">
            <div className="settings-row">
              <div>
                <strong>{searchCopy.searxngOptions?.loadTitle || "Load available options"}</strong>
                <span>{searchCopy.searxngOptions?.loadDescription || ""}</span>
                {state.searchOptionsNotice ? <span>{state.searchOptionsNotice}</span> : null}
                {state.searchOptionsError ? <span className="settings-row__error">{state.searchOptionsError}</span> : null}
              </div>
              <Button loading={state.searchOptionsLoading} disabled={state.searchLoading || state.searchOptionsLoading} onClick={client.loadSearxngOptions}>
                {state.searchOptionsLoading ? searchCopy.searxngOptions?.loading || "Loading..." : searchCopy.searxngOptions?.load || "Load options"}
              </Button>
            </div>
            <SettingsRow title={searchCopy.searxngEngines?.title || "SearXNG engines"} description={searchCopy.searxngEngines?.description || ""} className="settings-row--field settings-row--choice-list">
              {engineOptions.length ? (
                <Select
                  mode="multiple"
                  className="settings-control"
                  value={form.searxngEngines || []}
                  disabled={state.searchLoading}
                  options={engineOptions.map((option: AnyRecord) => ({ value: option.id, label: `${option.label}${searxngEngineMeta(copy, option) ? ` - ${searxngEngineMeta(copy, option)}` : ""}` }))}
                  onChange={(values) => (form.searxngEngines = values)}
                />
              ) : <p className="settings-empty-inline">{searchCopy.searxngOptions?.emptyEngines || "No engines loaded."}</p>}
            </SettingsRow>
            <SettingsRow title={searchCopy.searxngCategories?.title || "SearXNG categories"} description={searchCopy.searxngCategories?.description || ""} className="settings-row--field settings-row--choice-list">
              {categoryOptions.length ? (
                <Select
                  mode="multiple"
                  className="settings-control"
                  value={form.searxngCategories || []}
                  disabled={state.searchLoading}
                  options={categoryOptions.map((option: AnyRecord) => ({ value: option.id, label: `${option.label}${option.configuredOnly ? ` - ${searchCopy.searxngOptions?.configuredOnly || "Configured but not listed"}` : ""}` }))}
                  onChange={(values) => (form.searxngCategories = values)}
                />
              ) : <p className="settings-empty-inline">{searchCopy.searxngOptions?.emptyCategories || "No categories loaded."}</p>}
            </SettingsRow>
          </div>
        ) : null}

        <SettingsRow title={searchCopy.proxy?.title || "Search proxy"} description={searchCopy.proxy?.description || ""} className="settings-row--field">
          <Input value={form.proxy} placeholder={searchCopy.proxy?.placeholder || "http://proxy-host:port"} disabled={state.searchLoading} onChange={(event) => (form.proxy = event.target.value)} />
        </SettingsRow>
        <SettingsRow title={searchCopy.currentTitle || "Current setting"} description={summary}>
          <Button icon={<SaveOutlined />} loading={state.searchLoading} disabled={state.searchLoading} onClick={client.saveSearchSettings}>
            {searchCopy.save || "Save search settings"}
          </Button>
        </SettingsRow>
      </SettingsCard>

      <SettingsSectionTitle>{searchCopy.credentialsTitle || "Provider API keys"}</SettingsSectionTitle>
      <SettingsCard className="settings-card--form">
        <SettingsRow
          title={searchCopy.credentials?.jina?.title || "Jina API key"}
          description={typeof searchCopy.credentials?.description === "function"
            ? searchCopy.credentials.description(webSearchCredentialStatus(copy, state, "jina"))
            : webSearchCredentialStatus(copy, state, "jina")}
          className="settings-row--field"
        >
          <Input.Password value={form.jinaApiKey} autoComplete="new-password" placeholder={searchCopy.credentials?.placeholder || "Leave blank to keep existing key"} disabled={state.searchLoading} onChange={(event) => (form.jinaApiKey = event.target.value)} />
        </SettingsRow>
      </SettingsCard>
    </section>
  );
}

function BrowserSettings({ client }: { client: Client }) {
  const state = client.settingsState;
  const copy = client.copy.value;
  const form = state.browserForm;
  const browserCopy = copy.settings.browser || {};
  const backendOptions = browserBackendOptions(copy, state);
  const summary = browserSummary(copy, state);
  const runtime = browserRuntimeStatus(copy, state);
  const testSummary = browserTestSummary(copy, state);
  const doctorSummary = browserDoctorSummary(copy, state);

  return (
    <section className="settings-page">
      <SettingsStatus message={state.browserLoading ? browserCopy.loading || "Loading browser settings..." : ""} />
      <SettingsStatus message={state.browserNotice} />
      <SettingsStatus message={state.browserError} type="error" />

      <SettingsSectionTitle>{browserCopy.title || "Browser automation"}</SettingsSectionTitle>
      <SettingsCard className="settings-card--form">
        <SettingsRow title={browserCopy.enabled?.title || "Enable browser tools"} description={browserCopy.enabled?.description || ""}>
          <Switch aria-label={browserCopy.enabled?.title || "Enable browser tools"} checked={Boolean(form.enabled)} disabled={state.browserLoading} onChange={(checked) => (form.enabled = checked)} />
        </SettingsRow>
        <SettingsRow title={browserCopy.backend?.title || "Backend"} description={browserCopy.backend?.description || ""} className="settings-row--field">
          <Select value={form.backend} disabled={state.browserLoading} options={backendOptions.map((backend) => ({ value: backend.id, label: backend.label }))} onChange={(value) => (form.backend = value)} />
        </SettingsRow>
        <SettingsRow title={browserCopy.cdpUrl?.title || "Chrome CDP URL"} description={browserCopy.cdpUrl?.description || ""} className="settings-row--field">
          <Input value={form.cdpUrl} placeholder={browserCopy.cdpUrl?.placeholder || "http://127.0.0.1:9222"} disabled={state.browserLoading} onChange={(event) => (form.cdpUrl = event.target.value)} />
        </SettingsRow>
        <SettingsRow title={browserCopy.launchArgs?.title || "Browser launch args"} description={browserCopy.launchArgs?.description || ""} className="settings-row--field">
          <Input value={form.launchArgs} spellCheck={false} placeholder={browserCopy.launchArgs?.placeholder || "--no-sandbox"} disabled={state.browserLoading} onChange={(event) => (form.launchArgs = event.target.value)} />
        </SettingsRow>
        <SettingsRow title={browserCopy.commandTimeout?.title || "Command timeout"} description={browserCopy.commandTimeout?.description || ""} className="settings-row--field">
          <InputNumber className="settings-control" value={Number(form.commandTimeout || 30)} min={1} max={600} disabled={state.browserLoading} onChange={(value) => (form.commandTimeout = Number(value || 30))} />
        </SettingsRow>
        <SettingsRow title={browserCopy.sessionTimeout?.title || "Session timeout"} description={browserCopy.sessionTimeout?.description || ""} className="settings-row--field">
          <InputNumber className="settings-control" value={Number(form.sessionTimeout || 1800)} min={1} max={86400} disabled={state.browserLoading} onChange={(value) => (form.sessionTimeout = Number(value || 1800))} />
        </SettingsRow>
        <SettingsRow title={browserCopy.allowPrivateUrls?.title || "Allow private URLs"} description={browserCopy.allowPrivateUrls?.description || ""}>
          <Switch aria-label={browserCopy.allowPrivateUrls?.title || "Allow private URLs"} checked={Boolean(form.allowPrivateUrls)} disabled={state.browserLoading} onChange={(checked) => (form.allowPrivateUrls = checked)} />
        </SettingsRow>
        <SettingsRow title={browserCopy.currentTitle || "Current setting"} description={summary}>
          <Button icon={<SaveOutlined />} loading={state.browserLoading} disabled={state.browserLoading} onClick={client.saveBrowserSettings}>
            {browserCopy.save || "Save browser settings"}
          </Button>
        </SettingsRow>
      </SettingsCard>

      <SettingsSectionTitle>{browserCopy.test?.title || "Manual browser test"}</SettingsSectionTitle>
      <SettingsCard className="settings-card--form">
        <SettingsRow title={browserCopy.test?.urlTitle || "Test URL"} description={browserCopy.test?.description || ""} className="settings-row--field">
          <Input value={form.testUrl} type="url" spellCheck={false} placeholder={browserCopy.test?.placeholder || "https://quotes.toscrape.com/js/"} disabled={state.browserTestLoading} onChange={(event) => (form.testUrl = event.target.value)} />
        </SettingsRow>
        <SettingsRow title={browserCopy.test?.currentTitle || "Test status"} description={testSummary} className="settings-row--update">
          <Space>
            <Button loading={state.browserTestLoading} disabled={state.browserTestLoading || state.browserLoading} onClick={client.runBrowserTest}>
              {state.browserTestLoading ? browserCopy.test?.running || "Testing..." : browserCopy.test?.run || "Run browser test"}
            </Button>
          </Space>
        </SettingsRow>
      </SettingsCard>

      <SettingsCard>
        <SettingsRow title={browserCopy.runtimeTitle || "Runtime status"} description={<>{runtime}{state.browser.runtime?.install_hint ? <><br />{state.browser.runtime.install_hint}</> : null}</>} />
      </SettingsCard>

      <SettingsSectionTitle>{browserCopy.doctor?.title || "Browser install check"}</SettingsSectionTitle>
      <SettingsCard>
        <SettingsRow title={browserCopy.doctor?.currentTitle || "Install status"} description={doctorSummary} className="settings-row--update">
          <Space wrap>
            <Button loading={state.browserDoctorLoading} disabled={state.browserDoctorLoading || state.browserLoading} onClick={client.runBrowserDoctor}>
              {state.browserDoctorLoading ? browserCopy.doctor?.running || "Checking..." : browserCopy.doctor?.run || "Check browser install"}
            </Button>
            <Button loading={state.browserInstallLoading} disabled={state.browserInstallLoading || state.browserDoctorLoading || state.browserLoading} onClick={client.runBrowserInstall}>
              {state.browserInstallLoading ? browserCopy.install?.running || "Installing..." : browserCopy.install?.run || "Install browser"}
            </Button>
          </Space>
        </SettingsRow>
        {state.browserDoctorResult?.checks?.length ? (
          <div className="settings-stack">
            {state.browserDoctorResult.checks.map((check: AnyRecord) => (
              <SettingsRow key={check.name || check.command} title={check.command || check.name} description={browserDoctorCheckSummary(copy, check)} />
            ))}
          </div>
        ) : null}
      </SettingsCard>
    </section>
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
