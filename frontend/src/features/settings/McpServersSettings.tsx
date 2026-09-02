import { Button, Input, Modal, Popconfirm, Switch } from "antd";
import { useMemo, useState, type FormEvent } from "react";

import type { McpServerDraft, McpServerSummary } from "../../api/mcpConnections";
import { useI18n } from "../../i18n/I18nProvider";
import type { McpConnectionsController } from "../mcp-settings/useMcpConnections";
import type { ToolSettingsController } from "../tool-settings/useToolSettings";


const emptyDraft: McpServerDraft = {
  name: "",
  startOnLaunch: false,
  transport: { type: "stdio", executable: "", arguments: [], workingDirectory: null },
};

function exactCommand(draft: McpServerDraft): string {
  return [draft.transport.executable, ...draft.transport.arguments].join("\n");
}

export function McpServersSettings({ controller, toolSettings, modalContainer = null }: { controller: McpConnectionsController; toolSettings: ToolSettingsController; modalContainer?: HTMLElement | null }) {
  const { t } = useI18n();
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<McpServerDraft>(emptyDraft);
  const [argumentsText, setArgumentsText] = useState("");
  const [confirmDraft, setConfirmDraft] = useState<McpServerDraft | null>(null);
  const [startCandidate, setStartCandidate] = useState<McpServerSummary | null>(null);
  const busy = controller.busyServerId !== null;

  const openEditor = (server?: McpServerSummary) => {
    const next = server ? { name: server.name, startOnLaunch: server.startOnLaunch, transport: server.transport } : emptyDraft;
    setEditingId(server?.id ?? null);
    setDraft(next);
    setArgumentsText(next.transport.arguments.join("\n"));
    setEditorOpen(true);
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const normalized = { ...draft, transport: { ...draft.transport, arguments: argumentsText.split("\n").map((item) => item.trim()).filter(Boolean), workingDirectory: draft.transport.workingDirectory?.trim() || null } };
    if (!normalized.name.trim() || !normalized.transport.executable.trim()) return;
    setConfirmDraft(normalized);
    setEditorOpen(false);
  };
  const save = async () => {
    if (!confirmDraft) return;
    const error = editingId ? await controller.update(editingId, confirmDraft) : await controller.create(confirmDraft);
    if (error === null) {
      setConfirmDraft(null);
      setEditorOpen(false);
      setEditingId(null);
      setDraft(emptyDraft);
      setArgumentsText("");
    }
  };
  const statusLabels = useMemo(() => ({ disabled: t("mcp.status.disabled"), stopped: t("mcp.status.stopped"), starting: t("mcp.status.starting"), connected: t("mcp.status.connected"), error: t("mcp.status.error"), stopping: t("mcp.status.stopping") }), [t]);

  return <>
    <div className="settings-mcp-heading"><p className="settings-card-description">{t("mcp.description")}</p><Button type="primary" onClick={() => openEditor()} disabled={busy}>{t("mcp.addServer")}</Button></div>
    {!controller.loaded && !controller.error ? <p role="status">{t("mcp.loading")}</p> : null}
    {controller.error ? <div className="settings-model-load-error" role="alert"><p>{controller.error}</p><button type="button" className="settings-secondary-button" onClick={() => void controller.reload()}>{t("common.retry")}</button></div> : null}
    {controller.loaded && controller.servers.length === 0 ? <p className="settings-provider-feedback">{t("mcp.empty")}</p> : null}
    <div className="settings-mcp-list">{controller.servers.map((server) => {
      const serverBusy = controller.busyServerId === server.id;
      const tools = controller.tools[server.id] ?? [];
      return <section className="settings-mcp-server" key={server.id} aria-label={t("mcp.serverLabel", { server: server.name })}>
        <div className="settings-mcp-server-header"><span><strong>{server.name}</strong><small>{statusLabels[server.status]}{server.protocolVersion ? ` · MCP ${server.protocolVersion}` : ""}</small></span><span className="settings-mcp-actions"><Button onClick={() => void controller.test(server.id)} disabled={busy}>{t("mcp.test")}</Button>{server.status === "connected" ? <Button onClick={() => void controller.stop(server.id)} disabled={busy}>{t("mcp.stop")}</Button> : <Button type="primary" onClick={() => setStartCandidate(server)} disabled={busy}>{t("mcp.start")}</Button>}<Button onClick={() => openEditor(server)} disabled={busy}>{t("mcp.edit")}</Button><Popconfirm title={t("mcp.removeConfirm")} okText={t("common.remove")} cancelText={t("common.cancel")} getPopupContainer={() => modalContainer ?? document.body} onConfirm={() => void controller.remove(server.id)}><Button danger disabled={busy}>{t("common.remove")}</Button></Popconfirm></span></div>
        <code className="settings-mcp-command">{server.transport.executable}{server.transport.arguments.map((argument) => `\n${argument}`)}</code>
        <p className="settings-control-description">{t("mcp.toolSummary", { supported: String(server.toolCount), unsupported: String(server.unsupportedToolCount) })}</p>
        {server.status === "connected" ? <div className="settings-mcp-tools">{tools.map((tool) => {
          const enabled = toolSettings.settings.enabledTools.includes(tool.id);
          return <div className="settings-mcp-tool" key={tool.id}><span><strong>{tool.title ?? tool.originalName}</strong><small>{tool.originalName} · {t("mcp.approvalAlways")}</small><span>{tool.description}</span>{!tool.supported ? <em>{t("mcp.unsupportedSchema")}</em> : null}</span><Switch aria-label={t("tools.toggleTool", { tool: tool.title ?? tool.originalName })} checked={enabled} disabled={!tool.supported || !toolSettings.settings.enabled || toolSettings.saving} onChange={(next) => void toolSettings.saveToolEnabled(tool.id, next)} /></div>;
        })}</div> : null}
      </section>;
    })}</div>

    <Modal getContainer={false} open={editorOpen} title={editingId ? t("mcp.editServer") : t("mcp.addServer")} footer={null} destroyOnHidden onCancel={() => { if (!busy) setEditorOpen(false); }}>
      <form className="settings-mcp-form" onSubmit={submit}>
        <label>{t("mcp.name")}<Input value={draft.name} maxLength={80} onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))} /></label>
        <label>{t("mcp.executable")}<Input value={draft.transport.executable} onChange={(event) => setDraft((current) => ({ ...current, transport: { ...current.transport, executable: event.target.value } }))} /></label>
        <label>{t("mcp.arguments")}<Input.TextArea rows={4} value={argumentsText} onChange={(event) => setArgumentsText(event.target.value)} /></label>
        <label>{t("mcp.workingDirectory")}<Input value={draft.transport.workingDirectory ?? ""} onChange={(event) => setDraft((current) => ({ ...current, transport: { ...current.transport, workingDirectory: event.target.value || null } }))} /></label>
        <label className="settings-mcp-autostart"><span>{t("mcp.startOnLaunch")}</span><Switch checked={draft.startOnLaunch} onChange={(value) => setDraft((current) => ({ ...current, startOnLaunch: value }))} /></label>
        <div className="settings-mcp-modal-actions"><Button onClick={() => setEditorOpen(false)}>{t("common.cancel")}</Button><Button type="primary" htmlType="submit">{t("mcp.continue")}</Button></div>
      </form>
    </Modal>
    <Modal getContainer={false} open={confirmDraft !== null} title={t("mcp.commandConfirmTitle")} okText={t("mcp.saveConfiguration")} cancelText={t("common.cancel")} confirmLoading={busy} onOk={() => void save()} onCancel={() => { setConfirmDraft(null); setEditorOpen(true); }}><p>{t("mcp.commandWarning")}</p><pre className="settings-mcp-command-preview">{confirmDraft ? exactCommand(confirmDraft) : ""}</pre><p>{t("mcp.cwdPreview", { path: confirmDraft?.transport.workingDirectory ?? "—" })}</p></Modal>
    <Modal getContainer={false} open={startCandidate !== null} title={t("mcp.startConfirmTitle")} okText={t("mcp.start")} cancelText={t("common.cancel")} confirmLoading={busy} onOk={async () => { if (!startCandidate) return; const result = await controller.start(startCandidate.id); if (result === null) setStartCandidate(null); }} onCancel={() => setStartCandidate(null)}><p>{t("mcp.commandWarning")}</p><pre className="settings-mcp-command-preview">{startCandidate ? exactCommand(startCandidate) : ""}</pre></Modal>
  </>;
}
