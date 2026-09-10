import { FolderOpenOutlined, MoreOutlined, PlusOutlined } from "@ant-design/icons";
import { Button, Dropdown, Input, Modal, Select, Space, Switch, Tag } from "antd";
import { useMemo, useRef, useState, type FormEvent } from "react";

import type { McpServerDraft, McpServerSummary } from "../../api/mcpConnections";
import { useI18n } from "../../i18n/I18nProvider";
import type { McpConnectionsController } from "../mcp-settings/useMcpConnections";
import { useLocalPathPicker } from "../local-paths/useLocalPathPicker";
import type { ToolSettingsController } from "../tool-settings/useToolSettings";


const emptyDraft: McpServerDraft = {
  name: "",
  startOnLaunch: true,
  transport: { type: "stdio", executable: "", arguments: [], workingDirectory: null },
  authentication: { type: "none" },
};

function exactCommand(draft: Pick<McpServerDraft, "transport">): string {
  return draft.transport.type === "stdio"
    ? [draft.transport.executable, ...draft.transport.arguments].join("\n")
    : draft.transport.url;
}

export function McpServersSettings({ controller, toolSettings, modalContainer = null }: { controller: McpConnectionsController; toolSettings: ToolSettingsController; modalContainer?: HTMLElement | null }) {
  const { t } = useI18n();
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<McpServerDraft>(emptyDraft);
  const [argumentsText, setArgumentsText] = useState("");
  const [confirmDraft, setConfirmDraft] = useState<McpServerDraft | null>(null);
  const [startCandidate, setStartCandidate] = useState<McpServerSummary | null>(null);
  const [removeCandidate, setRemoveCandidate] = useState<McpServerSummary | null>(null);
  const [existingBearerConfigured, setExistingBearerConfigured] = useState(false);
  const pathPicker = useLocalPathPicker();
  const busy = controller.busyServerId !== null;
  const opener = useRef<HTMLButtonElement | null>(null);
  const sectionRef = useRef<HTMLElement | null>(null);
  const restoreFocus = () => {
    if (editorOpen || confirmDraft || startCandidate || removeCandidate) return;
    if (opener.current?.isConnected) opener.current.focus();
    else sectionRef.current?.querySelector<HTMLButtonElement>("button")?.focus();
  };

  const openEditor = (server?: McpServerSummary) => {
    const next: McpServerDraft = server ? {
      name: server.name,
      startOnLaunch: server.startOnLaunch,
      transport: server.transport,
      authentication: server.authentication.type === "bearer-token"
        ? { type: "bearer-token", token: null }
        : { type: "none" },
    } : emptyDraft;
    setEditingId(server?.id ?? null);
    setDraft(next);
    setArgumentsText(next.transport.type === "stdio" ? next.transport.arguments.join("\n") : "");
    setExistingBearerConfigured(
      server?.authentication.type === "bearer-token"
      && server.authentication.configured
    );
    setEditorOpen(true);
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const normalized: McpServerDraft = draft.transport.type === "stdio"
      ? { ...draft, authentication: { type: "none" }, transport: { ...draft.transport, arguments: argumentsText.split("\n").map((item) => item.trim()).filter(Boolean), workingDirectory: draft.transport.workingDirectory?.trim() || null } }
      : { ...draft, transport: { ...draft.transport, url: draft.transport.url.trim() } };
    if (!normalized.name.trim() || (normalized.transport.type === "stdio" ? !normalized.transport.executable.trim() : !normalized.transport.url)) return;
    if (
      normalized.authentication.type === "bearer-token"
      && !normalized.authentication.token?.trim()
      && !existingBearerConfigured
    ) return;
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
      setExistingBearerConfigured(false);
    }
  };
  const statusLabels = useMemo(() => ({ disabled: t("mcp.status.disabled"), stopped: t("mcp.status.stopped"), starting: t("mcp.status.starting"), connected: t("mcp.status.connected"), error: t("mcp.status.error"), stopping: t("mcp.status.stopping") }), [t]);

  return <>
    <section ref={sectionRef} className="settings-card settings-mcp-section" aria-label={t("mcp.serversTitle")} onClickCapture={(event) => { if (event.target instanceof Element) { const button = event.target.closest("button"); if (button) opener.current = button; } }}>
    <div className="settings-mcp-heading"><h3>{t("mcp.serversTitle")}</h3><Button type="primary" icon={<PlusOutlined aria-hidden="true" />} onClick={() => openEditor()} disabled={busy}>{t("mcp.addServer")}</Button></div>
    <p className="settings-card-description">{t("mcp.description")}</p>
    {!controller.loaded && !controller.error ? <p role="status">{t("mcp.loading")}</p> : null}
    {controller.error ? <div className="settings-model-load-error" role="alert"><p>{controller.error}</p><button type="button" className="settings-secondary-button" onClick={() => void controller.reload()}>{t("common.retry")}</button></div> : null}
    {controller.loaded && controller.servers.length === 0 ? <p className="settings-provider-feedback">{t("mcp.empty")}</p> : null}
    <div className="settings-mcp-list">{controller.servers.map((server) => {
      const tools = controller.tools[server.id] ?? [];
      return <section className="settings-mcp-server" key={server.id} aria-label={t("mcp.serverLabel", { server: server.name })}>
        <div className="settings-mcp-server-header"><span><span className="settings-tool-name"><strong>{server.name}</strong><Tag color={server.status === "connected" ? "success" : server.status === "error" ? "error" : undefined}>{statusLabels[server.status]}</Tag></span><small>{t(server.transport.type === "stdio" ? "mcp.transport.stdio" : "mcp.transport.streamableHttp")}</small></span><span className="settings-mcp-actions">{server.status === "connected" ? <Button onClick={() => void controller.stop(server.id)} disabled={busy}>{t(server.transport.type === "stdio" ? "mcp.stop" : "mcp.disconnect")}</Button> : <Button type="primary" onClick={() => setStartCandidate(server)} disabled={busy}>{t(server.transport.type === "stdio" ? "mcp.start" : "mcp.connect")}</Button>}<Dropdown trigger={["click"]} getPopupContainer={() => modalContainer ?? document.body} menu={{ items: [{ key: "edit", label: t("mcp.edit") }, { key: "test", label: t("mcp.test") }, { key: "remove", label: t("common.remove"), danger: true }], onClick: ({ key }) => { if (busy) return; if (key === "edit") openEditor(server); else if (key === "test") void controller.test(server.id); else setRemoveCandidate(server); } }}><Button icon={<MoreOutlined />} aria-label={t("mcp.actions", { server: server.name })} disabled={busy} /></Dropdown></span></div>
        <details className="settings-mcp-details"><summary>{t("mcp.details")}</summary>
        <p className="settings-control-description">{t(server.authentication.type === "none" ? "mcp.auth.none" : server.authentication.configured ? "mcp.auth.bearerConfigured" : "mcp.auth.bearerMissing")}{server.protocolVersion ? ` · MCP ${server.protocolVersion}` : ""}</p>
        <p className="settings-control-description">{t("mcp.toolSummary", { supported: String(server.toolCount), unsupported: String(server.unsupportedToolCount) })}</p>
        {server.status === "connected" ? <div className="settings-mcp-tools">{tools.map((tool) => {
          const enabled = toolSettings.settings.enabledTools.includes(tool.id);
          return <div className="settings-mcp-tool" key={tool.id}><span><strong>{tool.title ?? tool.originalName}</strong><small>{tool.originalName} · {t("mcp.approvalAlways")}</small><span>{tool.description}</span>{!tool.supported ? <em>{t("mcp.unsupportedSchema")}</em> : null}</span><Switch aria-label={t("tools.toggleTool", { tool: tool.title ?? tool.originalName })} checked={enabled} disabled={!tool.supported || !toolSettings.settings.enabled || toolSettings.saving} onChange={(next) => void toolSettings.saveToolEnabled(tool.id, next)} /></div>;
        })}</div> : null}
        </details>
      </section>;
    })}</div>
    </section>

    <Modal afterClose={restoreFocus} getContainer={false} open={editorOpen} title={editingId ? t("mcp.editServer") : t("mcp.addServer")} footer={null} destroyOnHidden onCancel={() => { if (!busy) setEditorOpen(false); }}>
      <form className="settings-mcp-form" onSubmit={submit}>
        <p className="settings-control-description">{t("mcp.saveHint")}</p>
        <label>{t("mcp.name")}<Input value={draft.name} maxLength={80} onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))} /></label>
        <div className="settings-mcp-form-field"><label htmlFor="mcp-transport-type">{t("mcp.transport.label")}</label><Select id="mcp-transport-type" value={draft.transport.type} options={[{ value: "stdio", label: t("mcp.transport.stdio") }, { value: "streamable-http", label: t("mcp.transport.streamableHttp") }]} getPopupContainer={() => modalContainer ?? document.body} onChange={(value: "stdio" | "streamable-http") => { setArgumentsText(""); setDraft((current) => ({ ...current, authentication: { type: "none" }, transport: value === "stdio" ? { type: "stdio", executable: "", arguments: [], workingDirectory: null } : { type: "streamable-http", url: "" } })); }} /></div>
        {draft.transport.type === "stdio" ? <>
          <div className="settings-mcp-form-field"><label htmlFor="mcp-executable">{t("mcp.executable")}</label><Space.Compact block><Input id="mcp-executable" value={draft.transport.executable} onChange={(event) => setDraft((current) => current.transport.type === "stdio" ? ({ ...current, transport: { ...current.transport, executable: event.target.value } }) : current)} /><Button icon={<FolderOpenOutlined />} loading={pathPicker.picking === "executable"} disabled={pathPicker.picking !== null} onClick={async () => { const selected = await pathPicker.pick("executable"); if (selected) setDraft((current) => current.transport.type === "stdio" ? ({ ...current, transport: { ...current.transport, executable: selected } }) : current); }}>{t("localPath.browseExecutable")}</Button></Space.Compact></div>
          <label>{t("mcp.arguments")}<Input.TextArea rows={4} value={argumentsText} onChange={(event) => setArgumentsText(event.target.value)} /></label>
          <div className="settings-mcp-form-field"><label htmlFor="mcp-working-directory">{t("mcp.workingDirectoryOptional")}</label><Space.Compact block><Input id="mcp-working-directory" value={draft.transport.workingDirectory ?? ""} onChange={(event) => setDraft((current) => current.transport.type === "stdio" ? ({ ...current, transport: { ...current.transport, workingDirectory: event.target.value || null } }) : current)} /><Button icon={<FolderOpenOutlined />} loading={pathPicker.picking === "directory"} disabled={pathPicker.picking !== null} onClick={async () => { const selected = await pathPicker.pick("directory"); if (selected) setDraft((current) => current.transport.type === "stdio" ? ({ ...current, transport: { ...current.transport, workingDirectory: selected } }) : current); }}>{t("localPath.browseDirectory")}</Button></Space.Compact><span className="settings-control-description">{t("mcp.workingDirectoryHint")}</span></div>
          {pathPicker.error ? <p className="settings-inline-error" role="alert">{pathPicker.error}</p> : null}
        </> : <>
          <label>{t("mcp.url")}<Input value={draft.transport.url} placeholder="https://example.com/mcp" onChange={(event) => setDraft((current) => current.transport.type === "streamable-http" ? ({ ...current, transport: { ...current.transport, url: event.target.value } }) : current)} /></label>
          <div className="settings-mcp-form-field"><label htmlFor="mcp-auth-type">{t("mcp.auth.label")}</label><Select id="mcp-auth-type" value={draft.authentication.type} options={[{ value: "none", label: t("mcp.auth.none") }, { value: "bearer-token", label: t("mcp.auth.bearer") }]} getPopupContainer={() => modalContainer ?? document.body} onChange={(value: "none" | "bearer-token") => setDraft((current) => ({ ...current, authentication: value === "none" ? { type: "none" } : { type: "bearer-token", token: null } }))} /></div>
          {draft.authentication.type === "bearer-token" ? <label>{t("mcp.auth.token")}<Input.Password value={draft.authentication.token ?? ""} maxLength={8192} autoComplete="new-password" placeholder={existingBearerConfigured ? t("mcp.auth.keepExisting") : t("mcp.auth.tokenPlaceholder")} onChange={(event) => setDraft((current) => current.authentication.type === "bearer-token" ? ({ ...current, authentication: { ...current.authentication, token: event.target.value || null } }) : current)} /></label> : null}
          <p className="settings-control-description">{t(draft.authentication.type === "bearer-token" ? "mcp.auth.encryptedHint" : "mcp.httpNoAuth")}</p>
        </>}
        <details className="settings-mcp-details"><summary>{t("mcp.advanced")}</summary><label className="settings-mcp-autostart"><span>{t("mcp.startOnLaunch")}</span><Switch checked={draft.startOnLaunch} onChange={(value) => setDraft((current) => ({ ...current, startOnLaunch: value }))} /></label></details>
        <div className="settings-mcp-modal-actions"><Button onClick={() => setEditorOpen(false)}>{t("common.cancel")}</Button><Button type="primary" htmlType="submit">{t("mcp.continue")}</Button></div>
      </form>
    </Modal>
    <Modal afterClose={restoreFocus} getContainer={false} open={confirmDraft !== null} title={t("mcp.commandConfirmTitle")} okText={t("mcp.saveConfiguration")} cancelText={t("common.cancel")} confirmLoading={busy} onOk={() => void save()} onCancel={() => { setConfirmDraft(null); setEditorOpen(true); }}><p>{t(confirmDraft?.transport.type === "streamable-http" ? "mcp.networkWarning" : "mcp.commandWarning")}</p><pre className="settings-mcp-command-preview">{confirmDraft ? exactCommand(confirmDraft) : ""}</pre>{confirmDraft?.transport.type === "stdio" ? <p>{t("mcp.cwdPreview", { path: confirmDraft.transport.workingDirectory ?? "—" })}</p> : <p>{t("mcp.urlSecretWarning")}</p>}</Modal>
    <Modal afterClose={restoreFocus} getContainer={false} open={startCandidate !== null} title={t(startCandidate?.transport.type === "streamable-http" ? "mcp.connectConfirmTitle" : "mcp.startConfirmTitle")} okText={t(startCandidate?.transport.type === "streamable-http" ? "mcp.connect" : "mcp.start")} cancelText={t("common.cancel")} confirmLoading={busy} onOk={async () => { if (!startCandidate) return; const result = await controller.start(startCandidate.id); if (result === null) setStartCandidate(null); }} onCancel={() => setStartCandidate(null)}><p>{t(startCandidate?.transport.type === "streamable-http" ? "mcp.networkWarning" : "mcp.commandWarning")}</p><pre className="settings-mcp-command-preview">{startCandidate ? exactCommand(startCandidate) : ""}</pre></Modal>
    <Modal afterClose={restoreFocus} getContainer={false} open={removeCandidate !== null} title={t("mcp.removeConfirm")} okText={t("common.remove")} cancelText={t("common.cancel")} okButtonProps={{ danger: true }} confirmLoading={busy} onCancel={() => { if (!busy) setRemoveCandidate(null); }} onOk={async () => { if (!removeCandidate) return; const error = await controller.remove(removeCandidate.id); if (error === null) setRemoveCandidate(null); }}>{removeCandidate?.name}</Modal>
  </>;
}
