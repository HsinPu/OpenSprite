import { useEffect, useId, useState } from "react";
import { Alert, Button, Checkbox, Drawer, Form, Grid, Input, InputNumber, Modal, Popconfirm, Radio } from "antd";
import { PlusOutlined } from "@ant-design/icons";
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
  const [editingModelKey, setEditingModelKey] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [auth, setAuth] = useState<"none" | "bearer">("bearer");
  const [key, setKey] = useState("");
  const [allowHttp, setAllowHttp] = useState(false);
  const [editingModels, setEditingModels] = useState<string | null>(null);
  const [modelId, setModelId] = useState("");
  const [modelName, setModelName] = useState("");
  const [contextLimit, setContextLimit] = useState(8192);
  const [outputLimit, setOutputLimit] = useState(2048);
  const [tools, setTools] = useState(false);
  useEffect(() => {
    if (!open) return;
    onOverlayChange?.(true);
    return () => onOverlayChange?.(false);
  }, [open, onOverlayChange]);
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
    <Button icon={<PlusOutlined />} onClick={() => { setEditingProvider(null); setName(""); setUrl(""); setKey(""); setAuth("bearer"); setAllowHttp(false); setOpen(true); void controller.reload(); }}>{t("models.custom.add")}</Button>
    {!open && controller.error ? <Alert type="error" title={customProviderErrorText(controller.error, t)} action={<Button onClick={() => void controller.reload()}>{t("common.retry")}</Button>} /> : null}
    {controller.catalog?.providers.map((provider) => <section key={provider.id} className="settings-service-card">
      <div><strong>{provider.name}</strong><p>{provider.base_url}</p><small>{provider.models.length} {t("models.custom.models")}</small></div>
      <div><Button disabled={controller.saving} onClick={async () => { if (await controller.refreshModels(provider)) await onChanged(); }}>{t("models.custom.refresh")}</Button>
        <Button disabled={controller.saving} onClick={() => { setEditingModelKey(null); setModelId(""); setModelName(""); setContextLimit(8192); setOutputLimit(2048); setTools(false); setEditingModels(editingModels === provider.id ? null : provider.id); }}>{t("models.custom.models")}</Button>
        <Button disabled={controller.saving} onClick={() => { setEditingProvider(provider); setName(provider.name); setUrl(provider.base_url); setAuth(provider.auth_mode); setKey(""); setAllowHttp(provider.allow_insecure_local); setOpen(true); }}>{t("models.custom.edit")}</Button>
        <Popconfirm title={t("models.custom.removeConfirm")} onConfirm={async () => { if (await controller.remove(provider)) await onChanged(); }} getPopupContainer={() => container ?? document.body}>
          <Button danger disabled={controller.saving}>{t("models.custom.remove")}</Button>
        </Popconfirm></div>
      {editingModels === provider.id ? <div style={{ width: "100%", minWidth: 0 }}>
        {provider.models.map((model) => <div key={model.key}><p>{model.name} · {model.model_id} · {model.context_limit} / {model.output_limit}</p>
          <Button disabled={controller.saving} onClick={() => { setEditingModelKey(model.key); setModelId(model.model_id); setModelName(model.name); setContextLimit(model.context_limit); setOutputLimit(model.output_limit); setTools(model.tools); }}>{t("models.custom.edit")}</Button>
          <Popconfirm title={t("models.custom.removeConfirm")} getPopupContainer={() => container ?? document.body} onConfirm={async () => { if (await controller.removeModel(provider, model.key)) { setEditingModelKey(null); setModelId(""); setModelName(""); await onChanged(); } }}>
            <Button danger disabled={controller.saving}>{t("models.custom.remove")}</Button>
          </Popconfirm></div>)}
        <Form layout="vertical" onFinish={async () => {
          const draft = { modelId, name: modelName.trim() || modelId, contextLimit, outputLimit, tools };
          const saved = editingModelKey ? await controller.editModel(provider, editingModelKey, draft) : await controller.addModel(provider, draft);
          if (saved) { setEditingModelKey(null); setModelId(""); setModelName(""); await onChanged(); }
        }}>
          <Form.Item label="Model ID" htmlFor={`${formId}-model-id`}><Input id={`${formId}-model-id`} value={modelId} onChange={(event) => setModelId(event.target.value)} disabled={controller.saving} /></Form.Item>
          <Form.Item label={t("models.custom.name")} htmlFor={`${formId}-model-name`}><Input id={`${formId}-model-name`} value={modelName} onChange={(event) => setModelName(event.target.value)} disabled={controller.saving} /></Form.Item>
          <Form.Item label={t("models.custom.context")} htmlFor={`${formId}-context`}><InputNumber id={`${formId}-context`} min={1024} value={contextLimit} onChange={(value) => value !== null && setContextLimit(value)} disabled={controller.saving} /></Form.Item>
          <Form.Item label={t("models.custom.output")} htmlFor={`${formId}-output`}><InputNumber id={`${formId}-output`} min={1} max={contextLimit} value={outputLimit} onChange={(value) => value !== null && setOutputLimit(value)} disabled={controller.saving} /></Form.Item>
          <Form.Item><Checkbox checked={tools} onChange={(event) => setTools(event.target.checked)} disabled={controller.saving}>{t("models.custom.tools")}</Checkbox></Form.Item>
          <Button htmlType="submit" loading={controller.saving} disabled={!modelId.trim() || outputLimit > contextLimit}>{t("common.save")}</Button>
        </Form>
      </div> : null}
    </section>)}
    {screens.sm === false ? <Drawer open={open} title={t(editingProvider ? "models.custom.edit" : "models.custom.add")} size="100%" onClose={close} getContainer={container ?? undefined}>{content}</Drawer>
      : <Modal open={open} title={t(editingProvider ? "models.custom.edit" : "models.custom.add")} onCancel={close} footer={null} mask={{ closable: !controller.saving }} keyboard={!controller.saving} getContainer={container ?? undefined}>{content}</Modal>}
  </>;
}
