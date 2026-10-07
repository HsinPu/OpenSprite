import { BookOutlined, CodeOutlined, ReloadOutlined } from "@ant-design/icons";
import { Alert, Button, ConfigProvider, Descriptions, Drawer, Empty, Grid, Space, Table, Tabs, Tag, theme, type TableColumnsType } from "antd";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  executionSettingsErrorText, getExecutionSettings, putExecutionSettings,
  type ExecutionPlugin, type ExecutionSelection, type ExecutionSettings as ExecutionSettingsData,
} from "../../api/executionSettings";
import type { MessageKey } from "../../i18n/catalog";
import { useI18n } from "../../i18n/I18nProvider";
import { ExecutionDeveloperGuide, type DeveloperGuideTab } from "./ExecutionDeveloperGuide";
import { ExecutionPackageManager } from "./ExecutionPackageManager";
import { SaveStatus } from "./SettingsPrimitives";
import "./ExecutionSettings.css";

const statusKeys: Record<ExecutionPlugin["status"], MessageKey> = {
  available: "execution.status.available", incompatible: "execution.status.incompatible", unavailable: "execution.status.unavailable",
};
const sameSelection = (left: ExecutionSelection, right: ExecutionSelection) => left.loopId === right.loopId && left.policyId === right.policyId;
type PluginRow = { id: string; kind: ExecutionPlugin["kind"]; plugin: ExecutionPlugin | null };

