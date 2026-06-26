import { ArrowLeftOutlined, CloseOutlined } from "@ant-design/icons";
import { Button, Form, Input } from "antd";
import { providerMark } from "./providerHelpers";

type AnyRecord = Record<string, any>;

export function ProviderConnectDialog({
  provider,
  state,
  providerCopy,
  onCancel,
  onSave,
}: {
  provider: AnyRecord;
  state: AnyRecord;
  providerCopy: AnyRecord;
  onCancel: () => void;
  onSave: () => void;
}) {
  const requiresApiKey = provider.requires_api_key !== false || provider.api_key_optional === true;

  return (
    <div className="provider-connect-dialog" role="dialog" aria-modal="true">
      <header className="provider-connect-dialog__top">
        <Button type="text" aria-label={providerCopy.backAria || "Back"} icon={<ArrowLeftOutlined />} onClick={onCancel} />
        <Button type="text" aria-label={providerCopy.closeAria || "Close"} icon={<CloseOutlined />} onClick={onCancel} />
      </header>
      <Form className="provider-connect-dialog__body" layout="vertical" onFinish={() => onSave()}>
        <div className="provider-connect-dialog__title">
          <span className="provider-row__mark" aria-hidden="true">{providerMark(provider)}</span>
          <h3>{typeof providerCopy.dialogTitle === "function" ? providerCopy.dialogTitle(provider.name) : `Connect ${provider.name}`}</h3>
        </div>
        <p>{typeof providerCopy.dialogDescription === "function" ? providerCopy.dialogDescription(provider.name) : ""}</p>
        <Form.Item className="provider-connect-field" label={providerCopy.nameLabel || "Name"}>
          <Input value={state.connectForm.name} placeholder={provider.name} autoComplete="off" onChange={(event) => (state.connectForm.name = event.target.value)} />
        </Form.Item>
        {requiresApiKey ? (
          <Form.Item className="provider-connect-field" label={typeof providerCopy.apiKeyLabel === "function" ? providerCopy.apiKeyLabel(provider.name) : "API key"}>
            <Input.Password value={state.connectForm.apiKey} placeholder="API key" autoComplete="off" onChange={(event) => (state.connectForm.apiKey = event.target.value)} />
          </Form.Item>
        ) : null}
        <Button type="link" className="provider-connect-dialog__advanced" onClick={() => (state.connectForm.showAdvanced = !state.connectForm.showAdvanced)}>
          {state.connectForm.showAdvanced ? providerCopy.advancedHide || "Hide advanced" : providerCopy.advancedShow || "Advanced"}
        </Button>
        {state.connectForm.showAdvanced ? (
          <Form.Item className="provider-connect-field" label="Base URL">
            <Input value={state.connectForm.baseUrl} spellCheck={false} onChange={(event) => (state.connectForm.baseUrl = event.target.value)} />
          </Form.Item>
        ) : null}
        <Button className="provider-connect-dialog__submit" type="primary" htmlType="submit" loading={state.providersLoading} disabled={state.providersLoading}>
          {providerCopy.submit || "Save"}
        </Button>
      </Form>
    </div>
  );
}
