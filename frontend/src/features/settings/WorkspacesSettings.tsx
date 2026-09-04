import { EditOutlined, FolderAddOutlined, FolderOpenOutlined, PlusOutlined } from "@ant-design/icons";
import { Button, Drawer, Input, Modal, Popconfirm, Select, Switch, Tag } from "antd";
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";

import {
  DEFAULT_WORKSPACE_ID,
  workspaceErrorText,
  type Workspace,
  type WorkspaceMount,
  type WorkspaceMountAccess,
} from "../../api/workspaces";
import { useI18n } from "../../i18n/I18nProvider";
import { useLocalPathPicker } from "../local-paths/useLocalPathPicker";
import type { WorkspaceController } from "../workspaces/useWorkspaces";
import { workspaceName } from "../workspaces/WorkspaceSwitcher";

type MountDraft = {
  alias: string;
  rootPath: string;
  accessMode: WorkspaceMountAccess;
  enabled: boolean;
};

const emptyMount: MountDraft = {
  alias: "",
  rootPath: "",
  accessMode: "read_only",
  enabled: true,
};

export function WorkspacesSettings({
  controller,
  container,
  onActivated,
  createRequest = 0,
  onCreateRequestHandled,
  onOverlayChange,
}: {
  controller: WorkspaceController;
  container: HTMLElement | null;
  onActivated: (workspaceId: string) => void;
  createRequest?: number;
  onCreateRequestHandled?: () => void;
  onOverlayChange?: (open: boolean) => void;
}) {
  const { t } = useI18n();
  const picker = useLocalPathPicker();
  const [mobile, setMobile] = useState(() => window.innerWidth <= 767);
  const [workspaceEditorOpen, setWorkspaceEditorOpen] = useState(false);
  const [editingWorkspace, setEditingWorkspace] = useState<Workspace | null>(null);
  const [workspaceNameDraft, setWorkspaceNameDraft] = useState("");
  const [importOpen, setImportOpen] = useState(false);
  const [mountEditorOpen, setMountEditorOpen] = useState(false);
  const [mountWorkspace, setMountWorkspace] = useState<Workspace | null>(null);
  const [editingMount, setEditingMount] = useState<WorkspaceMount | null>(null);
  const [mountDraft, setMountDraft] = useState<MountDraft>(emptyMount);
  const [formError, setFormError] = useState<string | null>(null);
  const opener = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const resize = () => setMobile(window.innerWidth <= 767);
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);

  const anyOverlay = workspaceEditorOpen || importOpen || mountEditorOpen;
  useEffect(() => { onOverlayChange?.(anyOverlay); }, [anyOverlay, onOverlayChange]);
  useEffect(() => () => onOverlayChange?.(false), [onOverlayChange]);

  const rememberOpener = (source: HTMLElement) => { opener.current = source; };
  const restoreFocus = () => window.requestAnimationFrame(() => opener.current?.focus());
  const closeWorkspaceEditor = () => { setWorkspaceEditorOpen(false); restoreFocus(); };
  const closeImport = () => { setImportOpen(false); restoreFocus(); };
  const closeMountEditor = () => { setMountEditorOpen(false); restoreFocus(); };

  const openWorkspaceEditor = (item: Workspace | null, source: HTMLElement) => {
    rememberOpener(source);
    setEditingWorkspace(item);
    setWorkspaceNameDraft(item?.name ?? "");
    setFormError(null);
    setWorkspaceEditorOpen(true);
  };
  const openImport = (source: HTMLElement) => {
    rememberOpener(source);
    setFormError(null);
    setImportOpen(true);
    void controller.loadImportCandidates(true);
  };
  const openMountEditor = (workspace: Workspace, mount: WorkspaceMount | null, source: HTMLElement) => {
    rememberOpener(source);
    setMountWorkspace(workspace);
    setEditingMount(mount);
    setMountDraft(mount ? {
      alias: mount.alias,
      rootPath: mount.rootPath,
      accessMode: mount.accessMode,
      enabled: mount.enabled,
    } : emptyMount);
    setFormError(null);
    setMountEditorOpen(true);
  };

  useEffect(() => {
    if (createRequest < 1) return;
    const active = document.activeElement;
    openWorkspaceEditor(null, active instanceof HTMLElement ? active : document.body);
    onCreateRequestHandled?.();
  }, [createRequest, onCreateRequestHandled]);

  const saveWorkspace = async (event: FormEvent) => {
    event.preventDefault();
    if (!workspaceNameDraft.trim()) {
      setFormError(t("workspaces.error.invalid"));
      return;
    }
    try {
      if (editingWorkspace) {
        await controller.update(editingWorkspace, workspaceNameDraft);
      } else {
        const result = await controller.create(workspaceNameDraft);
        onActivated(result.activeWorkspaceId);
      }
      closeWorkspaceEditor();
    } catch (error) {
      setFormError(workspaceErrorText(error, t));
    }
  };

  const saveMount = async (event: FormEvent) => {
    event.preventDefault();
    if (!mountWorkspace || !mountDraft.alias.trim() || !mountDraft.rootPath.trim()) {
      setFormError(t("workspaces.error.invalid"));
      return;
    }
    try {
      if (editingMount) {
        await controller.updateMount(
          mountWorkspace,
          editingMount.id,
          mountDraft.alias,
          mountDraft.rootPath,
          mountDraft.accessMode,
          mountDraft.enabled,
        );
      } else {
        await controller.addMount(
          mountWorkspace,
          mountDraft.alias,
          mountDraft.rootPath,
          mountDraft.accessMode,
        );
      }
      closeMountEditor();
    } catch (error) {
      setFormError(workspaceErrorText(error, t));
    }
  };

  const displayName = (item: Workspace) => workspaceName(item.kind, item.name, t("workspaces.default"));
  const availability = (value: { availability: string; unavailableReason: string | null }) => value.availability === "available"
    ? t("workspaces.available")
    : value.availability === "not_applicable"
      ? t("workspaces.mountDisabled")
      : t(`workspaces.unavailableReason.${value.unavailableReason}` as never);
  const overlay = (open: boolean, title: string, onClose: () => void, body: ReactNode) => mobile
    ? <Drawer getContainer={container ?? false} rootStyle={container ? { position: "absolute" } : undefined} open={open} placement="right" size="100vw" title={title} onClose={onClose} destroyOnHidden>{body}</Drawer>
    : <Modal getContainer={container ?? false} open={open} title={title} footer={null} onCancel={onClose} destroyOnHidden>{body}</Modal>;

  const workspaceEditor = <form className="workspace-editor" onSubmit={saveWorkspace}>
    <label>{t("workspaces.field.name")}<Input value={workspaceNameDraft} maxLength={80} autoComplete="off" onChange={(event) => setWorkspaceNameDraft(event.target.value)} /></label>
    {!editingWorkspace ? <p className="settings-control-description">{t("workspaces.managedRootCreateHint")}</p> : <p className="settings-control-description">{t("workspaces.renameKeepsDirectory")}</p>}
    {formError ? <p className="workspace-editor__error" role="alert">{formError}</p> : null}
    <div className="workspace-editor__actions"><Button onClick={closeWorkspaceEditor}>{t("common.cancel")}</Button><Button type="primary" htmlType="submit" loading={controller.saving}>{t("common.save")}</Button></div>
  </form>;

  const mountEditor = <form className="workspace-editor" onSubmit={saveMount}>
    <label>{t("workspaces.mountAlias")}<Input value={mountDraft.alias} maxLength={40} onChange={(event) => setMountDraft((current) => ({ ...current, alias: event.target.value }))} /></label>
    <label>{t("workspaces.mountPath")}<div className="workspace-editor__path"><Input value={mountDraft.rootPath} maxLength={32768} onChange={(event) => setMountDraft((current) => ({ ...current, rootPath: event.target.value }))} /><Button icon={<FolderOpenOutlined aria-hidden="true" />} loading={picker.picking === "directory"} onClick={async () => { const selected = await picker.pick("directory"); if (selected) setMountDraft((current) => ({ ...current, rootPath: selected, alias: current.alias || selected.split(/[\\/]/).filter(Boolean).at(-1) || "" })); }}>{t("localPath.browseDirectory")}</Button></div></label>
    <label>{t("workspaces.mountAccess")}<Select value={mountDraft.accessMode} options={[{ value: "read_only", label: t("workspaces.readOnly") }, { value: "read_write", label: t("workspaces.readWrite") }]} onChange={(accessMode) => setMountDraft((current) => ({ ...current, accessMode }))} /></label>
    {editingMount ? <label className="workspace-editor__switch">{t("workspaces.mountEnabled")}<Switch checked={mountDraft.enabled} onChange={(enabled) => setMountDraft((current) => ({ ...current, enabled }))} /></label> : null}
    <p className="settings-control-description">{t("workspaces.mountNoToolsHint")}</p>
    {picker.error ? <p className="workspace-editor__error" role="alert">{picker.error}</p> : null}
    {formError ? <p className="workspace-editor__error" role="alert">{formError}</p> : null}
    <div className="workspace-editor__actions"><Button onClick={closeMountEditor}>{t("common.cancel")}</Button><Button type="primary" htmlType="submit" loading={controller.saving}>{t("common.save")}</Button></div>
  </form>;

  const importBody = <div className="workspace-import-list">
    <p className="settings-control-description">{t("workspaces.importDescription")}</p>
    {controller.importCandidatesLoading && controller.importCandidates.length === 0 ? <p role="status">{t("workspaces.loading")}</p> : null}
    {!controller.importCandidatesLoading && controller.importCandidates.length === 0 ? <p>{t("workspaces.importEmpty")}</p> : null}
    {controller.importCandidates.map((candidate) => <div className="workspace-import-item" key={candidate.directoryName}><div><strong>{candidate.directoryName}</strong><span>{candidate.rootPath}</span></div><Button loading={controller.saving} onClick={async () => { try { const result = await controller.importExisting(candidate.directoryName); onActivated(result.activeWorkspaceId); closeImport(); } catch (error) { setFormError(workspaceErrorText(error, t)); } }}>{t("workspaces.importAction")}</Button></div>)}
    {controller.importCandidatesNextCursor ? <Button loading={controller.importCandidatesLoading} onClick={() => void controller.loadImportCandidates(false)}>{t("app.loadMoreConversations")}</Button> : null}
    {formError ? <p className="workspace-editor__error" role="alert">{formError}</p> : null}
  </div>;

  return <section className="workspace-settings" aria-label={t("settings.category.workspaces")}>
    <div className="workspace-settings__toolbar"><Button type="primary" icon={<PlusOutlined aria-hidden="true" />} onClick={(event) => openWorkspaceEditor(null, event.currentTarget)} disabled={!controller.catalog || controller.saving}>{t("workspaces.create")}</Button><Button icon={<FolderAddOutlined aria-hidden="true" />} onClick={(event) => openImport(event.currentTarget)} disabled={!controller.catalog || controller.saving}>{t("workspaces.importExisting")}</Button></div>
    <p className="settings-control-description">{t("workspaces.noFileToolsNotice")}</p>
    {controller.loading ? <p role="status">{t("workspaces.loading")}</p> : null}
    {controller.error ? <div className="settings-model-load-error" role="alert"><p>{workspaceErrorText(controller.error, t)}</p><Button onClick={() => void controller.reload()}>{t("common.retry")}</Button></div> : null}
    <div className="workspace-settings__list">{controller.catalog?.workspaces.map((item) => {
      const empty = item.usage.conversationCount === 0 && item.usage.scheduleCount === 0 && item.usage.activeRunCount === 0;
      return <article className="workspace-settings__item" key={item.id}>
        <div className="workspace-settings__summary"><div><h3>{displayName(item)}</h3><p title={item.rootPath}>{item.rootPath}</p><small>{t("workspaces.directoryName", { name: item.directoryName })}</small></div><Tag color={item.availability === "available" ? "green" : "red"}>{availability(item)}</Tag></div>
        <dl><div><dt>{t("workspaces.conversations")}</dt><dd>{item.usage.conversationCount}</dd></div><div><dt>{t("workspaces.schedules")}</dt><dd>{item.usage.scheduleCount}</dd></div><div><dt>{t("workspaces.activeRuns")}</dt><dd>{item.usage.activeRunCount}</dd></div></dl>
        <section className="workspace-mounts" aria-label={`${t("workspaces.mounts")} ${displayName(item)}`}><div className="workspace-mounts__header"><h4>{t("workspaces.mounts")}</h4><Button aria-label={`${t("workspaces.addMount")} ${displayName(item)}`} icon={<PlusOutlined aria-hidden="true" />} disabled={controller.saving || item.usage.activeRunCount > 0 || item.mounts.length >= 20} onClick={(event) => openMountEditor(item, null, event.currentTarget)}>{t("workspaces.addMount")}</Button></div>{item.mounts.length === 0 ? <p>{t("workspaces.noMounts")}</p> : item.mounts.map((mount) => <article className="workspace-mount" key={mount.id}><div><strong>{mount.alias}</strong><span title={mount.rootPath}>{mount.rootPath}</span><small>{t(mount.accessMode === "read_only" ? "workspaces.readOnly" : "workspaces.readWrite")} · {availability(mount)}</small></div><div><Button aria-label={`${t("common.edit")} ${mount.alias}`} icon={<EditOutlined aria-hidden="true" />} disabled={controller.saving || item.usage.activeRunCount > 0} onClick={(event) => openMountEditor(item, mount, event.currentTarget)}>{t("common.edit")}</Button><Popconfirm getPopupContainer={() => container ?? document.body} title={t("workspaces.removeMountConfirm")} okText={t("common.remove")} cancelText={t("common.cancel")} onConfirm={() => controller.removeMount(item, mount.id).catch(() => undefined)}><Button aria-label={`${t("common.remove")} ${mount.alias}`} danger disabled={controller.saving || item.usage.activeRunCount > 0}>{t("common.remove")}</Button></Popconfirm></div></article>)}</section>
        <div className="workspace-settings__actions">{item.kind === "managed" ? <><Button aria-label={`${t("common.edit")} ${displayName(item)}`} icon={<EditOutlined aria-hidden="true" />} onClick={(event) => openWorkspaceEditor(item, event.currentTarget)}>{t("common.edit")}</Button><Popconfirm getPopupContainer={() => container ?? document.body} title={t("workspaces.deleteConfirm")} description={empty ? t("workspaces.deletePreservesDirectory") : t("workspaces.deleteBlocked")} okText={t("common.remove")} cancelText={t("common.cancel")} disabled={!empty} onConfirm={async () => { await controller.remove(item); if (item.id === controller.catalog?.activeWorkspaceId) onActivated(DEFAULT_WORKSPACE_ID); }}><Button aria-label={`${t("common.remove")} ${displayName(item)}`} danger disabled={!empty || controller.saving}>{t("common.remove")}</Button></Popconfirm></> : <Tag>{t("workspaces.defaultFixed")}</Tag>}</div>
      </article>;
    })}</div>
    {overlay(workspaceEditorOpen, editingWorkspace ? t("workspaces.editTitle") : t("workspaces.createTitle"), closeWorkspaceEditor, workspaceEditor)}
    {overlay(importOpen, t("workspaces.importTitle"), closeImport, importBody)}
    {overlay(mountEditorOpen, editingMount ? t("workspaces.editMountTitle") : t("workspaces.addMountTitle"), closeMountEditor, mountEditor)}
  </section>;
}
