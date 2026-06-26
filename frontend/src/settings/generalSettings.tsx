import { DeleteOutlined, ReloadOutlined, SaveOutlined } from "@ant-design/icons";
import { Button, Input, Segmented, Select, Space, Switch } from "antd";
import { connectionLabel } from "../components/displayHelpers";
import { SettingsCard, SettingsRow, SettingsSectionTitle, SettingsStatus } from "./settingsPrimitives";

type AnyRecord = Record<string, any>;
type ValueRef<T> = { value: T };

type GeneralSettingsClient = {
  copy: ValueRef<AnyRecord>;
  settingsState: AnyRecord;
  settingsForm: AnyRecord;
  webSessionCount?: ValueRef<number>;
  state: AnyRecord;
  toggleSettingsConnection: (checked: boolean) => void;
  saveConnectionSettings: () => void;
  loadUpdateStatus: () => void;
  runUpdate: () => void;
};

export function GeneralSettings({ client, clearWebSessions }: { client: GeneralSettingsClient; clearWebSessions: () => void }) {
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
