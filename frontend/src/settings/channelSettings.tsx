import { ArrowLeftOutlined, CloseOutlined } from "@ant-design/icons";
import { Button, Form, Input, List, Tag } from "antd";
import type { ChannelConnectForm, ChannelSettings as ChannelSettingsValue, ChannelView } from "../composables/useSettingsState";
import { providerMark } from "./providerHelpers";
import { SettingsCard, SettingsSectionTitle, SettingsStatus } from "./settingsPrimitives";

type ValueRef<T> = { value: T };

type ChannelCopyFormatter = (name: string) => string;

type ChannelSettingsCopyView = {
  loading?: string;
  connectedTitle?: string;
  noConnectedTitle?: string;
  noConnectedDescription?: string;
  connectedBadge?: string;
  enabledBadge?: string;
  disconnect?: string;
  availableTitle?: string;
  noAvailableTitle?: string;
  noAvailableDescription?: string;
  builtInBadge?: string;
  add?: string;
  connect?: string;
  backAria?: string;
  closeAria?: string;
  dialogTitle?: ChannelCopyFormatter;
  dialogDescription?: ChannelCopyFormatter;
  nameLabel?: string;
  namePlaceholder?: string;
  tokenLabel?: ChannelCopyFormatter;
  submit?: string;
};

type ChannelSettingsCopy = {
  settings: {
    channels?: ChannelSettingsCopyView;
  };
};

type ChannelSettingsStateView = {
  channelsLoading: boolean;
  channelsNotice: string;
  channelsError: string;
  channels: ChannelSettingsValue;
  channelConnectForm: ChannelConnectForm;
};

type ChannelSettingsClient = {
  copy: ValueRef<ChannelSettingsCopy>;
  settingsState: ChannelSettingsStateView;
  disconnectChannel: (channel: ChannelView) => void;
  beginChannelConnect: (channel: ChannelView) => void;
  cancelChannelConnect: () => void;
  saveChannelConnection: () => void;
};

function text(value: unknown, fallback = ""): string {
  return typeof value === "string" || typeof value === "number" ? String(value) : fallback;
}

function channelName(channel: ChannelView): string {
  return text(channel.name, text(channel.type, channel.id));
}

export function ChannelSettings({ client }: { client: ChannelSettingsClient }) {
  const state = client.settingsState;
  const copy = client.copy.value;
  const channelCopy = copy.settings.channels || {};
  const channels = state.channels;
  const selectedConnectChannel =
    [...(channels.available || []), ...(channels.connected || [])].find((channel) => (channel.type || channel.id) === state.channelConnectForm.type) || null;
  const selectedConnectName = selectedConnectChannel ? channelName(selectedConnectChannel) : "";

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
          renderItem={(channel: ChannelView) => (
            <List.Item key={channel.id || channel.type} className="provider-row">
              <div className="provider-row__main">
                <span className="provider-row__mark" aria-hidden="true">{providerMark(channel)}</span>
                <div>
                  <div className="provider-row__title">
                    <strong>{channelName(channel)}</strong>
                    <Tag className="provider-row__badge">{channelCopy.connectedBadge || "Connected"}</Tag>
                    {Boolean(channel.enabled) ? <Tag className="provider-row__badge">{channelCopy.enabledBadge || "Enabled"}</Tag> : null}
                  </div>
                  <span>{text(channel.description, text(channel.status, channel.id))}</span>
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
          renderItem={(channel: ChannelView) => (
            <List.Item key={channel.id || channel.type} className="provider-row provider-row--stacked">
              <div className="provider-row__content">
                <div className="provider-row__main">
                  <span className="provider-row__mark" aria-hidden="true">{providerMark(channel)}</span>
                  <div>
                    <div className="provider-row__title">
                      <strong>{channelName(channel)}</strong>
                      <Tag className="provider-row__badge">{channelCopy.builtInBadge || "Built-in"}</Tag>
                    </div>
                    <span>{text(channel.description, channel.id)}</span>
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
              <h3>{typeof channelCopy.dialogTitle === "function" ? channelCopy.dialogTitle(selectedConnectName) : `Connect ${selectedConnectName}`}</h3>
            </div>
            <p>{typeof channelCopy.dialogDescription === "function" ? channelCopy.dialogDescription(selectedConnectName) : ""}</p>
            <Form.Item className="provider-connect-field" label={channelCopy.nameLabel || "Name"}>
              <Input value={state.channelConnectForm.name} placeholder={channelCopy.namePlaceholder || ""} autoComplete="off" onChange={(event) => (state.channelConnectForm.name = event.target.value)} />
            </Form.Item>
            <Form.Item className="provider-connect-field" label={typeof channelCopy.tokenLabel === "function" ? channelCopy.tokenLabel(selectedConnectName) : "Token"}>
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
