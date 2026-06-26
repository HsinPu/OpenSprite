import { ArrowLeftOutlined, CloseOutlined, ReloadOutlined } from "@ant-design/icons";
import { Button, Form, Input, InputNumber, Select, Tag } from "antd";
import { mcpRuntimeStatus, mcpToolGroups } from "./mcpHelpers";
import { SettingsCard, SettingsRow, SettingsSectionTitle, SettingsStatus } from "./settingsPrimitives";

type AnyRecord = Record<string, any>;
type ValueRef<T> = { value: T };

type McpSettingsClient = {
  copy: ValueRef<AnyRecord>;
  settingsState: AnyRecord;
  reloadMcpSettings: () => void;
  toggleMcpToolGroup: (serverId: string) => void;
  beginMcpCreate: () => void;
  beginMcpEdit: (server: AnyRecord) => void;
  removeMcpServer: (server: AnyRecord) => void;
  cancelMcpEdit: () => void;
  saveMcpServer: () => void;
  toggleMcpAdvanced: () => void;
  toggleMcpJsonInput: () => void;
  applyMcpJson: () => void;
};

export function McpSettings({ client }: { client: McpSettingsClient }) {
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
