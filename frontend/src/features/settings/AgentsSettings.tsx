import {
  Alert,
  Button,
  Drawer,
  Dropdown,
  Empty,
  Grid,
  Input,
  Modal,
  Pagination,
  Popconfirm,
  Select,
  Switch,
  Tag,
  Tabs,
  Tooltip,
  Upload,
} from "antd";
import {
  DeleteOutlined,
  EditOutlined,
  MoreOutlined,
  PlusOutlined,
  ReloadOutlined,
  UploadOutlined,
} from "@ant-design/icons";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  AgentApiError,
  agentReasons,
  batchAgents,
  createAgent,
  deleteAgent,
  getAgent,
  getAgentSettings,
  listAgents,
  scanAgents,
  setAgentEnabled,
  setAgentSettings,
  updateAgent,
  type AgentBatchAction,
  type AgentList,
  type AgentReason,
  type AgentScope,
  type AgentSettings,
  type CustomAgent,
} from "../../api/customAgents";
import type { MessageKey } from "../../i18n/catalog";
import { useI18n } from "../../i18n/I18nProvider";
import type { ProviderCatalogController } from "../ai-settings/useProviderCatalog";
import type { WorkspaceController } from "../workspaces/useWorkspaces";
import "./agents.css";

type AgentsSettingsProps = {
  workspaces: Pick<WorkspaceController, "catalog">;
  providerCatalog: ProviderCatalogController;
  container: HTMLElement | null;
  onOverlayChange?: (open: boolean) => void;
};

type DraftMode = "create" | "edit" | "import";
type Draft = {
  mode: DraftMode;
  item: CustomAgent | null;
  name: string;
  description: string;
  instructions: string;
  providerMode: "inherit" | "specified";
  providerId: string;
  model: string;
  rawContent: string;
  importedFile: string;
  loading: boolean;
  committed: boolean;
};

type BatchState = {
  action: AgentBatchAction;
  scope: AgentScope;
  workspaceId: string | null;
  revision: number;
  ids: string[];
  label: string;
};

const reasonKeys: Record<AgentReason, MessageKey> = {
  effective: "agents.reason.effective",
  disabled: "agents.reason.disabled",
  master_disabled: "agents.reason.masterDisabled",
  shadowed_by_workspace: "agents.reason.shadowed",
  duplicate_name: "agents.reason.duplicateName",
  missing: "agents.reason.missing",
  invalid_format: "agents.reason.invalidFormat",
  content_too_large: "agents.reason.contentTooLarge",
  unsafe_path: "agents.reason.unsafePath",
  workspace_unavailable: "agents.reason.workspaceUnavailable",
};

const REASON_VALUES = new Set<string>(agentReasons);

function normaliseName(name: string): string {
  return name.normalize("NFC").toLocaleLowerCase();
}

function errorCode(error: unknown): string {
  return error instanceof AgentApiError ? error.code : error instanceof Error ? error.message : "network_error";
}

function tomlString(value: string): string {
  return JSON.stringify(value);
}

function parseTomlValue(content: string, key: string): string {
  const match = content.match(new RegExp(`^${key}\\s*=\\s*(?:"((?:\\\\.|[^"\\\\])*)"|'''([\\s\\S]*?)'''|"""([\\s\\S]*?)""")\\s*$`, "m"));
  if (!match) return "";
  if (match[1] !== undefined) {
    try { return JSON.parse(`"${match[1]}"`) as string; } catch { return match[1]; }
  }
  return match[2] ?? match[3] ?? "";
}

function serialiseDraft(draft: Draft): string {
  const lines = [
    `name = ${tomlString(draft.name.trim())}`,
    `description = ${tomlString(draft.description)}`,
    `developer_instructions = ${tomlString(draft.instructions)}`,
  ];
  if (draft.providerMode === "specified") {
    lines.push(`provider_id = ${tomlString(draft.providerId.trim())}`);
    lines.push(`model = ${tomlString(draft.model.trim())}`);
  }
  return `${lines.join("\n")}\n`;
}

function emptyDraft(mode: DraftMode, item: CustomAgent | null = null): Draft {
  return {
    mode,
    item,
    name: item?.name ?? "",
    description: item?.description ?? "",
    instructions: "",
    providerMode: item?.providerId && item.model ? "specified" : "inherit",
    providerId: item?.providerId ?? "",
    model: item?.model ?? "",
    rawContent: "",
    importedFile: "",
    loading: false,
    committed: false,
  };
}

