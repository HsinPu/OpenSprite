import { SaveOutlined } from "@ant-design/icons";
import { Button, InputNumber, Select, Switch } from "antd";
import { DEFAULT_LOG_LEVELS, type LogForm, type LogState } from "../composables/logDefaults";
import { SettingsCard, SettingsRow, SettingsSectionTitle, SettingsStatus } from "./settingsPrimitives";

type ValueRef<T> = { value: T };

type SettingsCopyText = {
  title: string;
  description: string;
};

type LogSettingsCopyView = {
  title: string;
  loading: string;
  disabled: string;
  enabled: SettingsCopyText;
  level: SettingsCopyText;
  retention: SettingsCopyText;
  systemPrompt: SettingsCopyText;
  systemPromptLines: SettingsCopyText;
  reasoningDetails: SettingsCopyText;
  currentTitle: string;
  save: string;
  rawResponseTitle: string;
  rawResponseDescription: string;
  summary: (level: string, retentionDays: number) => string;
};

type LogSettingsCopy = {
  settings: {
    log: LogSettingsCopyView;
  };
};

type LogSettingsStateView = {
  logLoading: boolean;
  logNotice: string;
  logError: string;
  log: Pick<LogState, "levels">;
  logForm: LogForm;
};

type LogSettingsClient = {
  copy: ValueRef<LogSettingsCopy>;
  settingsState: LogSettingsStateView;
  saveLogSettings: () => void;
};

export function LogSettings({ client }: { client: LogSettingsClient }) {
  const state = client.settingsState;
  const copy = client.copy.value;
  const form = state.logForm;
  const logCopy = copy.settings.log;
  const logLevelOptions = Array.isArray(state.log?.levels) && state.log.levels.length
    ? state.log.levels
    : DEFAULT_LOG_LEVELS;
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
