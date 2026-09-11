import { useEffect, useId, useRef, useState } from "react";
import { Alert, Button, Checkbox, Drawer, Dropdown, Form, Grid, Input, InputNumber, Modal, Popconfirm, Radio } from "antd";
import { ApiOutlined, EllipsisOutlined } from "@ant-design/icons";
import { useI18n } from "../../i18n/I18nProvider";
import { useCustomProviders } from "../ai-settings/useCustomProviders";
import type { CustomProvider } from "../../api/customProviders";
import { customProviderErrorText } from "../ai-settings/customProviderErrors";

export function CustomProviderCreate({ onChanged, container, hasCustomProviders, onOverlayChange }: { onChanged: () => Promise<unknown>; container: HTMLElement | null; hasCustomProviders: boolean; onOverlayChange?: (open: boolean) => void }) {
  const { t } = useI18n();
  const formId = useId();
  const controller = useCustomProviders(hasCustomProviders);
  const screens = Grid.useBreakpoint();
  const [open, setOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState<CustomProvider | null>(null);
  const [removingProvider, setRemovingProvider] = useState<CustomProvider | null>(null);
  const menuOpener = useRef<HTMLElement | null>(null);
  const [editingModelKey, setEditingModelKey] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [auth, setAuth] = useState<"none" | "bearer">("bearer");
  const [key, setKey] = useState("");
  const [allowHttp, setAllowHttp] = useState(false);
  const [editingModels, setEditingModels] = useState<string | null>(null);
  const [modelFormOpen, setModelFormOpen] = useState(false);
  const [modelSearch, setModelSearch] = useState("");
  const [modelId, setModelId] = useState("");
  const [modelName, setModelName] = useState("");
  const [contextLimit, setContextLimit] = useState(8192);
  const [outputLimit, setOutputLimit] = useState(2048);
  const [tools, setTools] = useState(false);
  useEffect(() => {
    if (!open && !removingProvider && !editingModels) return;
    onOverlayChange?.(true);
    return () => onOverlayChange?.(false);
  }, [open, removingProvider, editingModels, onOverlayChange]);
  const close = () => { if (!controller.saving) { setOpen(false); setKey(""); } };
  const content = <Form layout="vertical" onFinish={async () => {
    const draft = { name, baseUrl: url, protocol: "openai_chat_completions" as const, authMode: auth,
      allowInsecureLocal: allowHttp, ...(auth === "bearer" && key ? { apiKey: key } : {}) };
    const saved = editingProvider ? await controller.update(editingProvider, draft) : await controller.create(draft);
    if (saved) { setKey(""); setOpen(false); await onChanged(); }
  }}>
    {controller.error ? <Alert type="error" title={customProviderErrorText(controller.error, t)} action={<Button onClick={() => void controller.reload()} disabled={controller.saving}>{t("common.retry")}</Button>} /> : null}
    <Form.Item label={t("models.custom.name")} htmlFor={`${formId}-name`}><Input id={`${formId}-name`} value={name} maxLength={80} onChange={(event) => setName(event.target.value)} disabled={controller.saving} /></Form.Item>
    <Form.Item label={t("models.custom.baseUrl")} htmlFor={`${formId}-url`}><Input id={`${formId}-url`} value={url} placeholder="https://example.com/v1" onChange={(event) => setUrl(event.target.value)} disabled={controller.saving} /></Form.Item>
    <Form.Item label={t("models.custom.auth")}><Radio.Group aria-label={t("models.custom.auth")} value={auth} onChange={(event) => { setAuth(event.target.value); setKey(""); }} disabled={controller.saving} optionType="button" options={[{ value: "bearer", label: "Bearer Token" }, { value: "none", label: t("models.custom.none") }]} /></Form.Item>
    {auth === "bearer" ? <Form.Item label="API Key" htmlFor={`${formId}-key`}><Input.Password id={`${formId}-key`} value={key} autoComplete="new-password" onChange={(event) => setKey(event.target.value)} disabled={controller.saving} /></Form.Item> : null}
    <Form.Item><Checkbox checked={allowHttp} onChange={(event) => setAllowHttp(event.target.checked)} disabled={controller.saving}>{t("models.custom.allowHttp")}</Checkbox></Form.Item>
    {allowHttp ? <Alert type="warning" title={t("models.custom.httpWarning")} /> : null}
    {editingProvider && auth === "bearer" ? <p>{t("models.custom.keepKey")}</p> : null}
    <Button type="primary" htmlType="submit" loading={controller.saving} disabled={controller.loading || controller.catalog === null || !name.trim() || !url.trim() || (auth === "bearer" && !key && !editingProvider)}>{t("common.save")}</Button>
  </Form>;
  return <>
    {!open && !removingProvider && controller.error ? <Alert type="error" title={customProviderErrorText(controller.error, t)} action={<Button onClick={() => void controller.reload()}>{t("common.retry")}</Button>} /> : null}
    {controller.catalog?.providers.map((provider) => <section key={provider.id} className="settings-service-card">
      <div className="settings-service-identity"><ApiOutlined className="settings-icon" aria-hidden="true" /><span><strong>{provider.name}</strong><small>{provider.models.length} {t("models.custom.models")} · {provider.base_url}</small></span></div>
      <div className="settings-service-actions">
        <Button disabled={controller.saving} onClick={() => { setEditingProvider(provider); setName(provider.name); setUrl(provider.base_url); setAuth(provider.auth_mode); setKey(""); setAllowHttp(provider.allow_insecure_local); setOpen(true); }}>{t("models.manage")}</Button>
        <Dropdown trigger={["click"]} getPopupContainer={() => container ?? document.body} menu={{ items: [
          { key: "refresh", label: t("models.custom.refresh"), onClick: async () => { if (await controller.refreshModels(provider)) await onChanged(); } },
          { key: "models", label: t("models.custom.models"), onClick: () => { setModelFormOpen(false); setModelSearch(""); setEditingModels(provider.id); } },
          { type: "divider" },
          { key: "remove", danger: true, label: t("models.custom.remove"), onClick: () => setRemovingProvider(provider) },
        ] }}><Button type="text" icon={<EllipsisOutlined aria-hidden="true" />} aria-label={t("models.providerActions", { provider: provider.name })} disabled={controller.saving} onClick={(event) => { menuOpener.current = event.currentTarget; }} /></Dropdown>
      </div>
      {editingModels === provider.id ? <Modal open title={`${t(modelFormOpen ? (editingModelKey ? "models.custom.edit" : "models.custom.addModel") : "models.custom.models")} · ${provider.name}`} width={720} footer={null} getContainer={container ?? undefined} onCancel={() => { if (!controller.saving) { if (modelFormOpen) setModelFormOpen(false); else setEditingModels(null); } }} mask={{ closable: !controller.saving }} keyboard={!controller.saving} afterClose={() => menuOpener.current?.focus()}>
        <div className="settings-custom-model-editor">
        {controller.error ? <Alert type="error" title={customProviderErrorText(controller.error, t)} /> : null}
        {!modelFormOpen ? <>
        <div className="custom-model-toolbar"><Input.Search allowClear aria-label={t("models.custom.search")} placeholder={t("models.custom.search")} value={modelSearch} onChange={(event) => setModelSearch(event.target.value)} /><Button type="primary" disabled={controller.saving} onClick={() => { setEditingModelKey(null); setModelId(""); setModelName(""); setContextLimit(8192); setOutputLimit(2048); setTools(false); setModelFormOpen(true); }}>{t("models.custom.addModel")}</Button></div>
        <div className="custom-model-list">
        {!provider.models.some((model) => `${model.name} ${model.model_id}`.normalize("NFC").toLowerCase().includes(modelSearch.trim().normalize("NFC").toLowerCase())) ? <p role="status">{t("models.custom.noResults")}</p> : null}
        {provider.models.filter((model) => `${model.name} ${model.model_id}`.normalize("NFC").toLowerCase().includes(modelSearch.trim().normalize("NFC").toLowerCase())).map((model) => <div className="custom-model-row" key={model.key}><div><strong>{model.name}</strong><div className="custom-model-id">{model.model_id}</div><small>{t("models.custom.context")}: {model.context_limit.toLocaleString()} · {t("models.custom.output")}: {model.output_limit.toLocaleString()}</small><div className="custom-model-source">{t(model.source === "manual" ? "models.custom.manualCapacity" : "models.custom.fallbackCapacity")}</div></div>
          <div className="custom-model-actions"><Button disabled={controller.saving} onClick={() => { setModelFormOpen(true); setEditingModelKey(model.key); setModelId(model.model_id); setModelName(model.name); setContextLimit(model.context_limit); setOutputLimit(model.output_limit); setTools(model.tools); }}>{t("models.custom.edit")}</Button>
          <Popconfirm title={t("models.custom.removeConfirm")} getPopupContainer={() => container ?? document.body} onConfirm={async () => { if (await controller.removeModel(provider, model.key)) { setEditingModelKey(null); setModelId(""); setModelName(""); await onChanged(); } }}>
            <Button danger disabled={controller.saving}>{t("models.custom.remove")}</Button>
          </Popconfirm></div></div>)}
        </div></> : <>
        <Alert type="info" title={t("models.custom.capacityHelp")} />
        <Form layout="vertical" onFinish={async () => {
          const draft = { modelId, name: modelName.trim() || modelId, contextLimit, outputLimit, tools };
          const saved = editingModelKey ? await controller.editModel(provider, editingModelKey, draft) : await controller.addModel(provider, draft);
          if (saved) { setModelFormOpen(false); setEditingModelKey(null); setModelId(""); setModelName(""); await onChanged(); }
        }}>
          <Form.Item label="Model ID" htmlFor={`${formId}-model-id`}><Input id={`${formId}-model-id`} value={modelId} onChange={(event) => setModelId(event.target.value)} disabled={controller.saving} /></Form.Item>
          <Form.Item label={t("models.custom.name")} htmlFor={`${formId}-model-name`}><Input id={`${formId}-model-name`} value={modelName} onChange={(event) => setModelName(event.target.value)} disabled={controller.saving} /></Form.Item>
          <div className="custom-model-capacities"><Form.Item label={t("models.custom.context")} htmlFor={`${formId}-context`}><InputNumber id={`${formId}-context`} min={1024} max={4000000} precision={0} value={contextLimit} onChange={(value) => value !== null && setContextLimit(value)} disabled={controller.saving} /></Form.Item>
          <Form.Item label={t("models.custom.output")} htmlFor={`${formId}-output`}><InputNumber id={`${formId}-output`} min={1} max={contextLimit} value={outputLimit} onChange={(value) => value !== null && setOutputLimit(value)} disabled={controller.saving} /></Form.Item>
          </div><Form.Item><Checkbox checked={tools} onChange={(event) => setTools(event.target.checked)} disabled={controller.saving}>{t("models.custom.tools")}</Checkbox></Form.Item>
          <div className="custom-model-actions"><Button disabled={controller.saving} onClick={() => setModelFormOpen(false)}>{t("common.cancel")}</Button><Button type="primary" htmlType="submit" loading={controller.saving} disabled={!modelId.trim() || outputLimit > contextLimit}>{t("common.save")}</Button></div>
        </Form>
        </>}
      </div></Modal> : null}
    </section>)}
    <section className="settings-service-card" aria-label={t("models.providerConnection", { provider: t("models.custom.entry") })}>
      <div className="settings-service-identity"><ApiOutlined className="settings-icon" aria-hidden="true" /><span><strong>{t("models.custom.entry")}</strong><small>{t("models.custom.entryDescription")}</small></span></div>
      <div className="settings-service-actions"><button type="button" className="settings-secondary-button" disabled={controller.saving} onClick={() => { setEditingProvider(null); setName(""); setUrl(""); setKey(""); setAuth("bearer"); setAllowHttp(false); setOpen(true); void controller.reload(); }}>{t("models.connect")}</button></div>
    </section>
    <Modal open={removingProvider !== null} afterClose={() => menuOpener.current?.focus()} getContainer={container ?? false} title={t("models.custom.removeConfirm")} okText={t("common.remove")} cancelText={t("common.cancel")} confirmLoading={controller.saving} okButtonProps={{ danger: true }} onCancel={() => { if (!controller.saving) setRemovingProvider(null); }} onOk={async () => { if (removingProvider && await controller.remove(removingProvider)) { setRemovingProvider(null); await onChanged(); } }}>
      <p>{removingProvider?.name}</p>
      {controller.error ? <Alert type="error" title={customProviderErrorText(controller.error, t)} /> : null}
    </Modal>
    {screens.sm === false ? <Drawer open={open} title={t(editingProvider ? "models.custom.edit" : "models.custom.add")} size="100%" onClose={close} getContainer={container ?? undefined}>{content}</Drawer>
      : <Modal open={open} title={t(editingProvider ? "models.custom.edit" : "models.custom.add")} onCancel={close} footer={null} mask={{ closable: !controller.saving }} keyboard={!controller.saving} getContainer={container ?? undefined}>{content}</Modal>}
  </>;
}
