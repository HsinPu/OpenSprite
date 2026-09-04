import { EditOutlined, FolderOpenOutlined, PlusOutlined } from "@ant-design/icons";
import { Button, Drawer, Input, Modal, Popconfirm, Tag } from "antd";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { UNASSIGNED_WORKSPACE_ID, workspaceErrorText, type Workspace } from "../../api/workspaces";
import { useI18n } from "../../i18n/I18nProvider";
import { useLocalPathPicker } from "../local-paths/useLocalPathPicker";
import type { WorkspaceController } from "../workspaces/useWorkspaces";
import { workspaceName } from "../workspaces/WorkspaceSwitcher";

type Draft = { name: string; rootPath: string };

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
  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<Workspace | null>(null);
  const [draft, setDraft] = useState<Draft>({ name: "", rootPath: "" });
  const [formError, setFormError] = useState<string | null>(null);
  const [confirmRootChange, setConfirmRootChange] = useState(false);
  const opener = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const resize = () => setMobile(window.innerWidth <= 767);
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);

  useEffect(() => {
    onOverlayChange?.(editorOpen || confirmRootChange);
  }, [confirmRootChange, editorOpen, onOverlayChange]);

  useEffect(() => () => onOverlayChange?.(false), [onOverlayChange]);

  const openEditor = (item: Workspace | null, source: HTMLElement) => {
    opener.current = source;
    setEditing(item);
    setDraft({ name: item?.name ?? "", rootPath: item?.rootPath ?? "" });
    setFormError(null);
    setEditorOpen(true);
  };
  useEffect(() => {
    if (createRequest < 1) return;
    const active = document.activeElement;
    openEditor(null, active instanceof HTMLElement ? active : document.body);
    onCreateRequestHandled?.();
  }, [createRequest, onCreateRequestHandled]);
  const closeEditor = () => {
    setEditorOpen(false);
    setConfirmRootChange(false);
    window.requestAnimationFrame(() => opener.current?.focus());
  };
  const save = async () => {
    try {
      if (editing) {
        await controller.update(editing, draft.name, draft.rootPath);
      } else {
        const result = await controller.create(draft.name, draft.rootPath);
        onActivated(result.activeWorkspaceId);
      }
      closeEditor();
    } catch (error) {
      setFormError(workspaceErrorText(error, t));
    }
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!draft.name.trim() || !draft.rootPath.trim()) {
      setFormError(t("workspaces.error.invalid"));
      return;
    }
    const rootChanged = editing?.rootPath !== draft.rootPath;
    const hasDependents = Boolean(editing && (editing.usage.conversationCount || editing.usage.scheduleCount));
    if (rootChanged && hasDependents) {
      setConfirmRootChange(true);
      return;
    }
    void save();
  };
  const displayName = (item: Workspace) => workspaceName(item.kind, item.name, t("workspaces.unassigned"));
  const availability = (item: Workspace) => item.availability === "available"
    ? t("workspaces.available")
    : item.availability === "not_applicable"
      ? t("workspaces.noRoot")
      : t(`workspaces.unavailableReason.${item.unavailableReason}` as never);
  const editor = <form className="workspace-editor" onSubmit={submit}>
    <label>{t("workspaces.field.name")}<Input value={draft.name} maxLength={80} autoComplete="off" onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))} /></label>
    <label>{t("workspaces.field.root")}<div className="workspace-editor__path"><Input value={draft.rootPath} maxLength={32768} onChange={(event) => setDraft((current) => ({ ...current, rootPath: event.target.value }))} /><Button aria-label={t("localPath.browseDirectory")} icon={<FolderOpenOutlined aria-hidden="true" />} loading={picker.picking === "directory"} onClick={async () => { const selected = await picker.pick("directory"); if (selected) setDraft((current) => ({ ...current, rootPath: selected, name: current.name || selected.split(/[\\/]/).filter(Boolean).at(-1) || "" })); }}>{t("localPath.browseDirectory")}</Button></div></label>
    <p className="settings-control-description">{t("workspaces.rootHint")}</p>
    {picker.error ? <p className="workspace-editor__error" role="alert">{picker.error}</p> : null}
    {formError ? <p className="workspace-editor__error" role="alert">{formError}</p> : null}
    <div className="workspace-editor__actions"><Button aria-label={t("common.cancel")} onClick={closeEditor}>{t("common.cancel")}</Button><Button aria-label={t("common.save")} type="primary" htmlType="submit" loading={controller.saving}>{t("common.save")}</Button></div>
  </form>;

  return <section className="workspace-settings" aria-label={t("settings.category.workspaces")}>
    <div className="workspace-settings__toolbar"><Button type="primary" aria-label={t("workspaces.create")} icon={<PlusOutlined aria-hidden="true" />} onClick={(event) => openEditor(null, event.currentTarget)} disabled={!controller.catalog || controller.saving}>{t("workspaces.create")}</Button></div>
    {controller.loading ? <p role="status">{t("workspaces.loading")}</p> : null}
    {controller.error ? <div className="settings-model-load-error" role="alert"><p>{workspaceErrorText(controller.error, t)}</p><Button onClick={() => void controller.reload()}>{t("common.retry")}</Button></div> : null}
    <div className="workspace-settings__list">{controller.catalog?.workspaces.map((item) => {
      const empty = item.usage.conversationCount === 0 && item.usage.scheduleCount === 0 && item.usage.activeRunCount === 0;
      return <article className="workspace-settings__item" key={item.id}>
        <div className="workspace-settings__summary"><div><h3>{displayName(item)}</h3><p title={item.rootPath ?? undefined}>{item.rootPath ?? t("workspaces.noRoot")}</p></div><Tag color={item.availability === "available" ? "green" : item.availability === "unavailable" ? "red" : "default"}>{availability(item)}</Tag></div>
        <dl><div><dt>{t("workspaces.conversations")}</dt><dd>{item.usage.conversationCount}</dd></div><div><dt>{t("workspaces.schedules")}</dt><dd>{item.usage.scheduleCount}</dd></div><div><dt>{t("workspaces.activeRuns")}</dt><dd>{item.usage.activeRunCount}</dd></div></dl>
        {item.kind === "directory" ? <div className="workspace-settings__actions"><Button aria-label={`${t("common.edit")} ${displayName(item)}`} icon={<EditOutlined aria-hidden="true" />} onClick={(event) => openEditor(item, event.currentTarget)}>{t("common.edit")}</Button><Popconfirm getPopupContainer={() => container ?? document.body} title={t("workspaces.deleteConfirm")} description={empty ? t("workspaces.deleteDescription") : t("workspaces.deleteBlocked")} okText={t("common.remove")} cancelText={t("common.cancel")} disabled={!empty} onConfirm={async () => { await controller.remove(item); if (item.id === controller.catalog?.activeWorkspaceId) onActivated(UNASSIGNED_WORKSPACE_ID); }}><Button aria-label={`${t("common.remove")} ${displayName(item)}`} danger disabled={!empty || controller.saving}>{t("common.remove")}</Button></Popconfirm></div> : null}
      </article>;
    })}</div>
    {mobile ? <Drawer getContainer={container ?? false} rootStyle={container ? { position: "absolute" } : undefined} open={editorOpen} placement="right" size="100vw" title={editing ? t("workspaces.editTitle") : t("workspaces.createTitle")} onClose={closeEditor} destroyOnHidden>{editor}</Drawer> : <Modal getContainer={container ?? false} open={editorOpen} title={editing ? t("workspaces.editTitle") : t("workspaces.createTitle")} footer={null} onCancel={closeEditor} destroyOnHidden>{editor}</Modal>}
    <Modal getContainer={container ?? false} open={confirmRootChange} title={t("workspaces.changeRootTitle")} okText={t("workspaces.changeRootConfirm")} cancelText={t("common.cancel")} confirmLoading={controller.saving} onCancel={() => setConfirmRootChange(false)} onOk={() => { setConfirmRootChange(false); void save(); }}><p>{t("workspaces.changeRootDescription")}</p></Modal>
  </section>;
}
