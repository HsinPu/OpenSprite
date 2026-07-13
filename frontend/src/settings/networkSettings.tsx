import { SaveOutlined } from "@ant-design/icons";
import { Button, Input } from "antd";
import type { NetworkForm } from "../composables/networkDefaults";
import { networkSummary } from "./scheduleNetworkHelpers";
import { SettingsCard, SettingsRow, SettingsSectionTitle, SettingsStatus } from "./settingsPrimitives";

type ValueRef<T> = { value: T };

type SettingsCopyText = {
  title?: string;
  description?: string;
  placeholder?: string;
};

type NetworkSettingsCopyView = {
  loading?: string;
  title?: string;
  httpProxy?: SettingsCopyText;
  httpsProxy?: SettingsCopyText;
  noProxy?: SettingsCopyText;
  proxyPlaceholder?: string;
  currentTitle?: string;
  save?: string;
  scopeTitle?: string;
  scopeDescription?: string;
  noProxyConfigured?: string;
  proxyConfigured?: (active: number) => string;
};

type NetworkSettingsCopy = {
  settings: {
    network?: NetworkSettingsCopyView;
  };
};

type NetworkSettingsStateView = {
  networkLoading: boolean;
  networkNotice: string;
  networkError: string;
  networkForm: NetworkForm;
};

type NetworkSettingsClient = {
  copy: ValueRef<NetworkSettingsCopy>;
  settingsState: NetworkSettingsStateView;
  saveNetworkSettings: () => void;
};

export function NetworkSettings({ client }: { client: NetworkSettingsClient }) {
  const state = client.settingsState;
  const copy = client.copy.value;
  const networkCopy: NetworkSettingsCopyView = copy.settings.network ?? {};
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
