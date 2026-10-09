import { DeleteOutlined, DownloadOutlined, ReloadOutlined, UploadOutlined } from "@ant-design/icons";
import { Alert, Button, Checkbox, Descriptions, Drawer, Empty, Form, Grid, Modal, Popconfirm, Space, Table, Tag, Tooltip, Typography, Upload, type TableColumnsType } from "antd";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  downloadExecutionDeployment, ExecutionPackageApiError, getExecutionPackages, importExecutionPackage,
  MAX_EXECUTION_PACKAGE_BYTES, removeExecutionPackage,
  type ExecutionPackage, type ExecutionPackageCatalog, type ExecutionPackageErrorCode,
} from "../../api/executionPluginPackages";
import type { MessageKey, Translator } from "../../i18n/catalog";
import { useI18n } from "../../i18n/I18nProvider";

const statusKeys: Record<ExecutionPackage["runtimeStatus"], MessageKey> = {
  not_installed: "execution.packages.status.notInstalled", confirmed: "execution.packages.status.confirmed",
  unverified: "execution.packages.status.unverified", mismatch: "execution.packages.status.mismatch",
  needs_update: "execution.packages.status.needsUpdate",
};
const errorKeys: Record<ExecutionPackageErrorCode, MessageKey> = {
  invalid_request: "execution.packages.error.invalidRequest", invalid_package: "execution.packages.error.invalidPackage",
  incompatible_package: "execution.packages.error.incompatible", package_too_large: "execution.packages.error.tooLarge",
  package_not_found: "execution.packages.error.notFound", packages_store_unavailable: "execution.packages.error.storeUnavailable",
  deployment_unavailable: "execution.packages.error.deploymentUnavailable", internal_error: "execution.packages.error.internal",
  network_error: "execution.packages.error.network", malformed_response: "execution.packages.error.malformed",
};
function errorText(error: unknown, t: Translator) {
  return t(errorKeys[error instanceof ExecutionPackageApiError ? error.code : "internal_error"]);
}
const sizeText = (size: number) => `${(size / 1024).toFixed(1)} KiB`;
const compatibleApi = (item: ExecutionPackage) => item.plugins.every(plugin => plugin.apiVersion === 5 && plugin.kind === "loop");
type Pending = { kind: "import" | "remove" | "download"; id?: string };

