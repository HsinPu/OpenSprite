import { Alert, Button, Drawer, Empty, Grid, Input, Modal, Popconfirm, Select, Switch, Tabs, Tag } from "antd";
import { useCallback, useEffect, useRef, useState } from "react";
import { getSkill, listSkills, skillRequest, skillStateLabels, type Skill, type SkillList, type SkillScope } from "../../api/skills";
import type { WorkspaceController } from "../workspaces/useWorkspaces";
import { useI18n } from "../../i18n/I18nProvider";

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
  const [editing, setEditing] = useState<Skill | null>(null);
  const [content, setContent] = useState("");
  const [editRevision, setEditRevision] = useState(0);
  const generation = useRef(0);
  const opener = useRef<HTMLElement | null>(null);
  useEffect(() => { onOverlayChange?.(editor); return () => onOverlayChange?.(false); }, [editor, onOverlayChange]);
  const reload = useCallback(async () => {
    const current = ++generation.current;
    setLoading(true);
    try {
      const value = await listSkills(scope, scope === "workspace" ? workspaceId : undefined);
      const inherited = scope === "workspace" ? await listSkills("global", workspaceId) : null;
      if (current !== generation.current) return;
      setData(value); setGlobals(inherited?.skills ?? []); setError(null);
    } catch (reason) { if (current === generation.current) setError(reason instanceof Error ? reason.message : "network_error"); }
    finally { if (current === generation.current) setLoading(false); }
  }, [scope, workspaceId]);
  useEffect(() => { void reload(); return () => { generation.current++; }; }, [reload]);
  const mutate = async (path: string, method: string, payload?: unknown) => {
    if (busy) return;
    setBusy(true);
    try { await skillRequest(path, method, payload); await reload(); return true; }
    catch (reason) { setError(reason instanceof Error ? reason.message : "network_error"); return false; }
    finally { setBusy(false); }
  };
  const open = async (item: Skill | null, target: HTMLElement) => {
    opener.current = target;
    setError(null);
    if (item) {
      setBusy(true);
      try { const value = await getSkill(item.id); setEditing(value.skill); setContent(value.skill.content ?? ""); setEditRevision(value.revision); setEditor(true); }
      catch (reason) { setError(reason instanceof Error ? reason.message : "network_error"); }
      finally { setBusy(false); }
    } else { setEditing(null); setContent("---\nname: \ndescription: \n---\n"); setEditRevision(data?.revision ?? 0); setEditor(true); }
  };
  const close = () => { if (!busy) { setEditor(false); opener.current?.focus(); } };
  const unavailable = scope === "workspace" && workspaces.catalog?.workspaces.find(item => item.id === workspaceId)?.availability !== "available";
  const form = <div style={{ display: "grid", gap: 12 }}>
    <p>{t("skills.saveHint")}</p>
    <label>{t("skills.import")}<input type="file" accept=".md,text/markdown" disabled={busy} onChange={event => {
      const file = event.target.files?.[0];
      if (!file) return;
      if (file.size > 65536) { setError("content_too_large"); return; }
      void file.arrayBuffer().then(buffer => { setContent(new TextDecoder("utf-8", { fatal: true }).decode(buffer)); }).catch(() => setError("invalid_format"));
    }} /></label>
    <label>{t("skills.content")}<Input.TextArea value={content} onChange={event => setContent(event.target.value)} rows={14} disabled={busy} /></label>
    {error ? <Alert type="error" title={t("skills.error", { code: error })} /> : null}
    <Button type="primary" loading={busy} disabled={unavailable} onClick={async () => {
      const payload = editing ? { content, expectedRevision: editRevision } : { scope, workspaceId: scope === "workspace" ? workspaceId : null, content, expectedRevision: editRevision };
      if (await mutate(editing ? `/${editing.id}` : "", editing ? "PUT" : "POST", payload)) { setEditor(false); opener.current?.focus(); }
    }}>{t("common.save")}</Button>
    {editing && editing.contentHash && content === editing.content ? <Button disabled={busy || unavailable} onClick={async () => {
      if (await mutate(`/${editing.id}/enabled`, "PUT", { enabled: true, confirmedHash: editing.contentHash, expectedRevision: editRevision })) { setEditor(false); opener.current?.focus(); }
    }}>{t("skills.approve")}</Button> : null}
  </div>;
  return <section aria-label={t("settings.category.skills")}>
    <h2>{t("settings.category.skills")}</h2><p>{t("skills.intro")}</p>
    <Tabs activeKey={scope} onChange={key => { if (!busy) { setData(null); setScope(key as SkillScope); } }} items={[{ key: "global", label: t("skills.global"), disabled: busy }, { key: "workspace", label: t("skills.workspace"), disabled: busy }]} />
    {scope === "workspace" ? <Select aria-label={t("skills.workspace")} value={workspaceId} style={{ width: "100%" }} disabled={busy} onChange={setWorkspaceId} options={workspaces.catalog?.workspaces.map(item => ({ value: item.id, label: item.kind === "default" ? t("workspaces.default") : item.name }))} /> : <label>{t("skills.master")} <Switch checked={data?.enabled ?? false} disabled={!data || busy || loading} onChange={enabled => void mutate("/settings", "PUT", { enabled, expectedRevision: data?.revision })} /></label>}
    {error ? <Alert type="error" title={t("skills.error", { code: error })} /> : null}
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBlock: 16 }}>
      <Button disabled={busy || loading || !data || unavailable} onClick={event => void open(null, event.currentTarget)}>{t("skills.create")}</Button>
      <Button loading={loading} disabled={busy} onClick={() => void reload()}>{t("common.retry")}</Button>
      <Button disabled={busy || loading || !data || unavailable} onClick={() => void mutate("/scan", "POST", { scope, workspaceId: scope === "workspace" ? workspaceId : null, expectedRevision: data?.revision })}>{t("skills.scan")}</Button>
    </div>
    {!loading && data?.skills.length === 0 ? <Empty description={t("skills.empty")} /> : null}
    {data?.skills.map(item => <article key={item.id} style={{ paddingBlock: 12, borderBottom: "1px solid #ddd" }}>
      <h3>{item.name} <Tag>{t(skillStateLabels[item.reason as keyof typeof skillStateLabels] ?? "skills.unavailable")}</Tag></h3><p>{item.description}</p>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}><Button disabled={busy} onClick={event => void open(item, event.currentTarget)}>{t("common.edit")}</Button>
        {item.enabled ? <Button disabled={busy} onClick={() => void mutate(`/${item.id}/enabled`, "PUT", { enabled: false, expectedRevision: data.revision })}>{t("skills.disable")}</Button> : null}
        <Popconfirm title={t("skills.archive")} getPopupContainer={() => container ?? document.body} onConfirm={() => mutate(`/${item.id}?expectedRevision=${data.revision}`, "DELETE")}><Button danger disabled={busy}>{t("common.remove")}</Button></Popconfirm>
      </div></article>)}
    {globals.length ? <h3>{t("skills.global")}</h3> : null}
    {globals.map(item => <label key={item.id} style={{ display: "flex", justifyContent: "space-between", paddingBlock: 8 }}>{item.name}<Select aria-label={item.name} disabled={busy || !data} value={item.disabledWorkspaces.includes(workspaceId) ? "disabled" : "inherit"} options={[{ value: "inherit", label: t("skills.inherit") }, { value: "disabled", label: t("skills.override") }]} onChange={value => void mutate(`/${item.id}/workspace-override`, "PUT", { workspaceId, disabled: value === "disabled", expectedRevision: data?.revision })} /></label>)}
    {screens.md ? <Modal open={editor} title={t("skills.content")} onCancel={close} afterClose={() => opener.current?.focus()} footer={null} getContainer={container ?? undefined} destroyOnHidden>{form}</Modal> : <Drawer open={editor} title={t("skills.content")} onClose={close} afterOpenChange={open => { if (!open) opener.current?.focus(); }} size="100%" getContainer={container ?? undefined} destroyOnHidden>{form}</Drawer>}
  </section>;
}