async function listAllAgents(scope: AgentScope, workspaceId: string | null): Promise<AgentList> {
  let cursor: string | undefined;
  let revision: number | null = null;
  const items: CustomAgent[] = [];
  for (let page = 0; page < 1000; page += 1) {
    const next = await listAgents(scope, workspaceId, cursor, 100);
    revision ??= next.revision;
    if (next.revision !== revision) throw new AgentApiError("revision_conflict");
    items.push(...next.items);
    if (!next.nextCursor) return { revision: revision ?? 0, items, nextCursor: null };
    cursor = next.nextCursor;
  }
  throw new AgentApiError("invalid_request");
}

export function AgentsSettings({ workspaces, providerCatalog, container, onOverlayChange }: AgentsSettingsProps) {
  const { t } = useI18n();
  const screens = Grid.useBreakpoint();
  const [scope, setScope] = useState<AgentScope>("global");
  const [workspaceId, setWorkspaceId] = useState(workspaces.catalog?.activeWorkspaceId ?? "");
  const [settings, setSettings] = useState<AgentSettings | null>(null);
  const [data, setData] = useState<AgentList | null>(null);
  const [inherited, setInherited] = useState<AgentList | null>(null);
  const [page, setPage] = useState(1);
  const [globalPage, setGlobalPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [batch, setBatch] = useState<BatchState | null>(null);
  const [batchError, setBatchError] = useState<string | null>(null);
  const generation = useRef(0);
  const opener = useRef<HTMLElement | null>(null);
  const batchOpener = useRef<HTMLButtonElement | null>(null);
  const batchInFlight = useRef(false);

  const workspace = workspaces.catalog?.workspaces.find((item) => item.id === workspaceId);
  const workspaceUnavailable = scope === "workspace" && (!workspace || workspace.availability !== "available");
  const currentItems = data?.items ?? [];
  const globalItems = inherited?.items ?? [];
  const currentPageNumber = Math.min(page, Math.max(1, Math.ceil(currentItems.length / 20)));
  const globalPageNumber = Math.min(globalPage, Math.max(1, Math.ceil(globalItems.length / 20)));
  const visibleItems = currentItems.slice((currentPageNumber - 1) * 20, currentPageNumber * 20);
  const visibleGlobals = globalItems.slice((globalPageNumber - 1) * 20, globalPageNumber * 20);

  const inheritedItems = useMemo(() => {
    if (scope !== "workspace") return [];
    const localByName = new Map(currentItems.map((item) => [normaliseName(item.name), item]));
    return globalItems.map((item) => {
      const local = localByName.get(normaliseName(item.name));
      return local ? { ...item, reason: "shadowed_by_workspace" as const, shadowedByAgentId: local.id } : item;
    });
  }, [currentItems, globalItems, scope]);

  useEffect(() => {
    onOverlayChange?.(draft !== null || batch !== null);
    return () => onOverlayChange?.(false);
  }, [batch, draft, onOverlayChange]);

  useEffect(() => {
    const ids = new Set(workspaces.catalog?.workspaces.map((item) => item.id) ?? []);
    if (scope === "workspace" && (!workspaceId || !ids.has(workspaceId))) {
      setWorkspaceId(workspaces.catalog?.activeWorkspaceId ?? "");
    }
  }, [scope, workspaceId, workspaces.catalog]);

  useEffect(() => {
    if (draft === null && batch === null) return;
    const dismiss = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopImmediatePropagation();
      if (!busy) {
        if (batch !== null) { setBatch(null); requestAnimationFrame(() => batchOpener.current?.focus()); }
        else { setDraft(null); requestAnimationFrame(() => opener.current?.focus()); }
      }
    };
    document.addEventListener("keydown", dismiss, true);
    return () => document.removeEventListener("keydown", dismiss, true);
  }, [batch, busy, draft]);

  const reload = useCallback(async (): Promise<boolean> => {
    const current = ++generation.current;
    setLoading(true);
    try {
      const nextSettings = await getAgentSettings();
      if (scope === "workspace" && !workspaceId) throw new AgentApiError("workspace_unavailable");
      const next = await listAllAgents(scope, scope === "workspace" ? workspaceId : null);
      const nextInherited = scope === "workspace" ? await listAllAgents("global", null) : null;
      if (current !== generation.current) return false;
      setSettings(nextSettings);
      setData(next);
      setInherited(nextInherited);
      setError(null);
      return true;
    } catch (reason) {
      if (current === generation.current) setError(errorCode(reason));
      return false;
    } finally {
      if (current === generation.current) setLoading(false);
    }
  }, [scope, workspaceId]);

  useEffect(() => {
    setPage(1); setGlobalPage(1); setData(null); setInherited(null); setError(null);
    void reload();
    return () => { generation.current += 1; };
  }, [reload]);

  const mutate = async (operation: () => Promise<unknown>): Promise<"refreshed" | "refresh_failed" | "failed"> => {
    if (busy) return "failed";
    setBusy(true); setError(null);
    try {
      await operation();
      return await reload() ? "refreshed" : "refresh_failed";
    } catch (reason) {
      setError(errorCode(reason));
      return "failed";
    } finally { setBusy(false); }
  };

  const openCreate = (target: HTMLElement) => {
    opener.current = target;
    setError(null);
    setDraft(emptyDraft("create"));
  };

  const openEdit = async (item: CustomAgent, target: HTMLElement) => {
    opener.current = target;
    setError(null);
    setDraft({ ...emptyDraft("edit", item), loading: true });
    try {
      const detail = await getAgent(item.id);
      setDraft((current) => current?.mode === "edit" && current.item?.id === item.id ? {
        ...current,
        loading: false,
        name: detail.name,
        description: detail.description,
        instructions: detail.content ? parseTomlValue(detail.content, "developer_instructions") : "",
        rawContent: detail.content ?? "",
        providerId: detail.providerId ?? "",
        model: detail.model ?? "",
        providerMode: detail.providerId && detail.model ? "specified" : "inherit",
      } : current);
    } catch (reason) {
      setDraft(null);
      setError(errorCode(reason));
      requestAnimationFrame(() => target.focus());
    }
  };

  const saveDraft = async () => {
    if (!draft || draft.loading || draft.committed || busy) return;
    const content = draft.mode === "import" ? draft.rawContent : serialiseDraft(draft);
    const expectedRevision = data?.revision ?? draft.item?.revision;
    if (expectedRevision === undefined || (draft.mode !== "import" && (!draft.name.trim() || !draft.instructions.trim() || (draft.providerMode === "specified" && (!draft.providerId.trim() || !draft.model.trim()))))) {
      setError("invalid_request");
      return;
    }
    const operation = draft.mode === "edit" && draft.item
      ? () => updateAgent({ id: draft.item!.id, content, expectedRevision })
      : () => createAgent({ scope, workspaceId: scope === "workspace" ? workspaceId : null, content, expectedRevision });
    const result = await mutate(operation);
    if (result === "refreshed") {
      setDraft(null);
      requestAnimationFrame(() => opener.current?.focus());
    } else if (result === "refresh_failed") {
      setDraft((current) => current ? { ...current, committed: true } : current);
    }
  };

  const beginImport = async (file: File) => {
    if (busy || loading || workspaceUnavailable || data === null) return Upload.LIST_IGNORE;
    setBusy(true); setError(null);
    try {
      if (!file.name.toLowerCase().endsWith(".toml")) throw new AgentApiError("invalid_format");
      const raw = new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer());
      setDraft({ ...emptyDraft("import"), rawContent: raw, importedFile: file.name, name: parseTomlValue(raw, "name"), description: parseTomlValue(raw, "description"), instructions: parseTomlValue(raw, "developer_instructions") });
    } catch (reason) { setError(errorCode(reason)); }
    finally { setBusy(false); }
    return Upload.LIST_IGNORE;
  };

  const openBatch = (action: AgentBatchAction, target: HTMLButtonElement) => {
    if (busy || loading || !data || !currentItems.length) return;
    batchOpener.current = target;
    const label = scope === "global" ? t("agents.global") : workspace?.name ?? workspaceId;
    setBatchError(null);
    setBatch({ action, scope, workspaceId: scope === "workspace" ? workspaceId : null, revision: data.revision, ids: currentItems.map((item) => item.id), label });
  };

  const submitBatch = async () => {
    if (!batch || batchInFlight.current || busy) return;
    batchInFlight.current = true; setBusy(true); setBatchError(null);
    try {
      await batchAgents({ scope: batch.scope, workspaceId: batch.workspaceId, ids: batch.ids, action: batch.action, expectedRevision: batch.revision });
      setBatch(null);
      await reload();
      requestAnimationFrame(() => batchOpener.current?.focus());
    } catch (reason) { setBatchError(errorCode(reason)); }
    finally { batchInFlight.current = false; setBusy(false); }
  };

  const toggleMaster = async (enabled: boolean) => {
    if (!settings) return;
    await mutate(() => setAgentSettings({ enabled, expectedRevision: settings.revision }));
  };

  const toggleAgent = async (item: CustomAgent, enabled: boolean) => {
    if (workspaceUnavailable) return;
    await mutate(() => setAgentEnabled({ id: item.id, enabled, expectedRevision: data?.revision ?? item.revision }));
  };

  const removeOne = async (item: CustomAgent) => {
    if (workspaceUnavailable) return;
    await mutate(() => deleteAgent({ id: item.id, expectedRevision: data?.revision ?? item.revision }));
  };

  const getPopupContainer = () => container ?? document.body;
  const modelChoices = providerCatalog.modelChoices;
  const providerOptions = [...new Set(modelChoices.map((choice) => choice.selection.providerId))].map((value) => ({ value, label: value }));
  const modelOptions = modelChoices.filter((choice) => !draft?.providerId || choice.selection.providerId === draft.providerId).map((choice) => ({ value: choice.selection.modelId, label: choice.label }));
  const row = (item: CustomAgent, readonly = false) => {
    const reason = REASON_VALUES.has(item.reason) ? item.reason : "invalid_format";
    const noFallback = scope === "workspace" && !readonly && normaliseName(item.name) && reason !== "effective" && globalItems.some((global) => normaliseName(global.name) === normaliseName(item.name));
    return <article className="agents-row" key={item.id}>
      <div className="agents-row-main"><strong>{item.name}</strong><Tag>{t(reasonKeys[reason as AgentReason])}</Tag>{noFallback ? <span className="agents-warning">{t("agents.noFallback")}</span> : null}</div>
      <div className="agents-row-actions">
        {readonly ? <Tag>{t("agents.readonly")}</Tag> : <>
          <Switch checked={item.enabled} disabled={busy || loading || workspaceUnavailable} aria-label={t("agents.toggle", { name: item.name })} onChange={(enabled) => void toggleAgent(item, enabled)} />
          <Tooltip title={t("common.edit")}><Button type="text" icon={<EditOutlined aria-hidden="true" />} aria-label={`${t("common.edit")} ${item.name}`} disabled={busy || loading || workspaceUnavailable} onClick={(event) => void openEdit(item, event.currentTarget)} /></Tooltip>
          <Popconfirm title={t("agents.removeConfirm", { name: item.name })} description={scope === "workspace" ? t("agents.removeInheritance") : undefined} okText={t("common.remove")} cancelText={t("common.cancel")} okButtonProps={{ danger: true }} onConfirm={() => void removeOne(item)}>
            <Button type="text" danger icon={<DeleteOutlined aria-hidden="true" />} aria-label={`${t("common.remove")} ${item.name}`} disabled={busy || loading || workspaceUnavailable} />
          </Popconfirm>
        </>}
      </div>
    </article>;
  };

  const editorBody = draft ? <div className="agents-editor" aria-busy={draft.loading || busy}>
    {draft.loading ? <p>{t("common.processing")}</p> : draft.mode === "import" ? <>
      <Alert type="info" title={t("agents.importPreview")} description={draft.importedFile} />
      <label>{t("agents.importFile")}<Input.TextArea readOnly value={draft.rawContent} rows={16} /></label>
    </> : <>
      <label>{t("agents.name")}<Input autoFocus value={draft.name} disabled={busy || draft.committed} onChange={(event) => setDraft((current) => current ? { ...current, name: event.target.value } : current)} /></label>
      <label>{t("agents.description")}<Input.TextArea value={draft.description} rows={3} disabled={busy || draft.committed} onChange={(event) => setDraft((current) => current ? { ...current, description: event.target.value } : current)} /></label>
      <label>{t("agents.instructions")}<Input.TextArea value={draft.instructions} rows={12} disabled={busy || draft.committed} onChange={(event) => setDraft((current) => current ? { ...current, instructions: event.target.value } : current)} /></label>
      <label>{t("agents.model")}
        <Select getPopupContainer={getPopupContainer} value={draft.providerMode} options={[{ value: "inherit", label: t("agents.inheritModel") }, { value: "specified", label: t("agents.specifyModel") }]} disabled={busy || draft.committed} onChange={(value: "inherit" | "specified") => setDraft((current) => current ? { ...current, providerMode: value } : current)} />
      </label>
      {draft.providerMode === "specified" ? <>
        <label>{t("agents.provider")}<Input list="agents-provider-options" value={draft.providerId} disabled={busy || draft.committed} onChange={(event) => setDraft((current) => current ? { ...current, providerId: event.target.value } : current)} /><datalist id="agents-provider-options">{providerOptions.map((option) => <option key={option.value} value={option.value} />)}</datalist></label>
        <label>{t("agents.model")}<Input list="agents-model-options" value={draft.model} disabled={busy || draft.committed} onChange={(event) => setDraft((current) => current ? { ...current, model: event.target.value } : current)} /><datalist id="agents-model-options">{modelOptions.map((option) => <option key={option.value} value={option.value} />)}</datalist></label>
      </> : null}
    </>}
    {error ? <Alert type="error" role="alert" title={t("agents.error", { code: error })} /> : null}
    <div className="agents-editor-actions"><Button onClick={() => { if (!busy) { setDraft(null); requestAnimationFrame(() => opener.current?.focus()); } }} disabled={busy}>{t("common.cancel")}</Button><Button type="primary" loading={busy} disabled={draft.loading || draft.committed || (draft.mode !== "import" && (!draft.name.trim() || !draft.instructions.trim() || (draft.providerMode === "specified" && (!draft.providerId.trim() || !draft.model.trim())))) || workspaceUnavailable} onClick={() => void saveDraft()}>{t("agents.save")}</Button></div>
    {draft.committed ? <Button loading={loading} onClick={async () => { if (await reload()) { setDraft(null); requestAnimationFrame(() => opener.current?.focus()); } }}>{t("common.retry")}</Button> : null}
  </div> : null;

  const editorOverlay = draft ? (screens.md ? <Modal rootClassName="agents-modal" open title={t(draft.mode === "create" ? "agents.createTitle" : draft.mode === "edit" ? "agents.editTitle" : "agents.importTitle")} footer={null} getContainer={container ?? undefined} destroyOnHidden onCancel={() => { if (!busy) { setDraft(null); requestAnimationFrame(() => opener.current?.focus()); } }} keyboard={!busy} mask={{ closable: !busy }} closable={!busy}>{editorBody}</Modal> : <Drawer rootClassName="agents-drawer" open title={t(draft.mode === "create" ? "agents.createTitle" : draft.mode === "edit" ? "agents.editTitle" : "agents.importTitle")} size="100%" getContainer={container ?? undefined} destroyOnHidden onClose={() => { if (!busy) { setDraft(null); requestAnimationFrame(() => opener.current?.focus()); } }} closable={!busy}>{editorBody}</Drawer>) : null;

  const actionItems = [
    { key: "enable", label: t("agents.batchEnable"), disabled: !currentItems.length || busy },
    { key: "disable", label: t("agents.batchDisable"), disabled: !currentItems.length || busy },
    { key: "remove", label: t("agents.batchRemove"), danger: true, disabled: !currentItems.length || busy },
  ];

  return <section className="agents-settings" aria-label={t("settings.category.agents")}>
    <div className="agents-heading"><div><h2>{t("settings.category.agents")}</h2><p>{t("agents.intro")}</p></div><label className="agents-master">{t("agents.master")} <Switch aria-label={t("agents.master")} checked={settings?.enabled ?? false} disabled={!settings || busy || loading} onChange={(enabled) => void toggleMaster(enabled)} /></label></div>
    <Tabs activeKey={scope} onChange={(key) => { if (!busy) { generation.current += 1; setScope(key as AgentScope); } }} items={[{ key: "global", label: t("agents.global"), disabled: busy }, { key: "workspace", label: t("agents.workspace"), disabled: busy }]} />
    {scope === "workspace" ? <div className="agents-workspace-select"><label htmlFor="agents-workspace">{t("agents.workspaceSelect")}</label><Select id="agents-workspace" getPopupContainer={getPopupContainer} aria-label={t("agents.workspaceSelect")} value={workspaceId || undefined} disabled={busy || loading} options={workspaces.catalog?.workspaces.map((item) => ({ value: item.id, label: item.kind === "default" ? t("workspaces.default") : item.name }))} onChange={(value) => { generation.current += 1; setData(null); setInherited(null); setWorkspaceId(value); }} /></div> : null}
    {workspaceUnavailable ? <Alert type="warning" title={t("agents.workspaceUnavailable")} /> : null}
    {error ? <Alert type="error" title={t("agents.error", { code: error })} action={<Button loading={loading} disabled={busy} onClick={() => void reload()}>{t("common.retry")}</Button>} /> : null}
    <div className="agents-toolbar"><h3>{t(scope === "global" ? "agents.global" : "agents.workspace")} <span>· {data?.items.length ?? "—"}</span></h3><div className="agents-toolbar-actions">
      <Tooltip title={t("agents.scan")} getPopupContainer={getPopupContainer}><Button aria-label={t("agents.scan")} icon={<ReloadOutlined />} disabled={busy || loading || !data || workspaceUnavailable} onClick={() => { if (data) void mutate(() => scanAgents({ scope, workspaceId: scope === "workspace" ? workspaceId : null, expectedRevision: data.revision })); }} /></Tooltip>
      <Upload accept=".toml,text/plain" multiple={false} showUploadList={false} beforeUpload={beginImport} disabled={busy || loading || !data || workspaceUnavailable}><Button icon={<UploadOutlined aria-hidden="true" />} disabled={busy || loading || !data || workspaceUnavailable}>{t("agents.import")}</Button></Upload>
      <Button type="primary" icon={<PlusOutlined aria-hidden="true" />} disabled={busy || loading || !data || workspaceUnavailable} onClick={(event) => openCreate(event.currentTarget)}>{t("agents.create")}</Button>
      <Dropdown trigger={["click"]} getPopupContainer={getPopupContainer} menu={{ items: actionItems, onClick: ({ key, domEvent }) => openBatch(key as AgentBatchAction, domEvent.currentTarget as HTMLButtonElement) }}><Button aria-label={t("agents.batchMenu")} icon={<MoreOutlined aria-hidden="true" />} disabled={busy || loading || !data || !currentItems.length} /></Dropdown>
    </div></div>
    {loading && !data ? <p className="agents-loading">{t("common.processing")}</p> : data && currentItems.length ? <>
      <div className="agents-list">{visibleItems.map((item) => row(item))}</div>
      <Pagination current={currentPageNumber} pageSize={20} total={currentItems.length} hideOnSinglePage onChange={setPage} />
    </> : <Empty description={t("agents.empty")} />}
    {scope === "workspace" ? <div className="agents-inherited"><h3>{t("agents.inheritedSection")}</h3><p>{t("agents.inheritanceHint")}</p>{inheritedItems.length ? <><div className="agents-list">{inheritedItems.slice((globalPageNumber - 1) * 20, globalPageNumber * 20).map((item) => row(item, true))}</div><Pagination current={globalPageNumber} pageSize={20} total={inheritedItems.length} hideOnSinglePage onChange={setGlobalPage} /></> : <Empty description={t("agents.empty")} />}</div> : null}
    {editorOverlay}
    <Modal open={batch !== null} title={t("agents.batchConfirm")} okText={t("agents.batchConfirm")} cancelText={t("common.cancel")} okButtonProps={{ danger: batch?.action === "remove" }} confirmLoading={busy} getContainer={container ?? undefined} onCancel={() => { if (!busy) { setBatch(null); requestAnimationFrame(() => batchOpener.current?.focus()); } }} onOk={() => void submitBatch()}>{batch ? <div className="agents-batch-confirm"><p>{t("agents.batchScope", { scope: batch.label, count: batch.ids.length })}</p><p>{t(batch.action === "enable" ? "agents.batchEnableHint" : batch.action === "disable" ? "agents.batchDisableHint" : "agents.batchRemoveHint")}</p>{batchError ? <Alert type="error" title={t("agents.error", { code: batchError })} /> : null}</div> : null}</Modal>
  </section>;
}

export default AgentsSettings;
