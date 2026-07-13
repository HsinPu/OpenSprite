import { ArrowLeftOutlined, CloseOutlined } from "@ant-design/icons";
import { Button, Form, Input } from "antd";
import { providerMark, type ProviderLike } from "./providerHelpers";
import type { ProviderConnectForm } from "../composables/providerConnectForm";

type ProviderConnectProviderView = ProviderLike & {
  api_key_optional?: unknown;
  default_base_url?: unknown;
  requires_api_key?: unknown;
};
type ProviderConnectCopyView = {
  advancedHide?: unknown;
  advancedShow?: unknown;
  apiKeyLabel?: unknown;
  backAria?: unknown;
  closeAria?: unknown;
  dialogDescription?: unknown;
  dialogTitle?: unknown;
  loading?: unknown;
  nameLabel?: unknown;
  submit?: unknown;
};
type ProviderConnectStateView = {
  connectForm: ProviderConnectForm;
  providersLoading: boolean;
};

function text(value: unknown, fallback = ""): string {
  return String(value || fallback);
}

function formatCopy(copyValue: unknown, providerName: string, fallback = ""): string {
  return typeof copyValue === "function" ? String(copyValue(providerName)) : text(copyValue, fallback);
}

export function ProviderConnectDialog({
  provider,
  state,
  providerCopy,
  onCancel,
  onSave,
}: {
  provider: ProviderConnectProviderView;
  state: ProviderConnectStateView;
  providerCopy: ProviderConnectCopyView;
  onCancel: () => void;
  onSave: () => void;
}) {
  const requiresApiKey = provider.requires_api_key !== false || provider.api_key_optional === true;
  const providerName = text(provider.name, text(provider.id));
  const form = state.connectForm;

  return (
    <div className="provider-connect-dialog" role="dialog" aria-modal="true">
      <header className="provider-connect-dialog__top">
        <Button type="text" aria-label={text(providerCopy.backAria, "Back")} icon={<ArrowLeftOutlined />} onClick={onCancel} />
        <Button type="text" aria-label={text(providerCopy.closeAria, "Close")} icon={<CloseOutlined />} onClick={onCancel} />
      </header>
      <Form className="provider-connect-dialog__body" layout="vertical" onFinish={() => onSave()}>
        <div className="provider-connect-dialog__title">
          <span className="provider-row__mark" aria-hidden="true">{providerMark(provider)}</span>
          <h3>{formatCopy(providerCopy.dialogTitle, providerName, `Connect ${providerName}`)}</h3>
        </div>
        <p>{formatCopy(providerCopy.dialogDescription, providerName)}</p>
        <Form.Item className="provider-connect-field" label={text(providerCopy.nameLabel, "Name")}>
          <Input value={form.name} placeholder={providerName} autoComplete="off" onChange={(event) => (form.name = event.target.value)} />
        </Form.Item>
        {requiresApiKey ? (
          <Form.Item className="provider-connect-field" label={formatCopy(providerCopy.apiKeyLabel, providerName, "API key")}>
            <Input.Password value={form.apiKey} placeholder="API key" autoComplete="off" onChange={(event) => (form.apiKey = event.target.value)} />
          </Form.Item>
        ) : null}
        <Button type="link" className="provider-connect-dialog__advanced" onClick={() => (form.showAdvanced = !form.showAdvanced)}>
          {form.showAdvanced ? text(providerCopy.advancedHide, "Hide advanced") : text(providerCopy.advancedShow, "Advanced")}
        </Button>
        {form.showAdvanced ? (
          <Form.Item className="provider-connect-field" label="Base URL">
            <Input value={form.baseUrl} spellCheck={false} onChange={(event) => (form.baseUrl = event.target.value)} />
          </Form.Item>
        ) : null}
        <Button className="provider-connect-dialog__submit" type="primary" htmlType="submit" loading={state.providersLoading} disabled={state.providersLoading}>
          {text(providerCopy.submit, "Save")}
        </Button>
      </Form>
    </div>
  );
}
