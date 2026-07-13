import { SaveOutlined } from "@ant-design/icons";
import { Button, Input, InputNumber, Select, Space, Switch } from "antd";
import type { BrowserForm, BrowserOperationResult, BrowserState } from "../composables/browserDefaults";
import {
  browserBackendOptions,
  browserDoctorChecks,
  browserDoctorCheckSummary,
  browserDoctorSummary,
  browserRuntimeStatus,
  browserSummary,
  browserTestSummary,
  type BrowserSettingsCopy,
  type BrowserSettingsCopyView,
  type BrowserSettingsStateLike,
} from "./searchBrowserHelpers";
import { SettingsCard, SettingsRow, SettingsSectionTitle, SettingsStatus } from "./settingsPrimitives";

type ValueRef<T> = { value: T };

type BrowserSettingsStateView = BrowserSettingsStateLike & {
  browserLoading: boolean;
  browserTestLoading: boolean;
  browserDoctorLoading: boolean;
  browserInstallLoading: boolean;
  browserError: string;
  browserNotice: string;
  browserTestResult: BrowserOperationResult | null;
  browserDoctorResult: BrowserOperationResult | null;
  browserInstallResult: BrowserOperationResult | null;
  browser: BrowserState;
  browserForm: BrowserForm;
};

type BrowserSettingsClient = {
  copy: ValueRef<BrowserSettingsCopy>;
  settingsState: BrowserSettingsStateView;
  saveBrowserSettings: () => void;
  runBrowserTest: () => void;
  runBrowserDoctor: () => void;
  runBrowserInstall: () => void;
};

export function BrowserSettings({ client }: { client: BrowserSettingsClient }) {
  const state = client.settingsState;
  const copy = client.copy.value;
  const form = state.browserForm;
  const browserCopy: BrowserSettingsCopyView = copy.settings.browser ?? {};
  const backendOptions = browserBackendOptions(copy, state);
  const summary = browserSummary(copy, state);
  const runtime = browserRuntimeStatus(copy, state);
  const testSummary = browserTestSummary(copy, state);
  const doctorSummary = browserDoctorSummary(copy, state);
  const doctorChecks = browserDoctorChecks(state.browserDoctorResult);
  const installHint = typeof state.browser.runtime.install_hint === "string" ? state.browser.runtime.install_hint : "";

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
        <SettingsRow title={browserCopy.runtimeTitle || "Runtime status"} description={<>{runtime}{installHint ? <><br />{installHint}</> : null}</>} />
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
        {doctorChecks.length ? (
          <div className="settings-stack">
            {doctorChecks.map((check, index) => (
              <SettingsRow key={String(check.name || check.command || index)} title={String(check.command || check.name || "")} description={browserDoctorCheckSummary(copy, check)} />
            ))}
          </div>
        ) : null}
      </SettingsCard>
    </section>
  );
}
