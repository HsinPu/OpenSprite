import { ArrowLeftOutlined, CloseOutlined } from "@ant-design/icons";
import { Button, Form, Input, List, Tag } from "antd";
import { providerMark } from "./providerHelpers";
import { SettingsCard, SettingsSectionTitle, SettingsStatus } from "./settingsPrimitives";

type AnyRecord = Record<string, any>;
type ValueRef<T> = { value: T };

type ChannelSettingsClient = {
  copy: ValueRef<AnyRecord>;
  settingsState: AnyRecord;
  disconnectChannel: (channel: AnyRecord) => void;
  beginChannelConnect: (channel: AnyRecord) => void;
  cancelChannelConnect: () => void;
  saveChannelConnection: () => void;
};

export function ChannelSettings({ client }: { client: ChannelSettingsClient }) {
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