export function ExecutionPackageManager({ active, catalogBusy, onRefreshCatalog, onGuide }: { active: boolean; catalogBusy: boolean; onRefreshCatalog: () => Promise<void>; onGuide: () => void }) {
  const { t, locale } = useI18n();
  const screens = Grid.useBreakpoint();
  const generation = useRef(0);
  const operation = useRef(false);
  const [catalog, setCatalog] = useState<ExecutionPackageCatalog | null>(null);
  const [loading, setLoading] = useState(false);
  const [pending, setPending] = useState<Pending | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [notice, setNotice] = useState<MessageKey | null>(null);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [trusted, setTrusted] = useState(false);
  const [importError, setImportError] = useState<unknown>(null);
  const busy = loading || pending !== null;
  const detail = catalog?.packages.find((item) => item.id === detailId);
  const downloadBlocked = catalog?.runtime.kind !== "docker" ? "execution.packages.localInstall" : catalog.runtime.baseImage === null ? "execution.packages.noBaseImage" : null;

  const reload = useCallback(async () => {
    const request = ++generation.current;
    setLoading(true);
    // Reopening invalidates results, but keeps the operation busy until its owner settles.
    setCatalog(null);
    setDetailId(null);
    setError(null);
    setNotice(null);
    try {
      const next = await getExecutionPackages();
      if (request === generation.current) setCatalog(next);
    } catch (failure) {
      if (request === generation.current) setError(failure);
    } finally {
      if (request === generation.current) setLoading(false);
    }
  }, []);
  useEffect(() => {
    if (active) void reload();
    else { setImportOpen(false); setDetailId(null); }
    return () => { generation.current += 1; };
  }, [active, reload]);

  const openImport = () => {
    if (busy || operation.current) return;
    setFile(null); setTrusted(false); setImportError(null); setImportOpen(true);
  };
  const closeImport = () => { if (pending?.kind !== "import") setImportOpen(false); };
  const importWheel = async () => {
    if (!file || !trusted || busy || operation.current) return;
    const request = ++generation.current;
    operation.current = true; setPending({ kind: "import" }); setImportError(null); setNotice(null);
    try {
      const next = await importExecutionPackage(file);
      if (request !== generation.current) return;
      setCatalog(next); setError(null); setImportOpen(false); setFile(null); setTrusted(false);
      setNotice("execution.packages.imported");
    } catch (failure) {
      if (request === generation.current) setImportError(failure);
    } finally {
      operation.current = false;
      setPending(null);
    }
  };
  const remove = async (item: ExecutionPackage) => {
    if (busy || operation.current) return;
    const request = ++generation.current;
    operation.current = true; setPending({ kind: "remove", id: item.id }); setError(null); setNotice(null);
    try {
      await removeExecutionPackage(item.id);
      if (request !== generation.current) return;
      setCatalog(null); setDetailId(null);
      const next = await getExecutionPackages();
      if (request !== generation.current) return;
      setCatalog(next); setNotice("execution.packages.removed");
    } catch (failure) {
      if (request === generation.current) setError(failure);
    } finally {
      operation.current = false;
      setPending(null);
    }
  };
  const download = async (item: ExecutionPackage) => {
    if (busy || operation.current || downloadBlocked || !compatibleApi(item)) return;
    const request = ++generation.current;
    operation.current = true; setPending({ kind: "download", id: item.id }); setError(null); setNotice(null);
    try {
      const blob = await downloadExecutionDeployment(item.id);
      if (request !== generation.current) return;
      const url = URL.createObjectURL(blob);
      try {
        const anchor = document.createElement("a");
        anchor.href = url; anchor.download = "opensprite-execution-plugin-deployment.zip";
        document.body.appendChild(anchor); anchor.click(); anchor.remove();
      } finally {
        window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      }
      setNotice("execution.packages.downloaded");
    } catch (failure) {
      if (request === generation.current) setError(failure);
    } finally {
      operation.current = false;
      setPending(null);
    }
  };
  const refreshRuntime = () => {
    if (busy || catalogBusy || operation.current) return;
    void Promise.allSettled([reload(), onRefreshCatalog()]);
  };
  const status = (item: ExecutionPackage) => <Tag color={!compatibleApi(item) || item.runtimeStatus === "mismatch" ? "warning" : undefined}>{t(compatibleApi(item) ? statusKeys[item.runtimeStatus] : "execution.packages.retiredApi")}</Tag>;
  const downloadButton = (item: ExecutionPackage) => {
    const reason = compatibleApi(item) ? downloadBlocked : "execution.packages.retiredApi";
    return <Tooltip title={reason ? t(reason) : undefined}><Button size="small" icon={<DownloadOutlined aria-hidden />} disabled={busy || reason !== null} loading={pending?.kind === "download" && pending.id === item.id} aria-label={t("execution.packages.downloadFor", { name: item.distributionName })} onClick={() => void download(item)}>{t("execution.packages.download")}</Button></Tooltip>;
  };
  const columns: TableColumnsType<ExecutionPackage> = [
    { key: "name", title: t("execution.packages.distribution"), width: 260, render: (_, item) => <div className="execution-settings__identity"><strong>{item.distributionName}</strong><code>{item.fileName}</code></div> },
    { key: "version", title: t("execution.column.version"), width: 90, dataIndex: "version" },
    { key: "status", title: t("execution.packages.runtimeStatus"), width: 150, render: (_, item) => status(item) },
    { key: "actions", title: t("execution.column.actions"), width: 240, align: "right", render: (_, item) => <Space size={8}><Button size="small" type="link" aria-label={t("execution.inspect", { name: item.distributionName })} onClick={() => setDetailId(item.id)}>{t("execution.details")}</Button>{downloadButton(item)}<Popconfirm title={<span className="execution-packages__remove-title">{t("execution.packages.removeTitle", { name: item.fileName })}</span>} description={t("execution.packages.removeHelp")} okText={t("execution.packages.remove")} cancelText={t("execution.packages.cancel")} onConfirm={() => remove(item)} disabled={busy}><Button size="small" type="text" danger icon={<DeleteOutlined aria-hidden />} aria-label={t("execution.packages.removeFor", { name: item.fileName })} disabled={busy} loading={pending?.kind === "remove" && pending.id === item.id} /></Popconfirm></Space> },
  ];
  const plugins = detail?.plugins ?? [];

  return <section className="execution-packages" aria-label={t("execution.packages.title")}>
    <div className="execution-settings__catalog-header"><div><h3>{t("execution.packages.title")}</h3><p className="settings-helper-text">{t("execution.packages.scope")}</p></div><Space size={8} wrap><Button icon={<ReloadOutlined aria-hidden />} disabled={busy || catalogBusy} onClick={refreshRuntime}>{t("execution.packages.refresh")}</Button><Button icon={<UploadOutlined aria-hidden />} disabled={busy} onClick={openImport}>{t("execution.packages.import")}</Button></Space></div>
    {catalog ? <div className="execution-packages__runtime"><span>{t(catalog.runtime.kind === "docker" ? "execution.packages.dockerRuntime" : "execution.packages.localRuntime")}</span>{catalog.runtime.baseImage ? <code>{catalog.runtime.baseImage}</code> : null}<span>{t(catalog.runtime.manifestStatus === "verified" ? "execution.packages.manifestVerified" : catalog.runtime.manifestStatus === "invalid" ? "execution.packages.manifestInvalid" : "execution.packages.manifestMissing")}</span></div> : null}
    {downloadBlocked && catalog ? <p className="settings-helper-text execution-packages__install-help">{t(downloadBlocked)} <Button type="link" size="small" onClick={onGuide}>{t("execution.installGuide")}</Button></p> : null}
    {error !== null ? <Alert type="error" showIcon title={errorText(error, t)} action={<Button disabled={busy} onClick={() => void reload()}>{t("general.reload")}</Button>} /> : null}
    {notice ? <p className="execution-packages__notice" role="status">{t(notice)}</p> : null}
    {loading ? <p className="settings-helper-text" role="status">{t("execution.packages.loading")}</p> : null}
    <Table<ExecutionPackage> size="small" rowKey="id" columns={columns} dataSource={catalog?.packages ?? []} pagination={false} loading={loading} scroll={{ x: 740 }} locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={t("execution.packages.empty")} /> }} />
    <Modal open={importOpen} title={t("execution.packages.importTitle")} onCancel={closeImport} closable={pending?.kind !== "import"} keyboard={pending?.kind !== "import"} destroyOnHidden footer={<Space size={8}><Button aria-label={t("execution.packages.cancel")} disabled={pending?.kind === "import"} onClick={closeImport}>{t("execution.packages.cancel")}</Button><Button type="primary" aria-label={t("execution.packages.confirmImport")} aria-busy={pending?.kind === "import"} loading={pending?.kind === "import"} disabled={!file || !trusted || busy} onClick={() => void importWheel()}>{t("execution.packages.confirmImport")}</Button></Space>}>
      <Alert type="info" showIcon title={t("execution.packages.importHelp")} />
      {importError !== null ? <Alert className="execution-packages__import-error" type="error" showIcon title={errorText(importError, t)} /> : null}
      <Form layout="vertical" className="execution-packages__import-form"><Form.Item label={t("execution.packages.wheelFile")} extra={t("execution.packages.fileHelp")}><Upload accept=".whl" multiple={false} showUploadList={false} disabled={pending?.kind === "import"} beforeUpload={(next) => {
        if (pending?.kind === "import") return Upload.LIST_IGNORE;
        setFile(null); setTrusted(false); setImportError(null);
        if (next.size > MAX_EXECUTION_PACKAGE_BYTES) setImportError(new ExecutionPackageApiError("package_too_large"));
        else if (!next.size || !next.name.endsWith(".whl")) setImportError(new ExecutionPackageApiError("invalid_package"));
        else setFile(next);
        return Upload.LIST_IGNORE;
      }}><Button icon={<UploadOutlined aria-hidden />} disabled={pending?.kind === "import"}>{t("execution.packages.chooseFile")}</Button></Upload>{file ? <div className="execution-packages__file"><code>{file.name}</code><span>{sizeText(file.size)}</span></div> : null}</Form.Item><Form.Item><Checkbox checked={trusted} disabled={!file || pending?.kind === "import"} onChange={(event) => setTrusted(event.target.checked)}>{t("execution.packages.trust")}</Checkbox></Form.Item></Form>
    </Modal>
    <Drawer open={detail !== undefined} title={t("execution.packages.detailsTitle")} size={screens.md ? 680 : "100%"} onClose={() => setDetailId(null)} destroyOnHidden className="execution-settings__drawer execution-packages__drawer" footer={detail ? <>{error !== null ? <Alert className="execution-settings__error" type="error" showIcon title={errorText(error, t)} /> : null}<div className="execution-settings__drawer-footer"><Button onClick={() => setDetailId(null)}>{t("execution.close")}</Button>{downloadButton(detail)}</div></> : null}>
      {detail ? <><h3>{detail.distributionName}</h3><Descriptions size="small" column={1} items={[
        { key: "file", label: t("execution.packages.wheelFile"), children: <code>{detail.fileName}</code> },
        { key: "version", label: t("execution.column.version"), children: detail.version },
        { key: "status", label: t("execution.packages.runtimeStatus"), children: status(detail) },
        { key: "sha", label: "SHA-256", children: <Typography.Text copyable={{ text: detail.sha256, tooltips: [t("chat.copyCode"), t("chat.copiedCode")] }}><code>{detail.sha256}</code></Typography.Text> },
        { key: "size", label: t("execution.packages.size"), children: sizeText(detail.sizeBytes) },
        { key: "imported", label: t("execution.packages.importedAt"), children: new Intl.DateTimeFormat(locale, { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date(detail.importedAt)) },
        { key: "python", label: "Requires-Python", children: detail.requiresPython ?? t("execution.packages.notDeclared") },
      ]} /><p className="execution-settings__detail-description">{t(detail.runtimeStatus === "confirmed" ? "execution.packages.confirmedHelp" : detail.runtimeStatus === "unverified" ? "execution.packages.unverifiedHelp" : detail.runtimeStatus === "mismatch" ? "execution.packages.mismatchHelp" : "execution.packages.notInstalledHelp")}</p><h4>{t("execution.packages.dependencies")}</h4>{detail.requiresDist.length ? <ul>{detail.requiresDist.map((dependency, index) => <li key={index}><code>{dependency}</code></li>)}</ul> : <p>{t("execution.packages.noDependencies")}</p>}<h4>{t("execution.packages.plugins")}</h4><Table size="small" rowKey={(item) => `${item.kind}:${item.id}`} dataSource={plugins} pagination={false} scroll={{ x: 420 }} columns={[
        { key: "id", title: t("execution.pluginId"), render: (_, item) => <div className="execution-settings__identity"><strong>{item.id}</strong><code>{item.entryPoint}</code></div> },
        { key: "kind", title: t("execution.column.kind"), width: 100, render: (_, item) => t(item.kind === "loop" ? "execution.loop" : "execution.policy") },
        { key: "api", title: "API", width: 64, dataIndex: "apiVersion" },
      ]} /></> : null}
    </Drawer>
  </section>;
}