export function ExecutionSettings({ active }: { active: boolean }) {
  const { t } = useI18n();
  const { token } = theme.useToken();
  const screens = Grid.useBreakpoint();
  const requestVersion = useRef(0);
  const draftRef = useRef<ExecutionSelection | null>(null);
  const [data, setData] = useState<ExecutionSettingsData | null>(null);
  const [draft, setDraft] = useState<ExecutionSelection | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);
  const [kind, setKind] = useState<ExecutionPlugin["kind"]>("loop");
  const [detail, setDetail] = useState<PluginRow | null>(null);
  const [guideOpen, setGuideOpen] = useState(false);
  const [guideTab, setGuideTab] = useState<DeveloperGuideTab>("loop");

  useEffect(() => { draftRef.current = draft; }, [draft]);
  const reload = useCallback(async (preserveDraft = false) => {
    const previousDraft = preserveDraft ? draftRef.current : null;
    const request = ++requestVersion.current;
    setLoading(true);
    setSaving(false);
    setError(null);
    setSaved(false);
    setData(null);
    setDraft(null);
    setDetail(null);
    try {
      const next = await getExecutionSettings();
      if (request !== requestVersion.current) return;
      setData(next);
      const stillAvailable = previousDraft !== null
        && next.plugins.some((plugin) => plugin.kind === "loop" && plugin.id === previousDraft.loopId && plugin.status === "available")
        && next.plugins.some((plugin) => plugin.kind === "policy" && plugin.id === previousDraft.policyId && plugin.status === "available");
      setDraft(stillAvailable ? previousDraft : next.selection);
    } catch (failure) {
      if (request === requestVersion.current) setError(failure);
    } finally {
      if (request === requestVersion.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (active) void reload();
    else { setDetail(null); setGuideOpen(false); }
    return () => { requestVersion.current += 1; };
  }, [active, reload]);

  const selectedPlugin = (type: ExecutionPlugin["kind"], id: string | undefined) => data?.plugins.find((item) => item.kind === type && item.id === id);
  const selectionAvailable = draft !== null
    && selectedPlugin("loop", draft.loopId)?.status === "available"
    && selectedPlugin("policy", draft.policyId)?.status === "available";
  const dirty = data !== null && draft !== null && !sameSelection(data.selection, draft);
  const busy = loading || saving;
  const pluginName = (row: PluginRow) => row.id === "standard"
    ? t(row.kind === "loop" ? "execution.standardLoopName" : "execution.standardPolicyName")
    : row.kind === "policy" && row.id === "no_recovery" ? t("execution.noRecoveryName") : row.plugin?.name ?? row.id;
  const description = (row: PluginRow) => {
    if (!row.plugin) return t("execution.missingPlugin");
    const builtinKey: MessageKey | null = row.id === "standard"
      ? (row.kind === "loop" ? "execution.standardLoopDescription" : "execution.standardPolicyDescription")
      : row.kind === "policy" && row.id === "no_recovery" ? "execution.noRecoveryDescription" : null;
    return builtinKey ? t(builtinKey) : row.plugin.description || t("execution.noDescription");
  };
  const status = (row: PluginRow) => <Tag color={row.plugin?.status === "incompatible" ? "warning" : undefined}>{t(statusKeys[row.plugin?.status ?? "unavailable"])}</Tag>;
  const selectedId = (selection: ExecutionSelection | null, type: ExecutionPlugin["kind"]) => type === "loop" ? selection?.loopId : selection?.policyId;
  const rowFor = (type: ExecutionPlugin["kind"], id: string): PluginRow => ({ id, kind: type, plugin: selectedPlugin(type, id) ?? null });
  const choose = (row: PluginRow) => {
    if (busy || !draft || row.plugin?.status !== "available") return;
    setDraft({ ...draft, [row.kind === "loop" ? "loopId" : "policyId"]: row.id });
    setSaved(false);
  };
  const save = async () => {
    if (busy || !data || !draft || !dirty || !selectionAvailable) return;
    const request = ++requestVersion.current;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const next = await putExecutionSettings(draft);
      if (request !== requestVersion.current) return;
      setData(next);
      setDraft(next.selection);
      setSaved(true);
    } catch (failure) {
      if (request === requestVersion.current) setError(failure);
    } finally {
      if (request === requestVersion.current) setSaving(false);
    }
  };
  const openGuide = (tab: DeveloperGuideTab) => { setGuideTab(tab); setGuideOpen(true); };
  const rows: PluginRow[] = loading ? [] : (data?.plugins ?? []).filter((item) => item.kind === kind).map((plugin) => ({ id: plugin.id, kind, plugin }));
  if (!loading) {
    for (const id of [selectedId(data?.selection ?? null, kind), selectedId(draft, kind)]) {
      if (id && !rows.some((row) => row.id === id)) rows.push(rowFor(kind, id));
    }
  }
  const columns: TableColumnsType<PluginRow> = [
    { title: t("execution.column.name"), key: "name", width: 230, render: (_, row) => <div className="execution-settings__identity"><strong>{pluginName(row)}</strong><code>{row.id}</code>{row.id === selectedId(data?.selection ?? null, row.kind) ? <span className="execution-settings__saved-badge">{t("execution.savedBadge")}</span> : null}</div> },
    { title: t("execution.column.behavior"), key: "behavior", responsive: ["lg"], render: (_, row) => <p className="execution-settings__description">{description(row)}</p> },
    { title: t("execution.column.version"), key: "version", width: 90, render: (_, row) => row.plugin?.version ?? "—" },
    { title: "API", key: "api", width: 64, render: (_, row) => row.plugin?.apiVersion ?? "—" },
    { title: t("execution.column.status"), key: "status", width: 116, render: (_, row) => status(row) },
    { title: t("execution.column.actions"), key: "actions", width: 80, align: "right", render: (_, row) => <Button type="link" size="small" aria-label={t("execution.inspect", { name: pluginName(row) })} onClick={() => setDetail(row)}>{t("execution.details")}</Button> },
  ];
  const savedSummary = (type: ExecutionPlugin["kind"]) => {
    const id = selectedId(data?.selection ?? null, type);
    if (!id || loading) return <span className="execution-settings__placeholder">—</span>;
    const row = rowFor(type, id);
    return <><strong>{pluginName(row)}</strong><div className="execution-settings__summary-metadata"><code>{id}</code><span>{row.plugin ? t("execution.version", { version: row.plugin.version }) : "—"}</span>{status(row)}</div></>;
  };

  return <div className="execution-settings settings-form-stack">
    <div className="settings-intro execution-settings__header"><div><h2>{t("settings.category.execution")}</h2><p>{t("execution.intro")}</p></div><Button icon={<CodeOutlined aria-hidden />} onClick={() => openGuide("loop")}>{t("execution.developerGuide")}</Button></div>
    {error !== null ? <Alert className="execution-settings__error" type="error" showIcon title={executionSettingsErrorText(error, t)} action={<Button disabled={busy} onClick={() => void reload()}>{t("general.reload")}</Button>} /> : null}
    {loading ? <p className="settings-helper-text" role="status">{t("execution.loading")}</p> : null}
    <section className="execution-settings__saved" aria-label={t("execution.savedTitle")}>
      <div className="execution-settings__section-title"><h3>{t("execution.savedTitle")}</h3>{saved ? <SaveStatus saved /> : null}</div>
      <dl className="execution-settings__saved-grid"><div><dt>{t("execution.loop")}</dt><dd>{savedSummary("loop")}</dd></div><div><dt>{t("execution.policy")}</dt><dd>{savedSummary("policy")}</dd></div></dl>
      <p className="settings-helper-text execution-settings__scope">{t("execution.scope")}</p>
    </section>
    <section className="execution-settings__catalog" aria-label={t("execution.selectionTitle")}>
      <div className="execution-settings__catalog-header"><div><h3>{t("execution.selectionTitle")}</h3><p className="settings-helper-text">{t("execution.draftHelp")}</p></div><Space size={8}><Button icon={<BookOutlined aria-hidden />} onClick={() => openGuide("install")}>{t("execution.installGuide")}</Button><Button icon={<ReloadOutlined aria-hidden />} aria-label={t("general.reload")} disabled={busy} onClick={() => void reload()} /></Space></div>
      <Tabs activeKey={kind} onChange={(key) => setKind(key as ExecutionPlugin["kind"])} items={[{ key: "loop", label: t("execution.loop") }, { key: "policy", label: t("execution.policy") }]} />
      <ConfigProvider theme={{ components: { Table: { rowSelectedBg: token.colorFillTertiary, rowSelectedHoverBg: token.colorFillSecondary } } }}><Table<PluginRow> size="small" rowKey="id" columns={columns} dataSource={rows} pagination={false} loading={loading} scroll={{ x: 620 }} locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={t("execution.emptyPlugins")} /> }} rowSelection={{ type: "radio", columnWidth: 40, selectedRowKeys: draft && !loading ? [selectedId(draft, kind)!] : [], onChange: (_, selectedRows) => { if (selectedRows[0]) choose(selectedRows[0]); }, getCheckboxProps: (row) => ({ name: `execution-${kind}`, disabled: busy || row.plugin?.status !== "available", "aria-label": t("execution.chooseDraft", { name: pluginName(row) }) }) }} /></ConfigProvider>
    </section>
    <div className="execution-settings__apply-bar" aria-label={t("execution.draftTitle")}>
      <div><strong>{t(dirty && !loading ? "execution.draftPending" : "execution.draftNone")}</strong>{draft && !loading ? <p>{t("execution.draftPair", { loop: pluginName(rowFor("loop", draft.loopId)), policy: pluginName(rowFor("policy", draft.policyId)) })}</p> : null}{draft && !selectionAvailable && !loading ? <p className="execution-settings__unavailable">{t("execution.unavailableDraft")}</p> : null}</div>
      <Space size={8}><Button disabled={!dirty || busy} onClick={() => { if (data) setDraft(data.selection); setError(null); setSaved(false); }}>{t("execution.cancelDraft")}</Button><Button type="primary" aria-label={t("execution.applyDraft")} aria-busy={saving} loading={saving} disabled={!dirty || !selectionAvailable || busy} onClick={() => void save()}>{t("execution.applyDraft")}</Button></Space>
    </div>
    <Drawer open={detail !== null} title={t("execution.pluginDetailsTitle")} size={screens.md ? 560 : "100%"} onClose={() => setDetail(null)} destroyOnHidden className="execution-settings__drawer" footer={<div className="execution-settings__drawer-footer"><Button onClick={() => setDetail(null)}>{t("execution.close")}</Button><Button type="primary" disabled={busy || !detail || detail.plugin?.status !== "available" || detail.id === selectedId(draft, detail.kind)} onClick={() => { if (detail) choose(detail); setDetail(null); }}>{t("execution.useDraft")}</Button></div>}>
      {detail ? <><h3>{pluginName(detail)}</h3><p className="execution-settings__detail-description">{description(detail)}</p><Descriptions size="small" column={1} items={[{ key: "kind", label: t("execution.column.kind"), children: t(detail.kind === "loop" ? "execution.loop" : "execution.policy") }, { key: "id", label: t("execution.pluginId"), children: <code>{detail.id}</code> }, { key: "version", label: t("execution.column.version"), children: detail.plugin?.version ?? "—" }, { key: "api", label: "API", children: detail.plugin?.apiVersion ?? "—" }, { key: "status", label: t("execution.column.status"), children: status(detail) }]} />{detail.plugin?.status !== "available" ? <Alert type="warning" showIcon title={t("execution.unavailablePlugin")} /> : null}</> : null}
    </Drawer>
    <ExecutionDeveloperGuide open={guideOpen} tab={guideTab} onTab={setGuideTab} onClose={() => setGuideOpen(false)} />
    <ExecutionPackageManager active={active} catalogBusy={busy} onRefreshCatalog={() => reload(true)} onGuide={() => openGuide("install")} />
  </div>;
}
