import { useState, type PointerEvent } from "react";
import { MenuFoldOutlined, MenuUnfoldOutlined, PlusOutlined } from "@ant-design/icons";
import { Button, Checkbox, Segmented, Switch } from "antd";

type AnyRecord = Record<string, any>;

type SidebarNavClient = AnyRecord & {
  copy: { value: AnyRecord };
  sidebarSessions: { value: AnyRecord[] };
  sidebarSessionTotal: { value: number };
  sidebarCollapsed: { value: boolean };
  sessionChannelFilter: { value: string };
  showHiddenSessions: { value: boolean };
  state: AnyRecord;
};

export function SidebarNav({
  client,
  beginSidebarResize,
  deleteSessions,
}: {
  client: SidebarNavClient;
  beginSidebarResize: (event: PointerEvent) => void;
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
