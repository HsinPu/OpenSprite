import { Alert, Button, Drawer, Dropdown, Empty, Grid, Input, Modal, Popconfirm, Select, Switch, Tabs, Tag, Tooltip, Upload } from "antd";
import { DeleteOutlined, PlusOutlined, ReloadOutlined, UploadOutlined } from "@ant-design/icons";
import "./skills.css";
import { useCallback, useEffect, useRef, useState } from "react";
import { listSkills, skillRequest, importSkillZip, skillStateLabels, type Skill, type SkillList, type SkillScope } from "../../api/skills";
import { FolderValidationError } from "./skillFolderImport";
import { inspectSkillZip, type ZipCandidate } from "./skillZipImport";
import type { WorkspaceController } from "../workspaces/useWorkspaces";
import { useI18n } from "../../i18n/I18nProvider";

type MutationResult = "refreshed" | "refresh_failed" | "failed";

export function SkillsSettings({ workspaces, container, onOverlayChange }: { workspaces: Pick<WorkspaceController, "catalog">; container: HTMLElement | null; onOverlayChange?: (open: boolean) => void }) {
  const { t } = useI18n();
  const screens = Grid.useBreakpoint();
  const [scope, setScope] = useState<SkillScope>("global");
  const [workspaceId, setWorkspaceId] = useState(workspaces.catalog?.activeWorkspaceId ?? "");
  const [data, setData] = useState<SkillList | null>(null);
  const [globals, setGlobals] = useState<Skill[]>([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editor, setEditor] = useState(false);
  const [content, setContent] = useState("");
  const [importedName, setImportedName] = useState("");
  const [folder, setFolder] = useState<ZipCandidate | null>(null);
  const [editorCommitted, setEditorCommitted] = useState(false);
  const folderReading = useRef(false);
  const [editRevision, setEditRevision] = useState(0);
  const generation = useRef(0);
  const opener = useRef<HTMLElement | null>(null);
  useEffect(() => { onOverlayChange?.(editor); return () => onOverlayChange?.(false); }, [editor, onOverlayChange]);
  useEffect(() => {
    if (!editor) return;
    const dismissEditor = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopImmediatePropagation();
      if (!busy) { setEditor(false); opener.current?.focus(); }
    };
    document.addEventListener("keydown", dismissEditor, true);
    return () => document.removeEventListener("keydown", dismissEditor, true);
  }, [editor, busy]);
  const reload = useCallback(async (): Promise<boolean> => {
    const current = ++generation.current;
    setLoading(true);
    try {
      const value = await listSkills(scope, scope === "workspace" ? workspaceId : undefined);
      const inherited = scope === "workspace" ? await listSkills("global", workspaceId) : null;
      if (current !== generation.current) return false;
      setData(value); setGlobals(inherited?.skills ?? []); setError(null);
      return true;
    } catch (reason) {
      if (current === generation.current) { setData(null); setGlobals([]); setError(reason instanceof Error ? reason.message : "network_error"); }
      return false;
    }
    finally { if (current === generation.current) setLoading(false); }
  }, [scope, workspaceId]);
  useEffect(() => { void reload(); return () => { generation.current++; }; }, [reload]);
  const mutate = async (path: string, method: string, payload?: unknown): Promise<MutationResult> => {
    if (busy) return "failed";
    setBusy(true);
    try {
      await skillRequest(path, method, payload);
      return await reload() ? "refreshed" : "refresh_failed";
    }
    catch (reason) { setError(reason instanceof Error ? reason.message : "network_error"); return "failed"; }
    finally { setBusy(false); }
  };
  const open = (target: HTMLElement) => {
    opener.current = target;
    setError(null); setImportedName(""); setFolder(null); setEditorCommitted(false);
    setContent("---\nname: \ndescription: \n---\n");
    setEditRevision(data?.revision ?? 0); setEditor(true);
  };
  const close = () => { if (!busy) { setEditor(false); opener.current?.focus(); } };
  const unavailable = scope === "workspace" && workspaces.catalog?.workspaces.find(item => item.id === workspaceId)?.availability !== "available";
  const form = <div style={{ display: "grid", gap: 12 }}>
    <p>{t("skills.saveHint")}</p>
    <div style={{ display: "grid", gap: 8, minWidth: 0 }}>
      <Upload accept=".md,text/markdown" multiple={false} showUploadList={false} disabled={busy || editorCommitted} beforeUpload={async file => {
        if (busy || editorCommitted) return Upload.LIST_IGNORE;
        if (file.size > 65536) { setError("content_too_large"); return Upload.LIST_IGNORE; }
        if (!file.name.toLowerCase().endsWith(".md")) { setError("invalid_format"); return Upload.LIST_IGNORE; }
        setBusy(true);
        setError(null);
        try {
          const buffer = await file.arrayBuffer();
          setContent(new TextDecoder("utf-8", { fatal: true }).decode(buffer));
          setImportedName(file.name);
        } catch { setError("invalid_format"); }
        finally { setBusy(false); }
        return Upload.LIST_IGNORE;
      }}>
        <Button icon={<UploadOutlined aria-hidden="true" />} disabled={busy || editorCommitted}>{t("skills.import")}</Button>
      </Upload>
      {importedName ? <span role="status" style={{ overflowWrap: "anywhere" }}>{importedName}</span> : null}
    </div>
    <label>{t("skills.content")}<Input.TextArea value={content} onChange={event => setContent(event.target.value)} rows={14} disabled={busy || editorCommitted} /></label>
    {error ? <Alert type="error" title={t("skills.error", { code: error })} /> : null}
    <Button type="primary" loading={busy} disabled={unavailable || editorCommitted} onClick={async () => {
      const payload = { scope, workspaceId: scope === "workspace" ? workspaceId : null, content, expectedRevision: editRevision };
      const result = await mutate("", "POST", payload);
      if (result === "refreshed") { setEditor(false); opener.current?.focus(); }
      else if (result === "refresh_failed") setEditorCommitted(true);
    }}>{t("common.save")}</Button>
    {editorCommitted ? <Button loading={loading} onClick={async () => { if (await reload()) { setEditorCommitted(false); setEditor(false); opener.current?.focus(); } }}>{t("common.retry")}</Button> : null}
  </div>;
  const folderForm = folder ? <div style={{ display: "grid", gap: 12, minWidth: 0 }}>
    <Alert type="info" title={t("skills.folderHint")} />
    <p>{scope === "global" ? t("skills.global") : `${t("skills.workspace")}: ${workspaces.catalog?.workspaces.find(item => item.id === workspaceId)?.name ?? workspaceId}`}</p>
    <h3>{folder.name}</h3><p>{folder.description}</p>
    <label>{t("skills.directoryName")}<Input value={folder.directoryName} disabled={busy || editorCommitted} onChange={event => setFolder({ ...folder, directoryName: event.target.value })} /></label>
    <p style={{ overflowWrap: "anywhere" }}>{t("skills.folderSummary", { name: folder.directoryName, count: folder.files.length, size: folder.totalBytes })}</p>
    <ul aria-label={t("skills.folderFiles")} style={{ maxHeight: 200, overflow: "auto", paddingInlineStart: 24 }}>
      {folder.files.map(item => <li key={item.path} style={{ overflowWrap: "anywhere" }}>{item.path} ({item.file.size} B)</li>)}
    </ul>
    <label>{t("skills.content")}<Input.TextArea readOnly value={folder.content} rows={10} /></label>
    {error ? <Alert type="error" title={t("skills.error", { code: error })} /> : null}
    <Button type="primary" loading={busy} disabled={unavailable || editorCommitted} onClick={async () => {
      if (busy) return;
      setBusy(true); setError(null);
      try {
        await importSkillZip(scope, scope === "workspace" ? workspaceId : null, folder.directoryName, folder.archive, editRevision);
        if (await reload()) { setEditor(false); opener.current?.focus(); }
        else setEditorCommitted(true);
      } catch (reason) { setError(reason instanceof Error ? reason.message : "network_error"); }
      finally { setBusy(false); }
    }}>{t("skills.confirmImport")}</Button>
    {editorCommitted ? <Button loading={loading} onClick={async () => { if (await reload()) { setEditorCommitted(false); setEditor(false); opener.current?.focus(); } }}>{t("common.retry")}</Button> : null}
  </div> : null;
  return <section className="skills-settings" aria-label={t("settings.category.skills")}>
    <div className="skills-heading"><h2>{t("settings.category.skills")}</h2><label className="skills-master">{t("skills.master")} <Switch aria-label={t("skills.master")} checked={data?.enabled ?? false} disabled={!data || busy || loading} onChange={enabled => void mutate("/settings", "PUT", { enabled, expectedRevision: data?.revision })} /></label></div><p>{t("skills.intro")}</p>
    <Tabs activeKey={scope} onChange={key => { if (!busy) { generation.current++; setData(null); setGlobals([]); setError(null); setScope(key as SkillScope); } }} items={[{ key: "global", label: t("skills.global"), disabled: busy }, { key: "workspace", label: t("skills.workspace"), disabled: busy }]} />
    {scope === "workspace" ? <Select getPopupContainer={() => container ?? document.body} aria-label={t("skills.workspace")} value={workspaceId} style={{ width: "100%" }} disabled={busy} onChange={value => { generation.current++; setData(null); setGlobals([]); setError(null); setWorkspaceId(value); }} options={workspaces.catalog?.workspaces.map(item => ({ value: item.id, label: item.kind === "default" ? t("workspaces.default") : item.name }))} /> : null}
    {error ? <Alert type="error" title={t("skills.error", { code: error })} action={<Button loading={loading} disabled={busy} onClick={() => void reload()}>{t("common.retry")}</Button>} /> : null}
    <p>{t("skills.capabilityHint")}</p>
    <div className="skills-toolbar">
      <h3>{t(scope === "global" ? "skills.global" : "skills.workspace")} Skills <span>· {data?.skills.length ?? "—"}</span></h3>
      <div className="skills-toolbar-actions">
      <Tooltip getPopupContainer={() => container ?? document.body} title={t("skills.scan")}><Button aria-label={t("skills.scan")} icon={<ReloadOutlined />} disabled={busy || loading || !data || unavailable} onClick={() => void mutate("/scan", "POST", { scope, workspaceId: scope === "workspace" ? workspaceId : null, expectedRevision: data?.revision })} /></Tooltip>
      <Dropdown getPopupContainer={() => container ?? document.body} trigger={["click"]} popupRender={() => <div className="skills-import-menu">
      <Button type="text" onClick={event => void open(event.currentTarget)}>{t("skills.import")}</Button>
      <Upload accept=".zip,application/zip" multiple={false} showUploadList={false} disabled={busy || loading || !data || unavailable} beforeUpload={async file => {
        if (folderReading.current || busy) return Upload.LIST_IGNORE;
        folderReading.current = true; setBusy(true); setError(null);
        try {
          const candidate = await inspectSkillZip(file);
          setEditorCommitted(false); setFolder(candidate); setEditRevision(data?.revision ?? 0); setEditor(true);
        } catch (reason) {
          setError(reason instanceof FolderValidationError ? `${reason.code}${reason.path ? `: ${reason.path}` : ""}` : "invalid_format");
        } finally { folderReading.current = false; setBusy(false); }
        return Upload.LIST_IGNORE;
      }}>
        <Button icon={<UploadOutlined aria-hidden="true" />} disabled={busy || loading || !data || unavailable} onClick={event => { opener.current = event.currentTarget; }}>{t("skills.importFolder")}</Button>
      </Upload>
      </div>}><Button icon={<UploadOutlined />} disabled={busy || loading || !data || unavailable}>{t("skills.importMenu")} ▾</Button></Dropdown>
      <Button type="primary" icon={<PlusOutlined />} disabled={busy || loading || !data || unavailable} onClick={event => void open(event.currentTarget)}>{t("skills.create")}</Button>
      </div>
    </div>
    {!loading && data?.skills.length === 0 ? <Empty description={t("skills.empty")} /> : null}
    {data?.skills.map(item => <article key={item.id} className="skills-row">
      <div className="skills-row-info"><h3 title={item.name}>{item.name}</h3>
        {item.state !== "ready" && item.state !== "disabled" ? <Tag role="status">{t(skillStateLabels[item.reason as keyof typeof skillStateLabels] ?? "skills.unavailable")}</Tag> : null}
        {scope === "workspace" && !item.effective ? <p className="skills-row-hint">{t("skills.noFallback")}</p> : null}
      </div>
      <div className="skills-row-actions"><Switch aria-label={t("skills.toggle", { name: item.name })} checked={item.enabled} disabled={busy || loading} onChange={enabled => void mutate(`/${item.id}/enabled`, "PUT", { enabled, expectedRevision: data.revision })} />
        <Popconfirm title={t("skills.archive")} description={scope === "workspace" ? t("skills.removeInheritance") : undefined} getPopupContainer={() => container ?? document.body} onConfirm={() => mutate(`/${item.id}?expectedRevision=${data.revision}`, "DELETE")}><Button className="skills-remove" type="text" title={`${t("common.remove")} Skill`} aria-label={`${t("common.remove")} ${item.name}`} icon={<DeleteOutlined aria-hidden="true" />} disabled={busy || loading} /></Popconfirm>
      </div></article>)}
    {scope === "workspace" ? <><h3>{t("skills.inherited")}</h3><p>{t("skills.inheritanceHint")}</p></> : null}
    {globals.map(item => <article key={item.id} className="skills-row"><div className="skills-row-info"><h3 title={item.name}>{item.name}</h3><Tag role="status">{t(skillStateLabels[item.reason as keyof typeof skillStateLabels] ?? "skills.unavailable")}</Tag></div></article>)}
    {screens.md ? <Modal open={editor} title={t(folder ? "skills.importFolder" : "skills.content")} onCancel={close} afterClose={() => opener.current?.focus()} footer={null} getContainer={container ?? undefined} destroyOnHidden>{folder ? folderForm : form}</Modal> : <Drawer open={editor} title={t(folder ? "skills.importFolder" : "skills.content")} onClose={close} afterOpenChange={open => { if (!open) opener.current?.focus(); }} size="100%" getContainer={container ?? undefined} destroyOnHidden>{folder ? folderForm : form}</Drawer>}
  </section>;
}
