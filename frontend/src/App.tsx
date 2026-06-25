import React, { CSSProperties, useEffect, useMemo, useState, useTransition } from "react";
import {
  Alert,
  App as AntdApp,
  Button,
  Card,
  Checkbox,
  Collapse,
  ConfigProvider,
  Descriptions,
  Empty,
  Flex,
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
  Timeline,
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
import { shortRunId } from "./composables/chatClientRunHelpers";

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
const TRACE_MATCH_WINDOW_MS = 5000;

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

function MessageTextRenderer({ blocks, copy }: { blocks: AnyRecord[]; copy: AnyRecord }) {
  return (
    <div className="message__rendered">
      {blocks.map((block) => {
        if (block.type === "heading") {
          if (block.level <= 1) {
            return <h3 key={block.id}>{renderSegments(block.segments)}</h3>;
          }
          if (block.level === 2) {
            return <h4 key={block.id}>{renderSegments(block.segments)}</h4>;
          }
          return <h5 key={block.id}>{renderSegments(block.segments)}</h5>;
        }
        if (block.type === "list") {
          const ListTag = block.ordered ? "ol" : "ul";
          return (
            <ListTag key={block.id}>
              {block.items.map((item: AnyRecord) => (
                <li key={item.id}>{renderSegments(item.segments)}</li>
              ))}
            </ListTag>
          );
        }
        if (block.type === "quote") {
          return <blockquote key={block.id}>{renderSegments(block.segments)}</blockquote>;
        }
        if (block.type === "code") {
          return (
            <pre key={block.id} className="message__code-block">
              <code>{block.code}</code>
            </pre>
          );
        }
        if (block.type === "json") {
          return (
            <details key={block.id} className="message__json-card">
              <summary>
                <strong>{copy.message.jsonTitle}</strong>
                <span>{block.summary}</span>
              </summary>
              <pre>{block.code}</pre>
            </details>
          );
        }
        if (block.type === "table") {
          return (
            <div key={block.id} className="message__table-wrap">
              <table className="message__table">
                <thead>
                  <tr>
                    {block.headers.map((header: AnyRecord) => (
                      <th key={header.id}>{header.text}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {block.rows.map((row: AnyRecord) => (
                    <tr key={row.id}>
                      {row.cells.map((cell: AnyRecord) => (
                        <td key={cell.id}>{cell.text}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        if (block.type === "rule") {
          return <hr key={block.id} className="message__rule" />;
        }
        return <p key={block.id}>{renderSegments(block.segments)}</p>;
      })}
    </div>
  );
}

function RunInspector({ client }: { client: Client }) {
  const copy = client.copy.value;
  const run = client.currentRun.value;
  const runs = client.currentRuns.value || [];

  return (
    <div className="trace-sidebar__body">
      {client.state.showRunHistory && (runs.length > 1 || client.currentRunsLoading.value || client.currentRunsError.value) ? (
        <section className="run-history" aria-live="polite">
          <div className="run-history__title">
            <span>{copy.runHistory.title}</span>
            {client.currentRunsLoading.value ? <small>{copy.runHistory.loading}</small> : null}
            {!client.currentRunsLoading.value && client.currentRunsError.value ? <small>{copy.runHistory.unavailable}</small> : null}
          </div>
          {runs.length ? (
            <label className="run-history__select">
              <span className="sr-only">{copy.runHistory.select}</span>
              <Select
                value={run?.runId || ""}
                options={runs.map((item: AnyRecord, index: number) => ({
                  value: item.runId,
                  label: runOptionLabel(copy, item, index),
                }))}
                onChange={(value) => client.selectRun(value)}
              />
            </label>
          ) : null}
        </section>
      ) : null}

      {client.state.showWorkState && client.currentWorkState.value ? (
        <WorkStateCard client={client} workState={client.currentWorkState.value} />
      ) : null}

      <RunDetailsPanel client={client} run={run} />
    </div>
  );
}

function WorkStateCard({ client, workState }: { client: Client; workState: AnyRecord }) {
  const copy = client.copy.value;
  const objective = workState.objective || workState.title || workState.current_task || copy.runSummary.fallbackObjective;
  const status = workState.status || workState.phase || "active";

  return (
    <Card size="small" className="work-state-card">
      <Space direction="vertical" size={8}>
        <Typography.Text type="secondary">{copy.workState?.currentTask || copy.runSummary.objective}</Typography.Text>
        <Typography.Title level={5}>{objective}</Typography.Title>
        <Tag color={runStatusColor(status)}>{status}</Tag>
        {Array.isArray(workState.next_steps) && workState.next_steps.length ? (
          <ul>
            {workState.next_steps.slice(0, 4).map((step: string, index: number) => (
              <li key={`${step}-${index}`}>{step}</li>
            ))}
          </ul>
        ) : null}
        <Space wrap>
          <Button size="small" onClick={() => client.resumeFollowUp(copy.workState?.continuePrompt || "continue")}>
            {copy.workState?.continue || "Continue"}
          </Button>
          <Button size="small" onClick={() => client.runVerification(copy.workState?.verifyPrompt || "verify")}>
            {copy.workState?.verify || "Verify"}
          </Button>
        </Space>
      </Space>
    </Card>
  );
}

function RunDetailsPanel({ client, run }: { client: Client; run: AnyRecord | null }) {
  const copy = client.copy.value;
  if (!run) {
    return <div className="run-trace__empty">{copy.trace?.noRun || copy.runHistory.unavailable}</div>;
  }

  return (
    <div className="run-details-panel">
      {client.state.showRunSummary ? <RunSummaryCard copy={copy} run={run} cleanupWorktreeSandbox={client.cleanupWorktreeSandbox} /> : null}
      {client.state.showRunTimeline ? <RunTimeline copy={copy} events={client.currentRunTimeline.value || []} /> : null}
      {client.state.showRunTrace ? (
        <RunTraceViewer
          copy={copy}
          run={run}
          cancelRun={client.cancelRun}
          revertFileChange={client.revertRunFileChange}
        />
      ) : null}
    </div>
  );
}

function RunSummaryCard({
  copy,
  run,
  cleanupWorktreeSandbox,
}: {
  copy: AnyRecord;
  run: AnyRecord;
  cleanupWorktreeSandbox: (run: AnyRecord) => void;
}) {
  const summary = run.summary || {};
  const metricItems = [
    {
      key: "status",
      label: copy.runSummary.status,
      children: summary.status || run.status,
    },
    ...(summary.duration
      ? [
          {
            key: "duration",
            label: copy.runSummary.duration,
            children: summary.duration,
          },
        ]
      : []),
    ...(Array.isArray(summary.tools)
      ? [
          {
            key: "tools",
            label: copy.runSummary.tools,
            children: summary.tools.length,
          },
        ]
      : []),
  ];

  return (
    <section className="run-summary-card" data-status={run.status || "unknown"}>
      <header className="run-summary-card__header">
        <div className="run-summary-card__title">
          <span className="run-summary-card__eyebrow">{copy.runSummary.title || "Run Summary"}</span>
          <strong>{summary.objective || summary.title || copy.runSummary.fallbackObjective}</strong>
        </div>
        <div className="run-summary-card__actions">
          <Tag className="run-summary-card__status" color={runStatusColor(run.status)} data-status={run.status || "unknown"}>
            {copy.run.statusLabels?.[run.status] || run.status}
          </Tag>
          {run.worktreeSandbox?.cleanupSupported ? (
            <Button className="run-summary-card__copy" size="small" onClick={() => cleanupWorktreeSandbox(run)}>
              {copy.runSummary.cleanupSandbox || "Cleanup sandbox"}
            </Button>
          ) : null}
        </div>
      </header>
      <div className="run-summary-card__body">
        {run.summaryLoading ? <div className="run-summary-card__message">{copy.runSummary.loading || "Loading..."}</div> : null}
        {run.summaryError ? <div className="run-summary-card__message" data-tone="error">{run.summaryError}</div> : null}
        <Descriptions className="run-summary-card__metrics" size="small" column={1} items={metricItems} />
        {summary.result || summary.final_answer ? (
          <p className="run-summary-card__note">{summary.result || summary.final_answer}</p>
        ) : null}
      </div>
    </section>
  );
}

function RunTimeline({ copy, events }: { copy: AnyRecord; events: AnyRecord[] }) {
  return (
    <Card size="small" className="run-timeline" title={copy.timeline?.title || copy.runHistory.title}>
      {events.length ? (
        <Timeline
          items={events.map((event) => ({
            color: event.tone === "error" ? "red" : event.tone === "success" ? "green" : "blue",
            children: (
              <div>
                <strong>{event.label || event.eventType}</strong>
                {event.detail ? <Typography.Paragraph type="secondary">{event.detail}</Typography.Paragraph> : null}
              </div>
            ),
          }))}
        />
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
      )}
    </Card>
  );
}

function RunTraceViewer({
  copy,
  run,
  cancelRun,
  revertFileChange,
}: {
  copy: AnyRecord;
  run: AnyRecord;
  cancelRun: (run: AnyRecord) => void;
  revertFileChange: (run: AnyRecord, change: AnyRecord) => void;
}) {
  const artifacts = run.artifacts || [];
  const events = run.rawEvents || run.events || [];
  const parts = run.parts || [];
  const fileChanges = run.fileChanges || [];

  function exportDebugJson() {
    const blob = new Blob([JSON.stringify({ run, exported_at: new Date().toISOString() }, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${run.runId || "run"}-trace.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  const items = [
    {
      key: "artifacts",
      label: `${copy.trace.artifactHeading || copy.trace.artifacts} (${artifacts.length})`,
      children: artifacts.length ? (
        <List
          dataSource={artifacts}
          renderItem={(artifact: AnyRecord) => (
            <List.Item>
              <List.Item.Meta
                avatar={<Tag color={runStatusColor(artifact.status)}>{artifact.status || artifact.kind || artifact.type}</Tag>}
                title={artifact.title || artifact.name || artifact.toolName || artifact.kind || artifact.type}
                description={artifact.detail || artifact.summary || artifact.path || artifact.message}
              />
            </List.Item>
          )}
        />
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ),
    },
    {
      key: "events",
      label: `${copy.trace.events || "Events"} (${events.length})`,
      children: events.length ? (
        <Timeline
          items={events.slice(-120).map((event: AnyRecord) => ({
            color: event.status === "failed" || event.tone === "error" ? "red" : "blue",
            children: (
              <Collapse
                className="run-trace__event-collapse"
                size="small"
                ghost
                items={[
                  {
                    key: event.id || event.eventType || event.type || "event",
                    label: event.label || event.eventType || event.type,
                    children: <pre>{JSON.stringify(event.payload || event, null, 2)}</pre>,
                  },
                ]}
              />
            ),
          }))}
        />
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ),
    },
    {
      key: "parts",
      label: `${copy.trace.parts} (${parts.length})`,
      children: parts.length ? (
        <Collapse
          items={parts.map((part: AnyRecord, index: number) => ({
            key: part.id || index,
            label: part.title || part.type || `${copy.trace.parts} ${index + 1}`,
            children: <pre>{part.text || part.content || JSON.stringify(part, null, 2)}</pre>,
          }))}
        />
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ),
    },
    {
      key: "files",
      label: `${copy.runSummary.diffSummary || "Files"} (${fileChanges.length})`,
      children: fileChanges.length ? (
        <List
          dataSource={fileChanges}
          renderItem={(change: AnyRecord) => (
            <List.Item
              actions={[
                change.revertSupported ? (
                  <Button size="small" onClick={() => revertFileChange(run, change)}>
                    {copy.runFileInspector?.revert || "Revert"}
                  </Button>
                ) : null,
              ].filter(Boolean)}
            >
              <List.Item.Meta title={change.path || change.label} description={change.status || change.kind} />
            </List.Item>
          )}
        />
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ),
    },
  ];

  return (
    <section className="run-trace" data-status={run.status || "unknown"}>
      <header className="run-trace__header">
        <div className="run-trace__title">
          <span className="run-trace__eyebrow">{copy.trace.title}</span>
          <strong>{run.runId}</strong>
        </div>
        <div className="run-trace__actions">
          <Tag className="run-trace__status" color={runStatusColor(run.status)} data-status={run.status || "unknown"}>{run.status}</Tag>
          <Button className="run-summary-card__copy" size="small" onClick={exportDebugJson}>
            {copy.trace.exportDebug}
          </Button>
          {run.status === "running" ? (
            <Button className="run-trace__cancel" size="small" danger disabled={run.cancelPending} onClick={() => cancelRun(run)}>
              {copy.trace.cancelRun}
            </Button>
          ) : null}
        </div>
      </header>
      <div className="run-trace__body">
        {run.traceError ? <div className="run-summary-card__message" data-tone="error">{run.traceError}</div> : null}
        {run.traceLoading ? <div className="run-summary-card__message">{copy.trace.loading || "Loading..."}</div> : null}
        <div className="run-trace__summary">
          <Tag>{events.length} {copy.trace.events || "events"}</Tag>
          <Tag>{artifacts.length} {copy.trace.artifacts}</Tag>
          <Tag>{parts.length} {copy.trace.parts}</Tag>
          <Tag>{fileChanges.length} {copy.runSummary.diffSummary || "files"}</Tag>
        </div>
        <Collapse className="run-trace__sections" size="small" defaultActiveKey={["artifacts"]} items={items} />
      </div>
    </section>
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

function SettingsSectionTitle({ children }: { children: React.ReactNode }) {
  return <Typography.Title className="settings-section-title" level={5}>{children}</Typography.Title>;
}

function SettingsCard({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <Card size="small" className={["settings-card", className].filter(Boolean).join(" ")}>{children}</Card>;
}

function SettingsStatus({ message, type = "info" }: { message?: string; type?: "info" | "success" | "warning" | "error" }) {
  return message ? <Alert className="settings-inline-status" type={type} showIcon message={message} /> : null;
}

function SettingsRow({
  title,
  description,
  children,
  className = "",
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={["settings-row", className].filter(Boolean).join(" ")}>
      <div className="settings-row__copy">
        <Typography.Text strong>{title}</Typography.Text>
        {description ? <Typography.Text type="secondary">{description}</Typography.Text> : null}
      </div>
      {children ? <div className="settings-row__control">{children}</div> : null}
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

function ProviderSettings({ client }: { client: Client }) {
  const copy = client.copy.value;
  const state = client.settingsState;
  const providers = (state.providers || {}) as AnyRecord;
  const providerCopy = copy.settings.providers || {};
  const selectedConnectProvider =
    [...(providers.available || []), ...(providers.connected || [])].find((provider: AnyRecord) => provider.id === state.connectForm.providerId) || null;
  const showCodexAuthCard =
    hasConnectedProvider(state, "openai-codex") ||
    state.codexAuthLoading ||
    state.codexAuth?.configured ||
    Boolean(state.codexAuth?.userCode || state.codexAuthNotice || state.codexAuthError);
  const showCopilotAuthCard =
    hasConnectedProvider(state, "copilot") ||
    state.copilotAuthLoading ||
    state.copilotAuth?.configured ||
    Boolean(state.copilotAuth?.userCode || state.copilotAuthNotice || state.copilotAuthError);
  const codexAuthStatusLabel = authStatusLabel(providerCopy.codexAuth, state.codexAuth, state.codexAuthLoading);
  const copilotAuthStatusLabel = authStatusLabel(providerCopy.copilotAuth, state.copilotAuth, state.copilotAuthLoading);
  const codexAuthDescription = codexDescription(copy, state);
  const copilotAuthDescription = copilotDescription(copy, state);
  const selectedConnectProviderRequiresApiKey = selectedConnectProvider?.requires_api_key !== false || selectedConnectProvider?.api_key_optional === true;

  return (
    <section className="settings-page">
      <SettingsStatus message={state.providersLoading ? providerCopy.loading || "Loading providers..." : ""} />
      <SettingsStatus message={state.providersNotice} />
      <SettingsStatus message={state.providersError} type="error" />

      {showCodexAuthCard ? (
        <>
          <SettingsSectionTitle>{providerCopy.codexAuth?.title || "OpenAI Codex auth"}</SettingsSectionTitle>
          <SettingsStatus message={state.codexAuthNotice} />
          <SettingsStatus message={state.codexAuthError} type="error" />
          <AuthProviderCard
            mark="Cx"
            name={providerCopy.codexAuth?.name || "OpenAI Codex"}
            status={codexAuthStatusLabel}
            description={codexAuthDescription}
            loading={state.codexAuthLoading}
            configured={state.codexAuth?.configured}
            copy={providerCopy.codexAuth || {}}
            auth={state.codexAuth || {}}
            onRefresh={client.loadCodexAuthStatus}
            onLogin={client.startCodexAuthLogin}
            onLogout={client.logoutCodexAuth}
          />
        </>
      ) : null}

      {showCopilotAuthCard ? (
        <>
          <SettingsSectionTitle>{providerCopy.copilotAuth?.title || "GitHub Copilot auth"}</SettingsSectionTitle>
          <SettingsStatus message={state.copilotAuthNotice} />
          <SettingsStatus message={state.copilotAuthError} type="error" />
          <AuthProviderCard
            mark="Gh"
            name={providerCopy.copilotAuth?.name || "GitHub Copilot"}
            status={copilotAuthStatusLabel}
            description={copilotAuthDescription}
            loading={state.copilotAuthLoading}
            configured={state.copilotAuth?.configured}
            copy={providerCopy.copilotAuth || {}}
            auth={state.copilotAuth || {}}
            onRefresh={client.loadCopilotAuthStatus}
            onLogin={client.startCopilotAuthLogin}
            onLogout={client.logoutCopilotAuth}
          />
        </>
      ) : null}

      <SettingsSectionTitle>{providerCopy.connectedTitle || "Connected providers"}</SettingsSectionTitle>
      <SettingsCard className="provider-card">
        <List
          className="provider-row-list"
          dataSource={providers.connected || []}
          locale={{
            emptyText: (
              <div className="provider-row provider-row--empty">
                <div>
                  <strong>{providerCopy.noConnectedTitle || "No connected providers"}</strong>
                  <span>{providerCopy.noConnectedDescription || ""}</span>
                </div>
              </div>
            ),
          }}
          renderItem={(provider: AnyRecord) => {
            const credentials = providerCredentials(state, provider);
            const effectiveCredentialId = providerEffectiveCredentialId(provider);
            return (
              <List.Item key={provider.id} className="provider-row">
                <div className="provider-row__main">
                  <span className="provider-row__mark" aria-hidden="true">{providerMark(provider)}</span>
                  <div>
                    <div className="provider-row__title">
                      <strong>{provider.name || provider.id}</strong>
                      {provider.is_default ? <Tag className="provider-row__badge">{providerCopy.currentBadge || "Current"}</Tag> : null}
                      {provider.preset_name && provider.preset_name !== provider.name ? <Tag className="provider-row__badge">{provider.preset_name}</Tag> : null}
                      {provider.provider === "openai-codex" && !state.codexAuth?.configured ? <Tag className="provider-row__badge">{providerCopy.codexAuth?.notConfigured || "Not configured"}</Tag> : null}
                      {provider.provider === "copilot" && !state.copilotAuth?.configured ? <Tag className="provider-row__badge">{providerCopy.copilotAuth?.notConfigured || "Not configured"}</Tag> : null}
                    </div>
                    <span>{providerDescription(copy, state, provider)}</span>
                    {provider.credential_preview ? (
                      <span className="provider-row__credential">
                        {typeof providerCopy.credentialLabel === "function"
                          ? providerCopy.credentialLabel(provider.credential_label || provider.name, provider.credential_preview, credentialSourceLabel(copy, provider))
                          : provider.credential_preview}
                      </span>
                    ) : provider.requires_api_key ? (
                      <span className="provider-row__credential provider-row__credential--missing">{providerCopy.missingCredential || "Missing credential"}</span>
                    ) : null}
                    {credentials.length > 1 ? (
                      <Form.Item className="provider-row__select" label={providerCopy.credentialSelect || "Credential"}>
                        <Select
                          value={effectiveCredentialId}
                          disabled={state.providersLoading}
                          options={credentials.map((credential: AnyRecord) => ({
                            value: credential.id,
                            label: `${credential.label || credential.name || credential.id}${credential.secret_preview ? ` - ${credential.secret_preview}` : ""}`,
                          }))}
                          onChange={(value) => client.setProviderCredential(provider, value)}
                        />
                      </Form.Item>
                    ) : null}
                  </div>
                </div>
                <div className="provider-row__actions provider-row__actions--connected">
                  {effectiveCredentialId ? (
                    <Button size="small" danger disabled={state.providersLoading} onClick={() => client.deleteCredential(provider, effectiveCredentialId)}>
                      {providerCopy.deleteCredential || "Delete credential"}
                    </Button>
                  ) : null}
                  <Button size="small" disabled={state.providersLoading} onClick={() => client.disconnectProvider(provider)}>
                    {providerCopy.disconnect || "Disconnect"}
                  </Button>
                </div>
              </List.Item>
            );
          }}
        />
      </SettingsCard>

      <SettingsSectionTitle>{providerCopy.popularTitle || "Available providers"}</SettingsSectionTitle>
      <SettingsCard className="provider-card">
        <List
          className="provider-row-list"
          dataSource={providers.available || []}
          locale={{
            emptyText: (
              <div className="provider-row provider-row--empty">
                <div>
                  <strong>{providerCopy.noAvailableTitle || "No available providers"}</strong>
                  <span>{providerCopy.noAvailableDescription || ""}</span>
                </div>
              </div>
            ),
          }}
          renderItem={(provider: AnyRecord) => {
            const oauth = provider.auth_type === "openai_codex_oauth" || provider.auth_type === "github_copilot_oauth";
            return (
              <List.Item key={provider.id} className="provider-row provider-row--stacked">
                <div className="provider-row__content">
                  <div className="provider-row__main">
                    <span className="provider-row__mark" aria-hidden="true">{providerMark(provider)}</span>
                    <div>
                      <div className="provider-row__title">
                        <strong>{provider.name || provider.id}</strong>
                        <Tag className="provider-row__badge">{providerCopy.builtInBadge || "Built-in"}</Tag>
                        {provider.connected_count ? <Tag className="provider-row__badge">{typeof providerCopy.connectedCount === "function" ? providerCopy.connectedCount(provider.connected_count) : provider.connected_count}</Tag> : null}
                      </div>
                      <span>{provider.default_base_url || provider.description || provider.id}</span>
                    </div>
                  </div>
                  <Button type="primary" disabled={state.providersLoading} onClick={() => (oauth ? client.connectOAuthProvider(provider) : client.beginProviderConnect(provider))}>
                    {oauth ? providerCopy.connectOAuth || "Connect OAuth" : providerCopy.connect || "Connect"}
                  </Button>
                </div>
              </List.Item>
            );
          }}
        />
      </SettingsCard>

      {selectedConnectProvider ? (
        <div className="provider-connect-dialog" role="dialog" aria-modal="true">
          <header className="provider-connect-dialog__top">
            <Button type="text" aria-label={providerCopy.backAria || "Back"} icon={<ArrowLeftOutlined />} onClick={client.cancelProviderConnect} />
            <Button type="text" aria-label={providerCopy.closeAria || "Close"} icon={<CloseOutlined />} onClick={client.cancelProviderConnect} />
          </header>
          <Form className="provider-connect-dialog__body" layout="vertical" onFinish={() => client.saveProviderConnection()}>
            <div className="provider-connect-dialog__title">
              <span className="provider-row__mark" aria-hidden="true">{providerMark(selectedConnectProvider)}</span>
              <h3>{typeof providerCopy.dialogTitle === "function" ? providerCopy.dialogTitle(selectedConnectProvider.name) : `Connect ${selectedConnectProvider.name}`}</h3>
            </div>
            <p>{typeof providerCopy.dialogDescription === "function" ? providerCopy.dialogDescription(selectedConnectProvider.name) : ""}</p>
            <Form.Item className="provider-connect-field" label={providerCopy.nameLabel || "Name"}>
              <Input value={state.connectForm.name} placeholder={selectedConnectProvider.name} autoComplete="off" onChange={(event) => (state.connectForm.name = event.target.value)} />
            </Form.Item>
            {selectedConnectProviderRequiresApiKey ? (
              <Form.Item className="provider-connect-field" label={typeof providerCopy.apiKeyLabel === "function" ? providerCopy.apiKeyLabel(selectedConnectProvider.name) : "API key"}>
                <Input.Password value={state.connectForm.apiKey} placeholder="API key" autoComplete="off" onChange={(event) => (state.connectForm.apiKey = event.target.value)} />
              </Form.Item>
            ) : null}
            <Button type="link" className="provider-connect-dialog__advanced" onClick={() => (state.connectForm.showAdvanced = !state.connectForm.showAdvanced)}>
              {state.connectForm.showAdvanced ? providerCopy.advancedHide || "Hide advanced" : providerCopy.advancedShow || "Advanced"}
            </Button>
            {state.connectForm.showAdvanced ? (
              <Form.Item className="provider-connect-field" label="Base URL">
                <Input value={state.connectForm.baseUrl} spellCheck={false} onChange={(event) => (state.connectForm.baseUrl = event.target.value)} />
              </Form.Item>
            ) : null}
            <Button className="provider-connect-dialog__submit" type="primary" htmlType="submit" loading={state.providersLoading} disabled={state.providersLoading}>
              {providerCopy.submit || "Save"}
            </Button>
          </Form>
        </div>
      ) : null}
    </section>
  );
}

function ModelSettings({ client }: { client: Client }) {
  const copy = client.copy.value;
  const state = client.settingsState;
  const modelCopy = copy.settings.models || {};
  const providers = state.models?.providers || [];
  const selectedProvider = providers.find((provider: AnyRecord) => provider.id === state.selectedTextProviderId) || providers[0] || null;
  const selectedProviderId = selectedProvider?.id || "";
  const selectedModel = selectedProvider ? state.modelSelections[selectedProvider.id] || selectedProvider.selected_model || "" : "";
  const selectedReasoning = selectedProvider ? state.reasoningSelections[selectedProvider.id] || selectedProvider.reasoning_effort || "" : "";

  return (
    <section className="settings-page">
      <SettingsStatus message={state.modelsLoading ? modelCopy.loading || "Loading models..." : ""} />
      <SettingsStatus message={state.modelsNotice} />
      <SettingsStatus message={state.modelsError} type="error" />
      <SettingsStatus message={state.mediaError} type="error" />

      <SettingsSectionTitle>{modelCopy.textTitle || "Text model"}</SettingsSectionTitle>
      {providers.length === 0 ? (
        <SettingsCard>
          <SettingsRow title={modelCopy.noProvidersTitle || "No providers"} description={modelCopy.noProvidersDescription || ""}>
            <Tag>{modelCopy.noProvidersBadge || ""}</Tag>
          </SettingsRow>
        </SettingsCard>
      ) : null}

      {selectedProvider ? (
        <SettingsCard className="model-provider-card">
          <div className="model-provider-card__header">
            <div className="provider-row__main">
              <span className="provider-row__mark" aria-hidden="true">{providerMark(selectedProvider)}</span>
              <div>
                <div className="provider-row__title">
                  <strong>{selectedProvider.name || selectedProvider.id}</strong>
                  {selectedProvider.is_default ? <Tag className="provider-row__badge">{modelCopy.currentBadge || "Current"}</Tag> : null}
                </div>
                <span>{selectedProvider.selected_model || modelCopy.noModel || "No model selected"}</span>
              </div>
            </div>
          </div>

          <div className="model-select-row">
            <Form.Item className="ant-field-label" label={modelCopy.providerChoice || "Provider"}>
              <Select
                value={selectedProviderId}
                disabled={state.modelsLoading}
                options={providers.map((provider: AnyRecord) => ({
                  value: provider.id,
                  label: `${provider.name || provider.id}${provider.is_default ? ` (${modelCopy.active || "active"})` : ""}`,
                }))}
                onChange={(value) => {
                  state.selectedTextProviderId = value;
                  state.modelSelections[value] = "";
                }}
              />
            </Form.Item>
            <Form.Item className="ant-field-label" label={modelCopy.modelChoice || "Model"}>
              <Select
                value={selectedModel}
                disabled={state.modelsLoading}
                options={[
                  { value: "", label: modelCopy.noModel || "No model" },
                  ...modelOptionsForProvider(selectedProvider, selectedModel).map((model: string) => ({
                    value: model,
                    label: textModelOptionLabel(copy, selectedProvider, model),
                  })),
                ]}
                onChange={(value) => (state.modelSelections[selectedProvider.id] = value)}
              />
            </Form.Item>
            <Form.Item className="ant-field-label" label={modelCopy.reasoningChoice || "Reasoning"}>
              <Select
                value={selectedReasoning}
                disabled={state.modelsLoading}
                options={[
                  { value: "", label: modelCopy.reasoningDefault || "Default" },
                  { value: "none", label: modelCopy.reasoningNone || "None" },
                  { value: "minimal", label: modelCopy.reasoningMinimal || "Minimal" },
                  { value: "low", label: modelCopy.reasoningLow || "Low" },
                  { value: "medium", label: modelCopy.reasoningMedium || "Medium" },
                  { value: "high", label: modelCopy.reasoningHigh || "High" },
                  { value: "xhigh", label: modelCopy.reasoningXhigh || "XHigh" },
                ]}
                onChange={(value) => (state.reasoningSelections[selectedProvider.id] = value)}
              />
            </Form.Item>
            <Button type="primary" disabled={state.modelsLoading || !selectedModel} loading={state.modelsLoading} onClick={() => client.selectModel(selectedProvider.id, selectedModel, selectedReasoning)}>
              {modelCopy.select || modelCopy.apply || "Apply"}
            </Button>
          </div>

          <div className="custom-model-row">
            <Form.Item className="ant-field-label" label={modelCopy.customModel || "Custom model"}>
              <Input value={state.customModels[selectedProvider.id] || ""} placeholder={modelCopy.customPlaceholder || ""} spellCheck={false} onChange={(event) => (state.customModels[selectedProvider.id] = event.target.value)} />
            </Form.Item>
            <Button disabled={state.modelsLoading || !state.customModels[selectedProvider.id]} onClick={() => client.selectModel(selectedProvider.id, state.customModels[selectedProvider.id], selectedReasoning)}>
              {modelCopy.useCustom || "Use custom"}
            </Button>
          </div>
        </SettingsCard>
      ) : null}

      <SettingsSectionTitle>{modelCopy.mediaTitle || "Media models"}</SettingsSectionTitle>
      {(state.media.providers || []).length === 0 ? (
        <SettingsCard>
          <SettingsRow title={modelCopy.noProvidersTitle || "No providers"} description={modelCopy.mediaNoProvidersDescription || ""}>
            <Tag>{modelCopy.noProvidersBadge || ""}</Tag>
          </SettingsRow>
        </SettingsCard>
      ) : null}

      {mediaModelCategories(copy).map((category) => {
        const selection = state.mediaSelections[category.key] || {};
        const providerModels = mediaModelsForProvider(state, category.key, selection.providerId, selection.model);
        return (
          <SettingsCard key={category.key} className="model-provider-card">
            <div className="model-provider-card__header">
              <div className="provider-row__main">
                <span className="provider-row__mark" aria-hidden="true">{category.mark}</span>
                <div>
                  <div className="provider-row__title">
                    <strong>{category.title}</strong>
                    {state.media.sections?.[category.key]?.enabled ? <Tag className="provider-row__badge">{modelCopy.enabledBadge || "Enabled"}</Tag> : null}
                  </div>
                  <span>{state.media.sections?.[category.key]?.model || modelCopy.noModel || "No model"}</span>
                </div>
              </div>
            </div>
            <SettingsRow title={modelCopy.enableMediaModel || "Enable media model"} description={category.description}>
              <Switch
                aria-label={modelCopy.enableMediaModel || "Enable media model"}
                checked={Boolean(selection.enabled)}
                onChange={(checkedValue) => {
                  selection.enabled = checkedValue;
                  if (selection.enabled && !selection.providerId) {
                    selection.providerId = state.media.providers?.[0]?.id || "";
                  }
                  if (selection.enabled) {
                    selection.model = "";
                  }
                }}
              />
            </SettingsRow>
            <div className="model-select-row">
              {selection.enabled ? (
                <Form.Item className="ant-field-label" label={modelCopy.providerChoice || "Provider"}>
                  <Select
                    value={selection.providerId || ""}
                    disabled={state.mediaLoading}
                    options={(state.media.providers || []).map((provider: AnyRecord) => ({
                      value: provider.id,
                      label: provider.name || provider.id,
                    }))}
                    onChange={(value) => {
                      selection.providerId = value;
                      selection.model = "";
                    }}
                  />
                </Form.Item>
              ) : null}
              {selection.enabled ? (
                <Form.Item className="ant-field-label" label={modelCopy.modelChoice || "Model"}>
                  <Select
                    value={selection.model || ""}
                    disabled={state.mediaLoading}
                    options={providerModels.map((model: string) => ({ value: model, label: model }))}
                    onChange={(value) => (selection.model = value)}
                  />
                </Form.Item>
              ) : null}
              <Button disabled={state.mediaLoading || (selection.enabled && !selection.providerId)} loading={state.mediaLoading} onClick={() => client.saveMediaModel(category.key)}>
                {modelCopy.saveMediaModel || modelCopy.apply || "Save"}
              </Button>
            </div>
            {selection.enabled ? (
              <div className="custom-model-row">
                <Form.Item className="ant-field-label" label={modelCopy.customModel || "Custom model"}>
                  <Input value={state.mediaCustomModels[category.key] || ""} placeholder={modelCopy.customPlaceholder || ""} disabled={state.mediaLoading} spellCheck={false} onChange={(event) => (state.mediaCustomModels[category.key] = event.target.value)} />
                </Form.Item>
                <Button disabled={state.mediaLoading || !state.mediaCustomModels[category.key]} onClick={() => client.saveMediaModel(category.key, state.mediaCustomModels[category.key])}>
                  {modelCopy.useCustom || "Use custom"}
                </Button>
              </div>
            ) : null}
          </SettingsCard>
        );
      })}
    </section>
  );
}

function ChannelSettings({ client }: { client: Client }) {
  const state = client.settingsState;
  const copy = client.copy.value;
  const channelCopy = copy.settings.channels || {};
  const channels: AnyRecord = state.channels || {};
  const selectedConnectChannel =
    [...(channels.available || []), ...(channels.connected || [])].find((channel: AnyRecord) => (channel.type || channel.id) === state.channelConnectForm.type) || null;

  return (
    <section className="settings-page">
      <SettingsStatus message={state.channelsLoading ? channelCopy.loading || "Loading channels..." : ""} />
      <SettingsStatus message={state.channelsNotice} />
      <SettingsStatus message={state.channelsError} type="error" />

      <SettingsSectionTitle>{channelCopy.connectedTitle || "Connected channels"}</SettingsSectionTitle>
      <SettingsCard className="provider-card">
        <List
          className="provider-row-list"
          dataSource={channels.connected || []}
          locale={{
            emptyText: (
              <div className="provider-row provider-row--empty">
                <div>
                  <strong>{channelCopy.noConnectedTitle || "No connected channels"}</strong>
                  <span>{channelCopy.noConnectedDescription || ""}</span>
                </div>
              </div>
            ),
          }}
          renderItem={(channel: AnyRecord) => (
            <List.Item key={channel.id || channel.type} className="provider-row">
              <div className="provider-row__main">
                <span className="provider-row__mark" aria-hidden="true">{providerMark(channel)}</span>
                <div>
                  <div className="provider-row__title">
                    <strong>{channel.name || channel.type || channel.id}</strong>
                    <Tag className="provider-row__badge">{channelCopy.connectedBadge || "Connected"}</Tag>
                    {channel.enabled ? <Tag className="provider-row__badge">{channelCopy.enabledBadge || "Enabled"}</Tag> : null}
                  </div>
                  <span>{channel.description || channel.status || channel.id}</span>
                </div>
              </div>
              <Button disabled={state.channelsLoading} onClick={() => client.disconnectChannel(channel)}>
                {channelCopy.disconnect || "Disconnect"}
              </Button>
            </List.Item>
          )}
        />
      </SettingsCard>

      <SettingsSectionTitle>{channelCopy.availableTitle || "Available channels"}</SettingsSectionTitle>
      <SettingsCard className="provider-card">
        <List
          className="provider-row-list"
          dataSource={channels.available || []}
          locale={{
            emptyText: (
              <div className="provider-row provider-row--empty">
                <div>
                  <strong>{channelCopy.noAvailableTitle || "No available channels"}</strong>
                  <span>{channelCopy.noAvailableDescription || ""}</span>
                </div>
              </div>
            ),
          }}
          renderItem={(channel: AnyRecord) => (
            <List.Item key={channel.id || channel.type} className="provider-row provider-row--stacked">
              <div className="provider-row__content">
                <div className="provider-row__main">
                  <span className="provider-row__mark" aria-hidden="true">{providerMark(channel)}</span>
                  <div>
                    <div className="provider-row__title">
                      <strong>{channel.name || channel.type || channel.id}</strong>
                      <Tag className="provider-row__badge">{channelCopy.builtInBadge || "Built-in"}</Tag>
                    </div>
                    <span>{channel.description || channel.id}</span>
                  </div>
                </div>
                <Button type="primary" disabled={state.channelsLoading} onClick={() => client.beginChannelConnect(channel)}>
                  {channelCopy.add || channelCopy.connect || "Add"}
                </Button>
              </div>
            </List.Item>
          )}
        />
      </SettingsCard>

      {selectedConnectChannel ? (
        <div className="provider-connect-dialog" role="dialog" aria-modal="true">
          <header className="provider-connect-dialog__top">
            <Button type="text" aria-label={channelCopy.backAria || "Back"} icon={<ArrowLeftOutlined />} onClick={client.cancelChannelConnect} />
            <Button type="text" aria-label={channelCopy.closeAria || "Close"} icon={<CloseOutlined />} onClick={client.cancelChannelConnect} />
          </header>
          <Form className="provider-connect-dialog__body" layout="vertical" onFinish={() => client.saveChannelConnection()}>
            <div className="provider-connect-dialog__title">
              <span className="provider-row__mark" aria-hidden="true">{providerMark(selectedConnectChannel)}</span>
              <h3>{typeof channelCopy.dialogTitle === "function" ? channelCopy.dialogTitle(selectedConnectChannel.name) : `Connect ${selectedConnectChannel.name}`}</h3>
            </div>
            <p>{typeof channelCopy.dialogDescription === "function" ? channelCopy.dialogDescription(selectedConnectChannel.name) : ""}</p>
            <Form.Item className="provider-connect-field" label={channelCopy.nameLabel || "Name"}>
              <Input value={state.channelConnectForm.name} placeholder={channelCopy.namePlaceholder || ""} autoComplete="off" onChange={(event) => (state.channelConnectForm.name = event.target.value)} />
            </Form.Item>
            <Form.Item className="provider-connect-field" label={typeof channelCopy.tokenLabel === "function" ? channelCopy.tokenLabel(selectedConnectChannel.name) : "Token"}>
              <Input.Password value={state.channelConnectForm.token} placeholder="Token" autoComplete="off" onChange={(event) => (state.channelConnectForm.token = event.target.value)} />
            </Form.Item>
            <Button className="provider-connect-dialog__submit" type="primary" htmlType="submit" loading={state.channelsLoading} disabled={state.channelsLoading}>
              {channelCopy.submit || "Save"}
            </Button>
          </Form>
        </div>
      ) : null}
    </section>
  );
}

function McpSettings({ client }: { client: Client }) {
  const state = client.settingsState;
  const copy = client.copy.value;
  const mcpCopy = copy.settings.mcp || {};
  const form = state.mcpForm;
  const toolGroups: AnyRecord[] = mcpToolGroups(copy, state);
  const runtimeStatus = mcpRuntimeStatus(copy, state);

  return (
    <section className="settings-page">
      <SettingsStatus message={state.mcpLoading ? mcpCopy.loading || "Loading MCP..." : ""} />
      <SettingsStatus message={state.mcpNotice} />
      <SettingsStatus message={state.mcpError} type="error" />

      <SettingsSectionTitle>{mcpCopy.runtimeTitle || "MCP runtime"}</SettingsSectionTitle>
      <SettingsCard className="settings-card--form">
        <SettingsRow title={mcpCopy.runtimeStatus || "Runtime status"} description={runtimeStatus}>
          <Button icon={<ReloadOutlined />} loading={state.mcpLoading} disabled={state.mcpLoading} onClick={client.reloadMcpSettings}>
            {mcpCopy.reload || "Reload"}
          </Button>
        </SettingsRow>
        <SettingsRow title={mcpCopy.connectedTools || "Connected tools"} description={toolGroups.length === 0 ? mcpCopy.noTools || "No tools" : ""} />
        {toolGroups.length ? (
          <div className="mcp-tool-groups">
            {toolGroups.map((group) => (
              <div key={group.serverId} className="mcp-tool-group">
                <Button className="mcp-tool-group__header" type="text" onClick={() => client.toggleMcpToolGroup(group.serverId)}>
                  <span aria-hidden="true">{group.expanded ? "v" : ">"}</span>
                  <strong>{group.serverName}</strong>
                  <small>{typeof mcpCopy.toolCount === "function" ? mcpCopy.toolCount(group.tools.length) : `${group.tools.length} tools`}</small>
                </Button>
                {group.expanded ? (
                  <div className="mcp-tool-group__tools">
                    {group.tools.map((tool: AnyRecord) => <Tag key={tool.fullName} className="mcp-tool-chip">{tool.name}</Tag>)}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        ) : null}
      </SettingsCard>

      <div className="mcp-server-list-screen">
        <div className="mcp-server-list-screen__header">
          <SettingsSectionTitle>{mcpCopy.serversTitle || "MCP servers"}</SettingsSectionTitle>
          <Button type="primary" onClick={client.beginMcpCreate}>
            {mcpCopy.openAdd || mcpCopy.addServer || "Add server"}
          </Button>
        </div>
        <SettingsCard className="provider-card">
          {(state.mcp.servers || []).length === 0 ? (
            <div className="provider-row provider-row--empty">
              <div>
                <strong>{mcpCopy.noServersTitle || "No MCP servers"}</strong>
                <span>{mcpCopy.noServersDescription || ""}</span>
              </div>
            </div>
          ) : null}
          {(state.mcp.servers || []).map((server: AnyRecord) => (
            <div key={server.id} className="schedule-job-row">
              <div className="schedule-job-row__main">
                <div className="provider-row__title">
                  <strong>{server.name || server.id}</strong>
                  <Tag className="provider-row__badge">{server.type || mcpCopy.autoTransport || "auto"}</Tag>
                </div>
                <span>{server.command || server.url || mcpCopy.noEndpoint || ""}</span>
                <span>{typeof mcpCopy.toolsLabel === "function" ? mcpCopy.toolsLabel((server.enabled_tools || []).join(", ")) : (server.enabled_tools || []).join(", ")}</span>
                {server.env_configured ? <span>{typeof mcpCopy.envKeys === "function" ? mcpCopy.envKeys((server.env_keys || []).join(", ")) : (server.env_keys || []).join(", ")}</span> : null}
                {server.headers_configured ? <span>{typeof mcpCopy.headerKeys === "function" ? mcpCopy.headerKeys((server.headers_keys || []).join(", ")) : (server.headers_keys || []).join(", ")}</span> : null}
              </div>
              <div className="schedule-job-row__actions">
                <Button onClick={() => client.beginMcpEdit(server)}>{mcpCopy.edit || "Edit"}</Button>
                <Button danger disabled={state.mcpLoading} onClick={() => client.removeMcpServer(server)}>{mcpCopy.remove || "Remove"}</Button>
              </div>
            </div>
          ))}
        </SettingsCard>
      </div>

      {form.showEditor ? (
        <div className="provider-connect-dialog" role="dialog" aria-modal="true">
          <header className="provider-connect-dialog__top">
            <Button type="text" aria-label={mcpCopy.backToList || "Back"} icon={<ArrowLeftOutlined />} onClick={client.cancelMcpEdit} />
            <Button type="text" aria-label={copy.settings.closeAria || "Close"} icon={<CloseOutlined />} onClick={client.cancelMcpEdit} />
          </header>
          <Form className="provider-connect-dialog__body" layout="vertical" onFinish={() => client.saveMcpServer()}>
            <div className="provider-connect-dialog__title">
              <span className="provider-row__mark" aria-hidden="true">MC</span>
              <h3>{form.editingId ? mcpCopy.editTitle || "Edit MCP server" : mcpCopy.addTitle || "Add MCP server"}</h3>
            </div>
            <p>{mcpCopy.simpleHint || ""}</p>
            <Form.Item className="provider-connect-field" label={mcpCopy.serverId || "Server ID"}>
              <Input value={form.serverId} disabled={Boolean(form.editingId)} spellCheck={false} autoComplete="off" onChange={(event) => (form.serverId = event.target.value)} />
            </Form.Item>
            <Form.Item className="provider-connect-field" label={mcpCopy.transport || "Transport"}>
              <Select
                value={form.type}
                options={[
                  { value: "stdio", label: "stdio" },
                  { value: "sse", label: "sse" },
                  { value: "streamableHttp", label: "streamableHttp" },
                ]}
                onChange={(value) => (form.type = value)}
              />
            </Form.Item>
            {form.type === "stdio" ? (
              <>
                <Form.Item className="provider-connect-field" label={mcpCopy.command || "Command"}>
                  <Input value={form.command} spellCheck={false} autoComplete="off" onChange={(event) => (form.command = event.target.value)} />
                </Form.Item>
                <Form.Item className="provider-connect-field" label={mcpCopy.args || "Args"}>
                  <Input.TextArea value={form.argsText} rows={3} spellCheck={false} onChange={(event) => (form.argsText = event.target.value)} />
                </Form.Item>
              </>
            ) : (
              <Form.Item className="provider-connect-field" label={mcpCopy.url || "URL"}>
                <Input value={form.url} spellCheck={false} autoComplete="off" onChange={(event) => (form.url = event.target.value)} />
              </Form.Item>
            )}

            <div className="mcp-editor__toolbar">
              <Button type="link" className="provider-connect-dialog__advanced" onClick={client.toggleMcpAdvanced}>
                {form.showAdvanced ? mcpCopy.hideAdvanced || "Hide advanced" : mcpCopy.showAdvanced || "Advanced"}
              </Button>
              <Button type="link" className="provider-connect-dialog__advanced" onClick={client.toggleMcpJsonInput}>
                {form.showJsonInput ? mcpCopy.hideJson || "Hide JSON" : mcpCopy.showJson || "Paste JSON"}
              </Button>
            </div>

            {form.showJsonInput ? (
              <div className="mcp-editor__json">
                <Form.Item className="provider-connect-field" label={mcpCopy.configJson || "Config JSON"}>
                  <Input.TextArea value={form.jsonText} rows={7} spellCheck={false} placeholder={mcpCopy.configJsonPlaceholder || ""} onChange={(event) => (form.jsonText = event.target.value)} />
                </Form.Item>
                <Button onClick={client.applyMcpJson}>{mcpCopy.applyJson || "Apply JSON"}</Button>
              </div>
            ) : null}

            {form.showAdvanced ? (
              <div className="mcp-editor__advanced">
                <div className="mcp-editor__section-title">
                  <strong>{mcpCopy.advancedTitle || "Advanced"}</strong>
                  <span>{mcpCopy.advancedHint || ""}</span>
                </div>
                <Form.Item className="provider-connect-field" label={mcpCopy.toolTimeout || "Tool timeout"}>
                  <InputNumber className="settings-control" value={Number(form.toolTimeout || 30)} min={1} step={1} onChange={(value) => (form.toolTimeout = String(value || 30))} />
                </Form.Item>
                <Form.Item className="provider-connect-field" label={mcpCopy.enabledTools || "Enabled tools"}>
                  <Input.TextArea value={form.enabledToolsText} rows={2} spellCheck={false} onChange={(event) => (form.enabledToolsText = event.target.value)} />
                </Form.Item>
                <Form.Item className="provider-connect-field" label={mcpCopy.env || "Environment JSON"}>
                  <Input.TextArea value={form.envJson} rows={3} spellCheck={false} placeholder={mcpCopy.jsonPlaceholder || "{}"} onChange={(event) => (form.envJson = event.target.value)} />
                </Form.Item>
                <Form.Item className="provider-connect-field" label={mcpCopy.headers || "Headers JSON"}>
                  <Input.TextArea value={form.headersJson} rows={3} spellCheck={false} placeholder={mcpCopy.jsonPlaceholder || "{}"} onChange={(event) => (form.headersJson = event.target.value)} />
                </Form.Item>
              </div>
            ) : null}

            <Button className="provider-connect-dialog__submit" type="primary" htmlType="submit" loading={state.mcpLoading} disabled={state.mcpLoading}>
              {form.editingId ? mcpCopy.update || "Update" : mcpCopy.add || "Add"}
            </Button>
          </Form>
        </div>
      ) : null}
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

function NetworkSettings({ client }: { client: Client }) {
  const state = client.settingsState;
  const copy = client.copy.value;
  const networkCopy = copy.settings.network || {};
  const form = state.networkForm;
  const summary = networkSummary(copy, state);

  return (
    <section className="settings-page">
      <SettingsStatus message={state.networkLoading ? networkCopy.loading || "Loading network settings..." : ""} />
      <SettingsStatus message={state.networkNotice} />
      <SettingsStatus message={state.networkError} type="error" />

      <SettingsSectionTitle>{networkCopy.title || "Network"}</SettingsSectionTitle>
      <SettingsCard className="settings-card--form">
        <SettingsRow title={networkCopy.httpProxy?.title || "HTTP proxy"} description={networkCopy.httpProxy?.description || ""} className="settings-row--field">
          <Input value={form.httpProxy} placeholder={networkCopy.proxyPlaceholder || "http://proxy-host:port"} disabled={state.networkLoading} onChange={(event) => (form.httpProxy = event.target.value)} />
        </SettingsRow>
        <SettingsRow title={networkCopy.httpsProxy?.title || "HTTPS proxy"} description={networkCopy.httpsProxy?.description || ""} className="settings-row--field">
          <Input value={form.httpsProxy} placeholder={networkCopy.proxyPlaceholder || "http://proxy-host:port"} disabled={state.networkLoading} onChange={(event) => (form.httpsProxy = event.target.value)} />
        </SettingsRow>
        <SettingsRow title={networkCopy.noProxy?.title || "No proxy"} description={networkCopy.noProxy?.description || ""} className="settings-row--field">
          <Input value={form.noProxy} placeholder={networkCopy.noProxy?.placeholder || "127.0.0.1,localhost"} disabled={state.networkLoading} onChange={(event) => (form.noProxy = event.target.value)} />
        </SettingsRow>
        <SettingsRow title={networkCopy.currentTitle || "Current setting"} description={summary}>
          <Button icon={<SaveOutlined />} loading={state.networkLoading} disabled={state.networkLoading} onClick={client.saveNetworkSettings}>
            {networkCopy.save || "Save network settings"}
          </Button>
        </SettingsRow>
      </SettingsCard>

      <SettingsCard>
        <SettingsRow title={networkCopy.scopeTitle || "Scope"} description={networkCopy.scopeDescription || ""} />
      </SettingsCard>
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

function LogSettings({ client }: { client: Client }) {
  const state = client.settingsState;
  const copy = client.copy.value;
  const form = state.logForm;
  const logCopy = copy.settings.log;
  const logLevelOptions = Array.isArray(state.log?.levels) && state.log.levels.length
    ? state.log.levels
    : ["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"];
  const logSummary = form.enabled
    ? logCopy.summary(form.level || "INFO", Number(form.retentionDays || 365))
    : logCopy.disabled;
  return (
    <section className="settings-page">
      <SettingsStatus message={state.logLoading ? logCopy.loading : ""} />
      <SettingsStatus message={state.logNotice} />
      <SettingsStatus message={state.logError} type="error" />

      <SettingsSectionTitle>{logCopy.title}</SettingsSectionTitle>
      <SettingsCard className="settings-card--form">
        <SettingsRow title={logCopy.enabled.title} description={logCopy.enabled.description}>
          <Switch aria-label={logCopy.enabled.title} checked={Boolean(form.enabled)} disabled={state.logLoading} onChange={(checked) => (form.enabled = checked)} />
        </SettingsRow>
        <SettingsRow title={logCopy.level.title} description={logCopy.level.description} className="settings-row--field">
          <Select
            value={form.level}
            disabled={state.logLoading || !form.enabled}
            options={logLevelOptions.map((level: string) => ({ value: level, label: level }))}
            onChange={(value) => (form.level = value)}
          />
        </SettingsRow>
        <SettingsRow title={logCopy.retention.title} description={logCopy.retention.description} className="settings-row--field">
          <InputNumber className="settings-control" min={1} max={3650} value={Number(form.retentionDays || 365)} disabled={state.logLoading || !form.enabled} onChange={(value) => (form.retentionDays = Number(value || 365))} />
        </SettingsRow>
        <SettingsRow title={logCopy.systemPrompt.title} description={logCopy.systemPrompt.description}>
          <Switch aria-label={logCopy.systemPrompt.title} checked={Boolean(form.logSystemPrompt)} disabled={state.logLoading || !form.enabled} onChange={(checked) => (form.logSystemPrompt = checked)} />
        </SettingsRow>
        <SettingsRow title={logCopy.systemPromptLines.title} description={logCopy.systemPromptLines.description} className="settings-row--field">
          <InputNumber className="settings-control" min={0} max={3650} value={Number(form.logSystemPromptLines || 0)} disabled={state.logLoading || !form.enabled || !form.logSystemPrompt} onChange={(value) => (form.logSystemPromptLines = Number(value || 0))} />
        </SettingsRow>
        <SettingsRow title={logCopy.reasoningDetails.title} description={logCopy.reasoningDetails.description}>
          <Switch aria-label={logCopy.reasoningDetails.title} checked={Boolean(form.logReasoningDetails)} disabled={state.logLoading || !form.enabled} onChange={(checked) => (form.logReasoningDetails = checked)} />
        </SettingsRow>
        <SettingsRow title={logCopy.currentTitle} description={logSummary}>
          <Button icon={<SaveOutlined />} loading={state.logLoading} disabled={state.logLoading} onClick={client.saveLogSettings}>
            {logCopy.save}
          </Button>
        </SettingsRow>
      </SettingsCard>

      <SettingsCard>
        <SettingsRow title={logCopy.rawResponseTitle} description={logCopy.rawResponseDescription} />
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

function AuthProviderCard({
  mark,
  name,
  status,
  description,
  loading,
  configured,
  copy,
  auth,
  onRefresh,
  onLogin,
  onLogout,
}: AnyRecord) {
  return (
    <SettingsCard className="provider-card">
      <div className="provider-row provider-row--stacked codex-auth-row">
        <div className="provider-row__content">
          <div className="provider-row__main">
            <span className="provider-row__mark" aria-hidden="true">{mark}</span>
            <div>
              <div className="provider-row__title">
                <strong>{name}</strong>
                <Tag className="provider-row__badge">{status}</Tag>
              </div>
              <span>{description}</span>
            </div>
          </div>
          <Space className="provider-row__actions" wrap>
            <Button icon={<ReloadOutlined />} loading={loading} disabled={loading} onClick={onRefresh}>{copy.refresh || "Refresh"}</Button>
            <Button type="primary" loading={loading} disabled={loading} onClick={onLogin}>{copy.login || "Login"}</Button>
            <Button disabled={loading || !configured} onClick={onLogout}>{copy.logout || "Logout"}</Button>
          </Space>
        </div>
        {auth.userCode ? (
          <div className="codex-auth-command">
            <span>{copy.userCodeLabel || "User code"}</span>
            <code>{auth.userCode}</code>
            {auth.verificationUri ? <a href={auth.verificationUri} target="_blank" rel="noreferrer">{copy.openVerification || "Open verification"}</a> : null}
          </div>
        ) : null}
      </div>
    </SettingsCard>
  );
}

function providerMark(value: AnyRecord) {
  return String(value?.name || value?.id || value?.type || "??").trim().slice(0, 2).toUpperCase();
}

function hasConnectedProvider(state: AnyRecord, presetId: string) {
  return (state.providers?.connected || []).some((provider: AnyRecord) => provider.provider === presetId || provider.id === presetId);
}

function authStatusLabel(copy: AnyRecord = {}, auth: AnyRecord = {}, loading = false) {
  if (loading) {
    return copy.loading || "Loading";
  }
  if (!auth.configured) {
    return copy.notConfigured || "Not configured";
  }
  if (auth.expired) {
    return copy.expired || "Expired";
  }
  return copy.configured || "Configured";
}

function codexDescription(copy: AnyRecord, state: AnyRecord) {
  const auth = state.codexAuth || {};
  const authCopy = copy.settings.providers?.codexAuth || {};
  if (!auth.configured) {
    return authCopy.description || "";
  }
  const parts = [];
  if (auth.account_id && typeof authCopy.account === "function") {
    parts.push(authCopy.account(auth.account_id));
  }
  if (auth.expires_at && typeof authCopy.expires === "function") {
    parts.push(authCopy.expires(auth.expires_at));
  }
  return parts.join(" - ") || authCopy.configuredDescription || "";
}

function copilotDescription(copy: AnyRecord, state: AnyRecord) {
  const auth = state.copilotAuth || {};
  const authCopy = copy.settings.providers?.copilotAuth || {};
  if (!auth.configured) {
    return authCopy.description || "";
  }
  return auth.path && typeof authCopy.path === "function" ? authCopy.path(auth.path) : authCopy.configuredDescription || "";
}

function providerCredentials(state: AnyRecord, provider: AnyRecord) {
  const providerKey = provider?.provider || provider?.id;
  return state.credentials?.[providerKey] || [];
}

function providerEffectiveCredentialId(provider: AnyRecord) {
  return provider?.credential_effective_id || provider?.effective_credential_id || provider?.credential_id || "";
}

function credentialSourceLabel(copy: AnyRecord, provider: AnyRecord) {
  const sources = copy.settings.providers?.credentialSources || {};
  return sources[provider?.credential_source] || "";
}

function providerDescription(copy: AnyRecord, state: AnyRecord, provider: AnyRecord) {
  const providerCopy = copy.settings.providers || {};
  if (provider?.provider === "openai-codex" && !state.codexAuth?.configured) {
    return providerCopy.codexAuth?.providerNeedsLogin || provider.base_url || "";
  }
  if (provider?.provider === "copilot" && !state.copilotAuth?.configured) {
    return providerCopy.copilotAuth?.providerNeedsLogin || provider.base_url || "";
  }
  return provider?.base_url || provider?.description || "";
}

function modelOptionsForProvider(provider: AnyRecord, selectedModel = "") {
  const models = Array.isArray(provider?.models) ? [...provider.models] : [];
  const selected = String(selectedModel || "").trim();
  if (selected && !models.includes(selected)) {
    models.unshift(selected);
  }
  return models;
}

function formatCompactTokenCount(value: any) {
  const tokens = Number(value);
  if (!Number.isFinite(tokens) || tokens <= 0) {
    return "";
  }
  if (tokens >= 1_000_000) {
    const millions = tokens / 1_000_000;
    return `${Number(millions.toFixed(millions >= 10 ? 0 : 1))}M`;
  }
  if (tokens >= 1_000) {
    return `${Math.round(tokens / 1_000)}K`;
  }
  return String(Math.round(tokens));
}

function textModelOptionLabel(copy: AnyRecord, provider: AnyRecord, model: string) {
  const contextLength = provider?.model_metadata?.[model]?.context_length;
  const formatted = formatCompactTokenCount(contextLength);
  const context = formatted && typeof copy.settings.models?.modelMetadata?.contextLength === "function"
    ? copy.settings.models.modelMetadata.contextLength(formatted)
    : "";
  const label = [model, context].filter(Boolean).join(" - ");
  return provider?.is_default && provider.selected_model === model
    ? `${label} (${copy.settings.models?.active || "active"})`
    : label;
}

function mediaModelCategories(copy: AnyRecord) {
  const categories = copy.settings.models?.mediaCategories || {};
  return [
    { key: "vision", mark: "VI", title: categories.vision?.title || "Vision", description: categories.vision?.description || "" },
    { key: "ocr", mark: "OC", title: categories.ocr?.title || "OCR", description: categories.ocr?.description || "" },
    { key: "speech", mark: "SP", title: categories.speech?.title || "Speech", description: categories.speech?.description || "" },
    { key: "video", mark: "VD", title: categories.video?.title || "Video", description: categories.video?.description || "" },
  ];
}

function mediaModelsForProvider(state: AnyRecord, category: string, providerId: string, selectedModel = "") {
  const provider = (state.media.providers || []).find((entry: AnyRecord) => entry.id === providerId);
  const mediaModels = provider?.media_models?.[category];
  const models = Array.isArray(mediaModels) ? [...mediaModels] : Array.isArray(provider?.models) ? [...provider.models] : [];
  const selected = String(selectedModel || "").trim();
  if (selected && !models.includes(selected)) {
    models.unshift(selected);
  }
  return models;
}

function mcpRuntimeStatus(copy: AnyRecord, state: AnyRecord) {
  const mcpCopy = copy.settings.mcp || {};
  const runtime = state.mcp.runtime || {};
  if (runtime.connecting) {
    return mcpCopy.runtimeConnecting || "Connecting";
  }
  if (runtime.connected) {
    return mcpCopy.runtimeConnected || "Connected";
  }
  if (runtime.connect_failures) {
    return typeof mcpCopy.runtimeFailed === "function" ? mcpCopy.runtimeFailed(runtime.connect_failures) : `Failed ${runtime.connect_failures} times`;
  }
  return mcpCopy.runtimeDisconnected || "Disconnected";
}

function mcpToolGroups(copy: AnyRecord, state: AnyRecord): AnyRecord[] {
  const toolNames = state.mcp.runtime?.tool_names || [];
  const servers = Array.isArray(state.mcp.servers) ? state.mcp.servers : [];
  const serverIds = servers.map((server: AnyRecord) => String(server.id || "").trim()).filter(Boolean);
  const groups = new Map<string, AnyRecord>();

  for (const server of servers) {
    const serverId = String(server.id || "").trim();
    if (!serverId) {
      continue;
    }
    groups.set(serverId, {
      serverId,
      serverName: server.name || serverId,
      expanded: state.mcpToolGroupsExpanded[serverId] === true,
      tools: [],
    });
  }

  for (const fullName of toolNames) {
    const normalized = String(fullName || "").trim();
    if (!normalized) {
      continue;
    }
    const withoutPrefix = normalized.startsWith("mcp_") ? normalized.slice(4) : normalized;
    const serverId = serverIds
      .filter((candidate) => withoutPrefix.startsWith(`${candidate}_`))
      .sort((left, right) => right.length - left.length)[0] || "unknown";
    const toolName = serverId === "unknown" ? withoutPrefix : withoutPrefix.slice(serverId.length + 1);
    if (!groups.has(serverId)) {
      groups.set(serverId, {
        serverId,
        serverName: serverId === "unknown" ? copy.settings.mcp?.unknownServer || "Unknown" : serverId,
        expanded: state.mcpToolGroupsExpanded[serverId] === true,
        tools: [],
      });
    }
    groups.get(serverId)?.tools.push({ fullName: normalized, name: toolName || normalized });
  }

  return (Array.from(groups.values()) as AnyRecord[])
    .map((group: AnyRecord) => ({
      serverId: group.serverId,
      serverName: group.serverName,
      expanded: group.expanded,
      tools: group.tools.sort((left: AnyRecord, right: AnyRecord) => left.name.localeCompare(right.name)),
    }))
    .filter((group) => group.tools.length > 0)
    .sort((left: AnyRecord, right: AnyRecord) => String(left.serverName).localeCompare(String(right.serverName)));
}

function scheduleTimezoneOptions(state: AnyRecord): string[] {
  const configured = Array.isArray(state.schedule.common_timezones) ? state.schedule.common_timezones : [];
  const options = configured.map((timezone: any) => String(timezone || "").trim()).filter(Boolean);
  const current = String(state.scheduleForm.defaultTimezone || state.schedule.default_timezone || "UTC").trim() || "UTC";
  const uniqueOptions: string[] = Array.from(new Set<string>(options.length ? options : ["UTC"]));
  if (!uniqueOptions.includes(current)) {
    uniqueOptions.unshift(current);
  }
  return uniqueOptions;
}

function networkSummary(copy: AnyRecord, state: AnyRecord) {
  const form = state.networkForm || {};
  const active = [form.httpProxy, form.httpsProxy].map((value) => String(value || "").trim()).filter(Boolean).length;
  if (!active) {
    return copy.settings.network?.noProxyConfigured || "No proxy configured";
  }
  return typeof copy.settings.network?.proxyConfigured === "function"
    ? copy.settings.network.proxyConfigured(active)
    : `${active} proxy setting${active === 1 ? "" : "s"} configured`;
}

function webSearchProviderLabel(copy: AnyRecord, provider: string) {
  return copy.settings.search?.providers?.[provider] || provider;
}

function webSearchFreshnessLabel(copy: AnyRecord, freshness: string) {
  return copy.settings.search?.freshness?.options?.[freshness] || freshness;
}

function webSearchProviderOptions(copy: AnyRecord, state: AnyRecord) {
  const providers = state.search?.providers;
  const values = Array.isArray(providers) && providers.length ? providers : ["duckduckgo", "searxng", "jina"];
  return values.map((id: string) => ({ id, label: webSearchProviderLabel(copy, id) }));
}

function webSearchFreshnessOptions(copy: AnyRecord, state: AnyRecord) {
  const freshnessOptions = state.search?.freshness_options;
  const values = Array.isArray(freshnessOptions) && freshnessOptions.length ? freshnessOptions : ["auto", "none", "day", "week", "month", "year"];
  return values.map((id: string) => ({ id, label: webSearchFreshnessLabel(copy, id) }));
}

function mergeSelectedSearchOptions(options: AnyRecord[] = [], selected: string[] = []) {
  const merged = new Map<string, AnyRecord>();
  for (const option of Array.isArray(options) ? options : []) {
    const id = String(option?.id || "").trim();
    if (!id) {
      continue;
    }
    merged.set(id, {
      ...option,
      id,
      label: String(option.label || id).trim() || id,
      configuredOnly: false,
    });
  }
  for (const id of Array.isArray(selected) ? selected : []) {
    const value = String(id || "").trim();
    if (!value || merged.has(value)) {
      continue;
    }
    merged.set(value, { id: value, label: value, categories: [], shortcut: "", configuredOnly: true });
  }
  return Array.from(merged.values());
}

function searxngEngineMeta(copy: AnyRecord, option: AnyRecord) {
  const parts = [];
  if (option.shortcut) {
    parts.push(option.shortcut);
  }
  if (Array.isArray(option.categories) && option.categories.length) {
    parts.push(option.categories.join(", "));
  }
  if (option.configuredOnly) {
    parts.push(copy.settings.search?.searxngOptions?.configuredOnly || "Configured but not listed");
  }
  return parts.join(" - ");
}

function webSearchCredentialStatus(copy: AnyRecord, state: AnyRecord, provider: string) {
  const configured = state.search?.[`${provider}_api_key_configured`] === true;
  return configured ? copy.settings.search?.credentials?.configured || "Configured" : copy.settings.search?.credentials?.notConfigured || "Not configured";
}

function webSearchSummary(copy: AnyRecord, state: AnyRecord) {
  const form = state.searchForm || {};
  return typeof copy.settings.search?.summary === "function"
    ? copy.settings.search.summary(
      webSearchProviderLabel(copy, form.provider || "searxng"),
      webSearchFreshnessLabel(copy, form.freshness || "auto"),
      Number(form.maxResults || 25),
    )
    : `${form.provider || "searxng"} - ${form.freshness || "auto"} - ${Number(form.maxResults || 25)}`;
}

function browserBackendOptions(copy: AnyRecord, state: AnyRecord) {
  const backends = state.browser?.backends;
  const values = Array.isArray(backends) && backends.length ? backends : ["agent-browser", "browserbase", "browser-use", "firecrawl"];
  return values.map((id: string) => ({ id, label: copy.settings.browser?.backends?.[id] || id }));
}

function selectedBrowserBackend(state: AnyRecord) {
  return state.browserForm?.backend || state.browser?.backend || "agent-browser";
}

function selectedBrowserBackendLabel(copy: AnyRecord, state: AnyRecord) {
  const backend = selectedBrowserBackend(state);
  return copy.settings.browser?.backends?.[backend] || backend;
}

function browserRuntimeStatus(copy: AnyRecord, state: AnyRecord) {
  const browserCopy = copy.settings.browser || {};
  const runtime = state.browser?.runtime || {};
  const backend = selectedBrowserBackend(state);
  const backendLabel = selectedBrowserBackendLabel(copy, state);
  if (backend !== "agent-browser") {
    const cloud = state.browser?.cloud?.[backend] || {};
    if (!cloud.configured) {
      return typeof browserCopy.cloudMissing === "function" ? browserCopy.cloudMissing(backendLabel) : `${backendLabel} credentials are not configured.`;
    }
    if (!runtime.available) {
      return typeof browserCopy.cloudAttachRuntimeMissing === "function" ? browserCopy.cloudAttachRuntimeMissing(backendLabel) : `${backendLabel} attach runtime is missing.`;
    }
    return typeof browserCopy.cloudConfigured === "function" ? browserCopy.cloudConfigured(backendLabel) : `${backendLabel} is configured.`;
  }
  if (runtime.available) {
    return typeof browserCopy.runtimeAvailable === "function" ? browserCopy.runtimeAvailable(runtime.command || "agent-browser") : `Available: ${runtime.command || "agent-browser"}`;
  }
  return browserCopy.runtimeMissing || "agent-browser and npx were not found.";
}

function browserSummary(copy: AnyRecord, state: AnyRecord) {
  const browserCopy = copy.settings.browser || {};
  const form = state.browserForm || {};
  const backend = selectedBrowserBackend(state);
  const backendLabel = selectedBrowserBackendLabel(copy, state);
  if (!form.enabled) {
    return browserCopy.disabled || "Browser tools are disabled.";
  }
  if (String(form.cdpUrl || "").trim()) {
    return browserCopy.cdpEnabled || "Browser tools attach through CDP.";
  }
  if (backend !== "agent-browser") {
    return typeof browserCopy.cloudEnabled === "function" ? browserCopy.cloudEnabled(backendLabel) : `Browser tools use ${backendLabel}.`;
  }
  return browserCopy.enabledSummary || "Browser tools are enabled.";
}

function browserTestSummary(copy: AnyRecord, state: AnyRecord) {
  const browserCopy = copy.settings.browser || {};
  const result = state.browserTestResult;
  if (!result) {
    return browserCopy.test?.notRun || "No manual browser test has run yet.";
  }
  if (result.ok) {
    return typeof browserCopy.test?.resultPassed === "function" ? browserCopy.test.resultPassed(result.url || "") : `Browser test passed: ${result.url || ""}`;
  }
  const error = result.error || result.open?.error || result.snapshot?.error || "";
  return typeof browserCopy.test?.resultFailed === "function" ? browserCopy.test.resultFailed(error) : `Browser test failed${error ? `: ${error}` : "."}`;
}

function browserDoctorSummary(copy: AnyRecord, state: AnyRecord) {
  const browserCopy = copy.settings.browser || {};
  const result = state.browserDoctorResult;
  if (!result) {
    return browserCopy.doctor?.notRun || "Install has not been checked yet.";
  }
  const checks = Array.isArray(result.checks) ? result.checks : [];
  const passed = checks.filter((check: AnyRecord) => check?.ok).length;
  if (result.ok) {
    return typeof browserCopy.doctor?.resultPassed === "function" ? browserCopy.doctor.resultPassed(passed, checks.length) : `Install check passed: ${passed}/${checks.length}`;
  }
  return typeof browserCopy.doctor?.resultFailed === "function" ? browserCopy.doctor.resultFailed(passed, checks.length) : `Install check failed: ${passed}/${checks.length}`;
}

function browserDoctorCheckSummary(copy: AnyRecord, check: AnyRecord) {
  const browserCopy = copy.settings.browser || {};
  const status = check?.ok ? browserCopy.doctor?.checkPassed || "Passed" : browserCopy.doctor?.checkFailed || "Failed";
  const detail = String(check?.suggestion || check?.stderr || check?.stdout || "").trim();
  return detail ? `${status}: ${detail}` : status;
}

function ToastStack({ client }: { client: Client }) {
  const toasts = client.toasts.value || [];
  if (!toasts.length) {
    return null;
  }
  return (
    <div className="toast-stack">
      {toasts.map((toast: AnyRecord) => (
        <Alert
          key={toast.id}
          type={noticeTone(toast.tone)}
          message={toast.text}
          closable
          onClose={() => client.dismissToast(toast.id)}
        />
      ))}
    </div>
  );
}

function Toolbar({ title, loading, onRefresh }: { title: string; loading?: boolean; onRefresh: () => void }) {
  return (
    <Flex justify="space-between" align="center">
      <Typography.Title level={5}>{title}</Typography.Title>
      <Button icon={<ReloadOutlined />} loading={loading} onClick={onRefresh}>Refresh</Button>
    </Flex>
  );
}

function SwitchRow({ label, checked, onChange }: { label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <Flex align="center" gap={8}>
      <Switch checked={Boolean(checked)} onChange={onChange} />
      <Typography.Text>{label}</Typography.Text>
    </Flex>
  );
}

function JsonCard({ title, value }: { title: string; value: any }) {
  return (
    <Card size="small" title={title}>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </Card>
  );
}

function credentialSelector(client: Client, provider: AnyRecord) {
  const credentials = client.settingsState.credentials?.[provider.provider || provider.id] || [];
  if (!credentials.length) {
    return null;
  }
  return (
    <Select
      key="credential"
      size="small"
      value={provider.credential_id || provider.effective_credential_id}
      style={{ minWidth: 160 }}
      onChange={(value) => client.setProviderCredential(provider, value)}
      options={credentials.map((credential: AnyRecord) => ({
        value: credential.id,
        label: credential.name || credential.id,
      }))}
    />
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

function connectionLabel(copy: AnyRecord, state: string) {
  return copy.connection?.[state] || state;
}

function connectionColor(state: string) {
  if (state === "connected") {
    return "green";
  }
  if (state === "connecting") {
    return "blue";
  }
  return "default";
}

function noticeTone(tone: string): "success" | "info" | "warning" | "error" {
  if (tone === "success" || tone === "warning" || tone === "error") {
    return tone;
  }
  return "info";
}

function runStatusColor(status: string) {
  if (["completed", "success", "done"].includes(status)) {
    return "green";
  }
  if (["failed", "error"].includes(status)) {
    return "red";
  }
  if (["running", "thinking", "tool_running", "streaming"].includes(status)) {
    return "blue";
  }
  if (["cancelled", "cancelling"].includes(status)) {
    return "orange";
  }
  return "default";
}

function runOptionLabel(copy: AnyRecord, run: AnyRecord, index: number) {
  const statusLabel = copy.run.statusLabels?.[run.status] || run.status;
  const prefix = index === 0 ? copy.runHistory.latest : `#${index + 1}`;
  return `${prefix} · Run ${shortRunId(run.runId)} · ${statusLabel}`;
}

function normalizeMessages({
  copy,
  entries,
  messages,
  runs,
  displayName,
}: {
  copy: AnyRecord;
  entries: AnyRecord[];
  messages: AnyRecord[];
  runs: AnyRecord[];
  displayName: string;
}) {
  const references = buildRunReferences(entries, runs);
  if (entries?.length) {
    return entries.filter(isChatEntry).map((entry, index) => normalizeEntry(copy, entry, index, displayName, references)).filter(Boolean);
  }
  return (messages || []).map((message, index) => normalizeMessage(copy, message, index, displayName, references)).filter((message) => message.text.trim());
}

function buildRunReferences(entries: AnyRecord[] = [], runs: AnyRecord[] = []) {
  const references = new Map<string, AnyRecord>();
  for (const run of runs || []) {
    upsertRunReference(references, normalizeRunReference(run));
  }
  for (const entry of entries || []) {
    upsertRunReference(references, normalizeRunReference(entry));
  }
  return Array.from(references.values()).sort((left, right) => Number(left.createdAt || 0) - Number(right.createdAt || 0));
}

function normalizeEntry(copy: AnyRecord, entry: AnyRecord, index: number, displayName: string, references: AnyRecord[]) {
  const role = entry.role === "user" ? "user" : "assistant";
  const content = Array.isArray(entry.content) ? entry.content.map((part: AnyRecord, partIndex: number) => normalizeTextPart(copy, part, partIndex)).filter(Boolean) : [];
  const text = sanitizeVisibleText(entry.text || "");
  if (!text && content.length === 0) {
    return null;
  }
  return {
    id: entry.id || `entry-${index}`,
    role,
    text,
    textBlocks: buildMessageBlocks(copy, text, `entry-${index}`),
    meta: entry.meta || (role === "user" ? displayName : "OpenSprite"),
    ...messageTimeFields(entry.createdAt ?? entry.created_at),
    content,
    traceRunId: findTraceRunIdForEntry(entry, role, references),
  };
}

function normalizeMessage(copy: AnyRecord, message: AnyRecord, index: number, displayName: string, references: AnyRecord[]) {
  const text = sanitizeVisibleText(message.text);
  const role = message.role === "user" ? "user" : "assistant";
  return {
    ...message,
    id: message.id || `message-${index}`,
    role,
    text,
    textBlocks: buildMessageBlocks(copy, text, message.id || `message-${index}`),
    meta: message.meta || (role === "user" ? displayName : "OpenSprite"),
    ...messageTimeFields(message.createdAt ?? message.created_at),
    content: [],
    traceRunId: findTraceRunIdForEntry(message, role, references),
  };
}

function normalizeTextPart(copy: AnyRecord, part: AnyRecord, index: number) {
  const text = sanitizeVisibleText(part?.text || part?.detail || "");
  if (!text) {
    return null;
  }
  return {
    id: part?.id || `text-${index}`,
    type: "text",
    text,
    textBlocks: buildMessageBlocks(copy, text, `part-${index}`),
  };
}

function isRunEntry(entry: AnyRecord) {
  const runId = String(entry?.runId || entry?.run_id || "").trim();
  const entryId = String(entry?.id || entry?.entry_id || entry?.entryId || "").trim();
  if (entryId.startsWith("run:")) {
    return true;
  }
  const entryType = String(entry?.type || entry?.entry_type || entry?.entryType || "").trim();
  if (entryType === "run") {
    return true;
  }
  const text = sanitizeVisibleText(entry?.text || "");
  const content = Array.isArray(entry?.content) ? entry.content : [];
  return Boolean(runId && !text && content.length === 0);
}

function isChatEntry(entry: AnyRecord) {
  if (isRunEntry(entry)) {
    return false;
  }
  return entry?.role === "user" || entry?.role === "assistant";
}

function findTraceRunIdForEntry(entry: AnyRecord, role: string, references: AnyRecord[]) {
  if (role !== "assistant") {
    return "";
  }
  const directRunId = getEntryRunId(entry);
  if (directRunId) {
    return directRunId;
  }
  const createdAt = normalizeTimestamp(entry?.createdAt ?? entry?.created_at);
  if (!createdAt) {
    return "";
  }
  const matches = references
    .filter((run) => run.createdAt && run.updatedAt)
    .filter((run) => createdAt >= run.createdAt - TRACE_MATCH_WINDOW_MS && createdAt <= run.updatedAt + TRACE_MATCH_WINDOW_MS)
    .sort((left, right) => Math.abs(Number(left.updatedAt || 0) - createdAt) - Math.abs(Number(right.updatedAt || 0) - createdAt));
  return matches[0]?.runId || "";
}

function getEntryRunId(entry: AnyRecord) {
  return String(entry?.runId || entry?.run_id || entry?.metadata?.runId || entry?.metadata?.run_id || "").trim();
}

function normalizeRunReference(source: AnyRecord) {
  const runId = getEntryRunId(source);
  if (!runId) {
    return null;
  }
  const createdAt = normalizeTimestamp(source?.createdAt ?? source?.created_at);
  const updatedAt = normalizeTimestamp(source?.finishedAt ?? source?.finished_at ?? source?.updatedAt ?? source?.updated_at);
  return {
    runId,
    status: String(source?.status || "").trim(),
    createdAt,
    updatedAt: updatedAt || createdAt,
  };
}

function upsertRunReference(references: Map<string, AnyRecord>, next: AnyRecord | null) {
  if (!next?.runId) {
    return;
  }
  const existing = references.get(next.runId);
  if (!existing) {
    references.set(next.runId, next);
    return;
  }
  existing.status = next.status || existing.status;
  existing.createdAt = minPositiveTimestamp(existing.createdAt, next.createdAt);
  existing.updatedAt = Math.max(Number(existing.updatedAt || 0), Number(next.updatedAt || 0));
}

function minPositiveTimestamp(left: number, right: number) {
  const leftValue = Number(left || 0);
  const rightValue = Number(right || 0);
  if (leftValue > 0 && rightValue > 0) {
    return Math.min(leftValue, rightValue);
  }
  return leftValue || rightValue || 0;
}

function normalizeTimestamp(value: any) {
  const timestamp = Number(value || 0);
  if (!Number.isFinite(timestamp) || timestamp <= 0) {
    return 0;
  }
  return timestamp > 1_000_000_000_000 ? timestamp : timestamp * 1000;
}

function sanitizeVisibleText(value: any) {
  return String(value || "")
    .replace(/<\s*(think|thinking|system-reminder)\b[^>]*>[\s\S]*?<\s*\/\s*\1\s*>/gi, "")
    .replace(/<\s*(think|thinking|system-reminder)\b[^>]*>[\s\S]*$/i, "")
    .trim();
}

function artifactTypeLabel(copy: AnyRecord, type: string) {
  const labels = copy.message.artifactTypes || {};
  return labels[type] || type;
}

function artifactStatusLabel(copy: AnyRecord, status: string) {
  const labels = copy.run?.statusLabels || {};
  return labels[status] || status;
}

function messageTimeFields(value: any) {
  const timestamp = Number(value || 0);
  if (!Number.isFinite(timestamp) || timestamp <= 0) {
    return { isoTime: "", timeLabel: "", fullTimeLabel: "" };
  }
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return { isoTime: "", timeLabel: "", fullTimeLabel: "" };
  }
  return {
    isoTime: date.toISOString(),
    timeLabel: new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" }).format(date),
    fullTimeLabel: new Intl.DateTimeFormat(undefined, {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(date),
  };
}

function buildMessageBlocks(copy: AnyRecord, value: any, keyPrefix: string) {
  const text = String(value || "").replace(/\r\n/g, "\n").trim();
  if (!text) {
    return [];
  }
  const jsonBlock = maybeJsonBlock(copy, text, `${keyPrefix}:json`);
  if (jsonBlock) {
    return [jsonBlock];
  }
  return parseMarkdownBlocks(copy, text, keyPrefix);
}

function maybeJsonBlock(copy: AnyRecord, text: string, id: string) {
  const trimmed = text.trim();
  if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) {
    return null;
  }
  try {
    const parsed = JSON.parse(trimmed);
    return {
      id,
      type: "json",
      summary: jsonSummary(copy, parsed),
      code: JSON.stringify(parsed, null, 2),
    };
  } catch {
    return null;
  }
}

function jsonSummary(copy: AnyRecord, value: any) {
  if (Array.isArray(value)) {
    return copy.message.jsonArray(value.length);
  }
  if (value && typeof value === "object") {
    const keys = Object.keys(value);
    return copy.message.jsonObject(keys.slice(0, 4).join(", "), keys.length);
  }
  return copy.message.jsonValue;
}

function parseMarkdownBlocks(copy: AnyRecord, text: string, keyPrefix: string) {
  const lines = text.split("\n");
  const blocks: AnyRecord[] = [];
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    const trimmed = line.trim();
    if (!trimmed) {
      index += 1;
      continue;
    }
    if (isMarkdownRule(trimmed)) {
      blocks.push({ id: `${keyPrefix}:rule-${blocks.length}`, type: "rule" });
      index += 1;
      continue;
    }
    const fence = trimmed.match(/^```([A-Za-z0-9_-]*)\s*$/);
    if (fence) {
      const language = fence[1] || "";
      const codeLines = [];
      index += 1;
      while (index < lines.length && !lines[index].trim().startsWith("```")) {
        codeLines.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) {
        index += 1;
      }
      blocks.push(codeBlock(copy, codeLines.join("\n"), language, `${keyPrefix}:code-${blocks.length}`));
      continue;
    }
    const heading = trimmed.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      blocks.push({
        id: `${keyPrefix}:heading-${blocks.length}`,
        type: "heading",
        level: heading[1].length,
        text: heading[2].trim(),
        segments: inlineSegments(heading[2].trim(), `${keyPrefix}:heading-${blocks.length}`),
      });
      index += 1;
      continue;
    }
    if (isMarkdownTable(lines, index)) {
      const tableLines = [lines[index]];
      index += 2;
      while (index < lines.length && lines[index].includes("|")) {
        tableLines.push(lines[index]);
        index += 1;
      }
      blocks.push(tableBlock(tableLines, `${keyPrefix}:table-${blocks.length}`));
      continue;
    }
    const unordered = trimmed.match(/^[-*]\s+(.+)$/);
    const ordered = trimmed.match(/^\d+[.)]\s+(.+)$/);
    if (unordered || ordered) {
      const orderedList = Boolean(ordered);
      const items = [];
      while (index < lines.length) {
        const itemMatch = lines[index].trim().match(orderedList ? /^\d+[.)]\s+(.+)$/ : /^[-*]\s+(.+)$/);
        if (!itemMatch) {
          break;
        }
        const itemText = itemMatch[1].trim();
        items.push({
          id: `${keyPrefix}:list-${blocks.length}-${items.length}`,
          text: itemText,
          segments: inlineSegments(itemText, `${keyPrefix}:list-${blocks.length}-${items.length}`),
        });
        index += 1;
      }
      blocks.push({ id: `${keyPrefix}:list-${blocks.length}`, type: "list", ordered: orderedList, items });
      continue;
    }
    const paragraphLines = [];
    while (index < lines.length && !isBlockStart(lines, index)) {
      if (!lines[index].trim()) {
        break;
      }
      paragraphLines.push(lines[index].trim());
      index += 1;
    }
    const paragraph = paragraphLines.join(" ").trim();
    if (paragraph) {
      blocks.push({
        id: `${keyPrefix}:paragraph-${blocks.length}`,
        type: "paragraph",
        text: paragraph,
        segments: inlineSegments(paragraph, `${keyPrefix}:paragraph-${blocks.length}`),
      });
    }
  }
  return blocks;
}

function codeBlock(copy: AnyRecord, code: string, language: string, id: string) {
  const jsonBlock = language.toLowerCase() === "json" ? maybeJsonBlock(copy, code, id) : null;
  if (jsonBlock) {
    return jsonBlock;
  }
  return { id, type: "code", language, code };
}

function isBlockStart(lines: string[], index: number) {
  const trimmed = lines[index]?.trim() || "";
  if (!trimmed) {
    return false;
  }
  return (
    isMarkdownRule(trimmed) ||
    /^```/.test(trimmed) ||
    /^(#{1,3})\s+/.test(trimmed) ||
    /^[-*]\s+/.test(trimmed) ||
    /^\d+[.)]\s+/.test(trimmed) ||
    /^>\s?/.test(trimmed) ||
    isMarkdownTable(lines, index)
  );
}

function isMarkdownRule(trimmed: string) {
  return /^(?:-{3,}|\*{3,}|_{3,})$/.test(String(trimmed || "").replace(/\s+/g, ""));
}

function isMarkdownTable(lines: string[], index: number) {
  const current = lines[index]?.trim() || "";
  const next = lines[index + 1]?.trim() || "";
  return current.includes("|") && /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(next);
}

function tableBlock(tableLines: string[], id: string) {
  const headers = splitTableRow(tableLines[0]).map((text, index) => ({ id: `${id}:h-${index}`, text }));
  const rows = tableLines.slice(1).map((line, rowIndex) => {
    const cells = splitTableRow(line).map((text, cellIndex) => ({ id: `${id}:r-${rowIndex}-${cellIndex}`, text }));
    return { id: `${id}:r-${rowIndex}`, cells };
  });
  return { id, type: "table", headers, rows };
}

function splitTableRow(line: string) {
  return String(line || "")
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function inlineSegments(text: string, idPrefix: string) {
  const segments: AnyRecord[] = [];
  const pattern = /(`[^`]+`)|(\[([^\]]+)\]\((https?:\/\/[^)\s]+)\))|(\*\*([^*\n][\s\S]*?[^*\n])\*\*)/g;
  let cursor = 0;
  let match;
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > cursor) {
      segments.push({ id: `${idPrefix}:t-${segments.length}`, type: "text", text: text.slice(cursor, match.index) });
    }
    if (match[1]) {
      segments.push({ id: `${idPrefix}:c-${segments.length}`, type: "code", text: match[1].slice(1, -1) });
    } else if (match[2]) {
      segments.push({ id: `${idPrefix}:l-${segments.length}`, type: "link", text: match[3], href: match[4] });
    } else {
      segments.push({ id: `${idPrefix}:s-${segments.length}`, type: "strong", text: match[6] });
    }
    cursor = pattern.lastIndex;
  }
  if (cursor < text.length) {
    segments.push({ id: `${idPrefix}:t-${segments.length}`, type: "text", text: text.slice(cursor) });
  }
  return segments.length ? segments : [{ id: `${idPrefix}:t-0`, type: "text", text }];
}

function renderSegments(segments: AnyRecord[] = []) {
  return segments.map((segment) => {
    if (segment.type === "code") {
      return <code key={segment.id}>{segment.text}</code>;
    }
    if (segment.type === "link") {
      return (
        <a key={segment.id} href={segment.href} target="_blank" rel="noreferrer">
          {segment.text}
        </a>
      );
    }
    if (segment.type === "strong") {
      return <strong key={segment.id}>{segment.text}</strong>;
    }
    return <React.Fragment key={segment.id}>{segment.text}</React.Fragment>;
  });
}
