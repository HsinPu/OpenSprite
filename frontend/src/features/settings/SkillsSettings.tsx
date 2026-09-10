import { Alert, Button, Drawer, Dropdown, Grid, Input, Modal, Pagination, Popconfirm, Select, Switch, Tabs, Tag, Tooltip, Upload } from "antd";
import { DeleteOutlined, MoreOutlined, PlusOutlined, ReloadOutlined, UploadOutlined } from "@ant-design/icons";
import "./skills.css";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { listSkills, skillRequest, importSkillZip, batchSkills, skillStateLabels, type Skill, type SkillList, type SkillScope, type SkillBatchAction, type SkillBatchResult } from "../../api/skills";
import { FolderValidationError } from "./skillFolderImport";
import { inspectSkillZip, type ZipCandidate } from "./skillZipImport";
import type { WorkspaceController } from "../workspaces/useWorkspaces";
import { useI18n } from "../../i18n/I18nProvider";

type MutationResult = "refreshed" | "refresh_failed" | "failed";
type StatusFilter = "all" | "enabled" | "disabled" | "abnormal";
const abnormal = (item: Skill) => item.state !== "ready" && item.state !== "disabled";

export function SkillsSettings({ workspaces, container, onOverlayChange }: { workspaces: Pick<WorkspaceController, "catalog">; container: HTMLElement | null; onOverlayChange?: (open: boolean) => void }) {
  const { t } = useI18n();
  const screens = Grid.useBreakpoint();
  const [scope, setScope] = useState<SkillScope>("global");
  const [workspaceId, setWorkspaceId] = useState(workspaces.catalog?.activeWorkspaceId ?? "");
  const [data, setData] = useState<SkillList | null>(null);
  const [globals, setGlobals] = useState<Skill[]>([]);
  const [page, setPage] = useState(1);
  const [globalPage, setGlobalPage] = useState(1);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [refreshFailed, setRefreshFailed] = useState(false);
  const filterItems = useCallback((items: Skill[]) => {
    const needle = query.trim().normalize("NFC").toLowerCase();
    return items.filter(item => item.name.normalize("NFC").toLowerCase().includes(needle)
      && (statusFilter === "all" || (statusFilter === "enabled" ? item.enabled : statusFilter === "disabled" ? !item.enabled : abnormal(item))));
  }, [query, statusFilter]);
  const filtered = useMemo(() => filterItems(data?.skills ?? []), [data, filterItems]);
  const inheritedFiltered = useMemo(() => filterItems(globals), [globals, filterItems]);
  const currentPage = Math.min(page, Math.max(1, Math.ceil(filtered.length / 20)));
  const currentGlobalPage = Math.min(globalPage, Math.max(1, Math.ceil(inheritedFiltered.length / 20)));
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editor, setEditor] = useState(false);
  const [batch, setBatch] = useState<{ action: SkillBatchAction; revision: number; count: number; scope: SkillScope; workspaceId: string | null; label: string } | null>(null);
  const [confirmation, setConfirmation] = useState("");
  const [batchError, setBatchError] = useState<string | null>(null);
  const [batchResult, setBatchResult] = useState<SkillBatchResult | null>(null);
  const batchInFlight = useRef(false);
  const batchOpener = useRef<HTMLButtonElement | null>(null);
  const [content, setContent] = useState("");
  const [importedName, setImportedName] = useState("");
  const [folder, setFolder] = useState<ZipCandidate | null>(null);
  const [editorCommitted, setEditorCommitted] = useState(false);
  const folderReading = useRef(false);
  const [editRevision, setEditRevision] = useState(0);
  const generation = useRef(0);
  const opener = useRef<HTMLElement | null>(null);
  useEffect(() => { onOverlayChange?.(editor || batch !== null); return () => onOverlayChange?.(false); }, [editor, batch, onOverlayChange]);
  useEffect(() => { setBatchResult(null); setPage(1); setGlobalPage(1); }, [scope, workspaceId]);
  useEffect(() => {
    if (!editor && !batch) return;
    const dismissEditor = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopImmediatePropagation();
      if (!busy) { if (batch) { setBatch(null); batchOpener.current?.focus(); } else { setEditor(false); opener.current?.focus(); } }
    };
    document.addEventListener("keydown", dismissEditor, true);
    return () => document.removeEventListener("keydown", dismissEditor, true);
  }, [editor, batch, busy]);
  const reload = useCallback(async (): Promise<boolean> => {
    const current = ++generation.current;
    setLoading(true);
    try {
      const value = await listSkills(scope, scope === "workspace" ? workspaceId : undefined);
      const inherited = scope === "workspace" ? await listSkills("global", workspaceId) : null;
      if (current !== generation.current) return false;
      setData(value); setGlobals(inherited?.skills ?? []); setError(null); setRefreshFailed(false);
      return true;
    } catch (reason) {
      if (current === generation.current) { setRefreshFailed(true); setError(reason instanceof Error ? reason.message : "network_error"); }
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
  const openBatch = (action: SkillBatchAction) => {
    if (busy || loading || refreshFailed || !data?.skills.length) return;
    const workspace = workspaces.catalog?.workspaces.find(item => item.id === workspaceId);
    setConfirmation(""); setBatchError(null); setBatchResult(null);
    setBatch({ action, revision: data.revision, count: data.skills.length, scope, workspaceId: scope === "workspace" ? workspaceId : null,
      label: scope === "global" ? t("skills.global") : workspace?.kind === "default" ? t("workspaces.default") : workspace?.name ?? workspaceId });
  };
  const submitBatch = async () => {
    if (!batch || batchInFlight.current || (batch.action === "archive" && confirmation !== t("skills.batchWord"))) return;
    batchInFlight.current = true; setBusy(true); setBatchError(null);
    try {
      const result = await batchSkills(batch.scope, batch.workspaceId, batch.action, batch.revision);
      setBatchResult(result); setBatch(null);
      await reload();
      batchOpener.current?.focus();
    } catch (reason) { setBatchError(reason instanceof Error ? reason.message : "network_error"); }
    finally { batchInFlight.current = false; setBusy(false); }
  };
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
    <div className="skills-heading"><h2>{t("settings.category.skills")}</h2><label className="skills-master">{t("skills.master")} <Switch aria-label={t("skills.master")} checked={data?.enabled ?? false} disabled={!data || busy || loading || refreshFailed} onChange={enabled => void mutate("/settings", "PUT", { enabled, expectedRevision: data?.revision })} /></label></div><p className="skills-intro">{t("skills.shortIntro")}</p>
    {data && !data.enabled ? <p role="status" className="skills-row-hint">{t("skills.paused")}</p> : null}
    <Tabs activeKey={scope} onChange={key => { if (!busy) { generation.current++; setData(null); setGlobals([]); setError(null); setScope(key as SkillScope); } }} items={[{ key: "global", label: t("skills.global"), disabled: busy }, { key: "workspace", label: t("skills.workspace"), disabled: busy }]} />
    {scope === "workspace" ? <Select getPopupContainer={() => container ?? document.body} aria-label={t("skills.workspace")} value={workspaceId} style={{ width: "100%" }} disabled={busy} onChange={value => { generation.current++; setData(null); setGlobals([]); setError(null); setWorkspaceId(value); }} options={workspaces.catalog?.workspaces.map(item => ({ value: item.id, label: item.kind === "default" ? t("workspaces.default") : item.name }))} /> : null}
    {error ? <Alert type="error" title={t("skills.error", { code: error })} action={<Button loading={loading} disabled={busy} onClick={() => void reload()}>{t("common.retry")}</Button>} /> : null}
    <details className="skills-help"><summary>{t("skills.help")}</summary><p>{t("skills.intro")}</p><p>{t("skills.capabilityHint")}</p></details>
    {batchResult ? <Alert role="status" type={batchResult.failed.length || batchResult.skipped.length ? "warning" : "success"} title={t("skills.batchResult", { completed: batchResult.completed, skipped: batchResult.skipped.length, failed: batchResult.failed.length })} description={batchResult.skipped.length || batchResult.failed.length ? <ul>{[...batchResult.skipped, ...batchResult.failed].map(issue => <li key={issue.id}>{data?.skills.find(item => item.id === issue.id)?.name ?? issue.id}: {issue.reason === "unchanged" ? t("skills.batchUnchanged") : t(skillStateLabels[issue.reason as keyof typeof skillStateLabels] ?? "skills.unavailable")}</li>)}</ul> : undefined} /> : null}
    <div className="skills-toolbar">
      <h3>{t(scope === "global" ? "skills.global" : "skills.workspace")} Skills <span>· {data?.skills.length ?? "—"}</span></h3>
      <div className="skills-toolbar-actions">
      <Tooltip getPopupContainer={() => container ?? document.body} title={t("skills.scan")}><Button aria-label={t("skills.scan")} icon={<ReloadOutlined />} disabled={busy || loading || refreshFailed || !data || unavailable} onClick={() => void mutate("/scan", "POST", { scope, workspaceId: scope === "workspace" ? workspaceId : null, expectedRevision: data?.revision })} /></Tooltip>
      <Dropdown getPopupContainer={() => container ?? document.body} trigger={["click"]} popupRender={() => <div className="skills-import-menu">
      <Button type="text" onClick={event => void open(event.currentTarget)}>{t("skills.import")}</Button>
      <Upload accept=".zip,application/zip" multiple={false} showUploadList={false} disabled={busy || loading || refreshFailed || !data || unavailable} beforeUpload={async file => {
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
        <Button icon={<UploadOutlined aria-hidden="true" />} disabled={busy || loading || refreshFailed || !data || unavailable} onClick={event => { opener.current = event.currentTarget; }}>{t("skills.importFolder")}</Button>
      </Upload>
      </div>}><Button icon={<UploadOutlined />} disabled={busy || loading || refreshFailed || !data || unavailable}>{t("skills.importMenu")} ▾</Button></Dropdown>
      <Button type="primary" icon={<PlusOutlined />} disabled={busy || loading || refreshFailed || !data || unavailable} onClick={event => void open(event.currentTarget)}>{t("skills.create")}</Button>
      <Dropdown getPopupContainer={() => container ?? document.body} trigger={["click"]} menu={{ items: [
        { key: "enable", label: t("skills.batchEnable") }, { key: "disable", label: t("skills.batchDisable") }, { type: "divider" }, { key: "archive", label: t("skills.batchArchive"), danger: true },
      ], onClick: ({ key }) => { if (key === "enable" || key === "disable" || key === "archive") openBatch(key); } }}>
        <Button ref={batchOpener} aria-label={t("skills.batchMenu")} title={t("skills.batchMenu")} icon={<MoreOutlined />} disabled={busy || loading || refreshFailed || !data?.skills.length} />
      </Dropdown>
      </div>
    </div>
    <div className="skills-filters">
      <Input aria-label={t("skills.search")} placeholder={t("skills.search")} allowClear value={query} onChange={event => { setQuery(event.target.value); setPage(1); setGlobalPage(1); }} />
      <Select aria-label={t("skills.filter")} value={statusFilter} getPopupContainer={() => container ?? document.body} onChange={(value: StatusFilter) => { setStatusFilter(value); setPage(1); setGlobalPage(1); }} options={[
        { value: "all", label: t("skills.filterAll") }, { value: "enabled", label: t("skills.filterEnabled") }, { value: "disabled", label: t("skills.disabled") }, { value: "abnormal", label: t("skills.filterAbnormal") },
      ]} />
    </div>
    {data ? <p className="skills-result-count" role="status">{t("skills.results", { count: filtered.length, total: data.skills.length })}</p> : null}
    {!loading && data && filtered.length === 0 ? <p className="skills-empty">{t(data.skills.length ? "skills.noMatches" : scope === "workspace" ? "skills.workspaceEmpty" : "skills.empty")}</p> : null}
    {filtered.slice((currentPage - 1) * 20, currentPage * 20).map(item => <article key={item.id} className="skills-row">
      <div className="skills-row-info"><h3 title={item.name}>{item.name}</h3>
        {item.state !== "ready" && item.state !== "disabled" ? <Tag role="status">{t(skillStateLabels[item.reason as keyof typeof skillStateLabels] ?? "skills.unavailable")}</Tag> : null}
        {scope === "workspace" && !item.effective ? <p className="skills-row-hint">{t("skills.noFallback")}</p> : null}
      </div>
      <div className="skills-row-actions"><Switch aria-label={t("skills.toggle", { name: item.name })} checked={item.enabled} disabled={busy || loading || refreshFailed} onChange={enabled => void mutate(`/${item.id}/enabled`, "PUT", { enabled, expectedRevision: data!.revision })} />
        <Popconfirm title={t("skills.archive")} description={scope === "workspace" ? t("skills.removeInheritance") : undefined} getPopupContainer={() => container ?? document.body} onConfirm={() => mutate(`/${item.id}?expectedRevision=${data!.revision}`, "DELETE")}><Button className="skills-remove" type="text" title={`${t("common.remove")} Skill`} aria-label={`${t("common.remove")} ${item.name}`} icon={<DeleteOutlined aria-hidden="true" />} disabled={busy || loading || refreshFailed} /></Popconfirm>
      </div></article>)}
    <Pagination size="small" current={currentPage} pageSize={20} total={filtered.length} onChange={setPage} hideOnSinglePage showSizeChanger={false} disabled={busy || loading} />
    {scope === "workspace" ? <><div className="skills-inherited-heading"><h3>{t("skills.inherited")} · {globals.length}</h3><Button type="link" disabled={busy} onClick={() => { generation.current++; setData(null); setGlobals([]); setError(null); setScope("global"); }}>{t("skills.manageGlobal")}</Button></div><p className="skills-row-hint">{t("skills.inheritanceHint")}</p>{data ? <p className="skills-result-count">{t("skills.results", { count: inheritedFiltered.length, total: globals.length })}</p> : null}{!loading && data && !inheritedFiltered.length ? <p className="skills-empty">{t(globals.length ? "skills.noMatches" : "skills.empty")}</p> : null}</> : null}
    {inheritedFiltered.slice((currentGlobalPage - 1) * 20, currentGlobalPage * 20).map(item => <article key={item.id} className="skills-row"><div className="skills-row-info"><h3 title={item.name}>{item.name}</h3>{!item.effective ? <Tag role="status">{t(skillStateLabels[item.reason as keyof typeof skillStateLabels] ?? "skills.unavailable")}</Tag> : null}</div></article>)}
    <Pagination size="small" current={currentGlobalPage} pageSize={20} total={inheritedFiltered.length} onChange={setGlobalPage} hideOnSinglePage showSizeChanger={false} disabled={busy || loading} />
    {screens.md ? <Modal open={editor} title={t(folder ? "skills.importFolder" : "skills.content")} onCancel={close} afterClose={() => opener.current?.focus()} footer={null} getContainer={container ?? undefined} destroyOnHidden>{folder ? folderForm : form}</Modal> : <Drawer open={editor} title={t(folder ? "skills.importFolder" : "skills.content")} onClose={close} afterOpenChange={open => { if (!open) opener.current?.focus(); }} size="100%" getContainer={container ?? undefined} destroyOnHidden>{folder ? folderForm : form}</Drawer>}
    <Modal open={batch !== null} title={t(batch?.action === "archive" ? "skills.batchArchive" : batch?.action === "enable" ? "skills.batchEnable" : "skills.batchDisable")} getContainer={container ?? undefined} onCancel={() => { if (!busy) setBatch(null); }} afterClose={() => batchOpener.current?.focus()} closable={!busy} mask={{ closable: !busy }} keyboard={!busy} confirmLoading={busy} okText={t("skills.batchConfirm")} cancelText={t("common.cancel")} okButtonProps={{ danger: batch?.action === "archive", disabled: busy || (batch?.action === "archive" && confirmation !== t("skills.batchWord")) }} cancelButtonProps={{ disabled: busy }} onOk={() => void submitBatch()} destroyOnHidden>
      <p>{t("skills.batchScope", { scope: batch?.label ?? "", count: batch?.count ?? 0 })}</p>
      <p>{t("skills.batchUnfiltered")}</p>
      <p>{t(batch?.action === "archive" ? "skills.batchArchiveHint" : batch?.action === "enable" ? "skills.batchEnableHint" : "skills.batchDisableHint")}</p>
      {batch?.scope === "workspace" ? <p>{t(batch.action === "archive" ? "skills.removeInheritance" : "skills.batchWorkspaceHint")}</p> : null}
      {batch?.action === "archive" ? <label>{t("skills.batchType", { word: t("skills.batchWord") })}<Input aria-label={t("skills.batchType", { word: t("skills.batchWord") })} value={confirmation} onChange={event => setConfirmation(event.target.value)} disabled={busy} autoComplete="off" /></label> : null}
      {batchError ? <Alert type="error" title={t("skills.error", { code: batchError })} description={t("skills.batchErrorHint")} /> : null}
    </Modal>
  </section>;
}
