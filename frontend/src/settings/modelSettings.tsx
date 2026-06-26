import { Button, Form, Input, Select, Switch, Tag } from "antd";
import {
  mediaModelCategories,
  mediaModelsForProvider,
  modelOptionsForProvider,
  providerMark,
  textModelOptionLabel,
} from "./providerHelpers";
import { SettingsCard, SettingsRow, SettingsSectionTitle, SettingsStatus } from "./settingsPrimitives";

type AnyRecord = Record<string, any>;
type ValueRef<T> = { value: T };

type ModelSettingsClient = {
  copy: ValueRef<AnyRecord>;
  settingsState: AnyRecord;
  selectModel: (providerId: string, model: string, reasoning?: string) => void;
  saveMediaModel: (category: string, model?: string) => void;
};

export function ModelSettings({ client }: { client: ModelSettingsClient }) {
  const copy = client.copy.value;
  const state = client.settingsState;
  const modelCopy = copy.settings.models || {};
  const providers = state.models?.providers || [];
  const selectedProvider = providers.find((provider: AnyRecord) => provider.id === state.selectedTextProviderId) || providers[0] || null;
  const selectedProviderId = selectedProvider?.id || "";
  const selectedModel = selectedProvider ? state.modelSelections[selectedProvider.id] || selectedProvider.selected_model || "" : "";
  const selectedReasoning = selectedProvider ? state.reasoningSelections[selectedProvider.id] || selectedProvider.reasoning_effort || "" : "";

  return (
    <section className="settings-page">
      <SettingsStatus message={state.modelsLoading ? modelCopy.loading || "Loading models..." : ""} />
      <SettingsStatus message={state.modelsNotice} />
      <SettingsStatus message={state.modelsError} type="error" />
      <SettingsStatus message={state.mediaError} type="error" />

      <SettingsSectionTitle>{modelCopy.textTitle || "Text model"}</SettingsSectionTitle>
      {providers.length === 0 ? (
        <SettingsCard>
          <SettingsRow title={modelCopy.noProvidersTitle || "No providers"} description={modelCopy.noProvidersDescription || ""}>
            <Tag>{modelCopy.noProvidersBadge || ""}</Tag>
          </SettingsRow>
        </SettingsCard>
      ) : null}

      {selectedProvider ? (
        <SettingsCard className="model-provider-card">
          <div className="model-provider-card__header">
            <div className="provider-row__main">
              <span className="provider-row__mark" aria-hidden="true">{providerMark(selectedProvider)}</span>
              <div>
                <div className="provider-row__title">
                  <strong>{selectedProvider.name || selectedProvider.id}</strong>
                  {selectedProvider.is_default ? <Tag className="provider-row__badge">{modelCopy.currentBadge || "Current"}</Tag> : null}
                </div>
                <span>{selectedProvider.selected_model || modelCopy.noModel || "No model selected"}</span>
              </div>
            </div>
          </div>

          <div className="model-select-row">
            <Form.Item className="ant-field-label" label={modelCopy.providerChoice || "Provider"}>
              <Select
                value={selectedProviderId}
                disabled={state.modelsLoading}
                options={providers.map((provider: AnyRecord) => ({
                  value: provider.id,
                  label: `${provider.name || provider.id}${provider.is_default ? ` (${modelCopy.active || "active"})` : ""}`,
                }))}
                onChange={(value) => {
                  state.selectedTextProviderId = value;
                  state.modelSelections[value] = "";
                }}
              />
            </Form.Item>
            <Form.Item className="ant-field-label" label={modelCopy.modelChoice || "Model"}>
              <Select
                value={selectedModel}
                disabled={state.modelsLoading}
                options={[
                  { value: "", label: modelCopy.noModel || "No model" },
                  ...modelOptionsForProvider(selectedProvider, selectedModel).map((model: string) => ({
                    value: model,
                    label: textModelOptionLabel(copy, selectedProvider, model),
                  })),
                ]}
                onChange={(value) => (state.modelSelections[selectedProvider.id] = value)}
              />
            </Form.Item>
            <Form.Item className="ant-field-label" label={modelCopy.reasoningChoice || "Reasoning"}>
              <Select
                value={selectedReasoning}
                disabled={state.modelsLoading}
                options={[
                  { value: "", label: modelCopy.reasoningDefault || "Default" },
                  { value: "none", label: modelCopy.reasoningNone || "None" },
                  { value: "minimal", label: modelCopy.reasoningMinimal || "Minimal" },
                  { value: "low", label: modelCopy.reasoningLow || "Low" },
                  { value: "medium", label: modelCopy.reasoningMedium || "Medium" },
                  { value: "high", label: modelCopy.reasoningHigh || "High" },
                  { value: "xhigh", label: modelCopy.reasoningXhigh || "XHigh" },
                ]}
                onChange={(value) => (state.reasoningSelections[selectedProvider.id] = value)}
              />
            </Form.Item>
            <Button type="primary" disabled={state.modelsLoading || !selectedModel} loading={state.modelsLoading} onClick={() => client.selectModel(selectedProvider.id, selectedModel, selectedReasoning)}>
              {modelCopy.select || modelCopy.apply || "Apply"}
            </Button>
          </div>

          <div className="custom-model-row">
            <Form.Item className="ant-field-label" label={modelCopy.customModel || "Custom model"}>
              <Input value={state.customModels[selectedProvider.id] || ""} placeholder={modelCopy.customPlaceholder || ""} spellCheck={false} onChange={(event) => (state.customModels[selectedProvider.id] = event.target.value)} />
            </Form.Item>
            <Button disabled={state.modelsLoading || !state.customModels[selectedProvider.id]} onClick={() => client.selectModel(selectedProvider.id, state.customModels[selectedProvider.id], selectedReasoning)}>
              {modelCopy.useCustom || "Use custom"}
            </Button>
          </div>
        </SettingsCard>
      ) : null}

      <SettingsSectionTitle>{modelCopy.mediaTitle || "Media models"}</SettingsSectionTitle>
      {(state.media.providers || []).length === 0 ? (
        <SettingsCard>
          <SettingsRow title={modelCopy.noProvidersTitle || "No providers"} description={modelCopy.mediaNoProvidersDescription || ""}>
            <Tag>{modelCopy.noProvidersBadge || ""}</Tag>
          </SettingsRow>
        </SettingsCard>
      ) : null}

      {mediaModelCategories(copy).map((category) => {
        const selection = state.mediaSelections[category.key] || {};
        const providerModels = mediaModelsForProvider(state, category.key, selection.providerId, selection.model);
        return (
          <SettingsCard key={category.key} className="model-provider-card">
            <div className="model-provider-card__header">
              <div className="provider-row__main">
                <span className="provider-row__mark" aria-hidden="true">{category.mark}</span>
                <div>
                  <div className="provider-row__title">
                    <strong>{category.title}</strong>
                    {state.media.sections?.[category.key]?.enabled ? <Tag className="provider-row__badge">{modelCopy.enabledBadge || "Enabled"}</Tag> : null}
                  </div>
                  <span>{state.media.sections?.[category.key]?.model || modelCopy.noModel || "No model"}</span>
                </div>
              </div>
            </div>
            <SettingsRow title={modelCopy.enableMediaModel || "Enable media model"} description={category.description}>
              <Switch
                aria-label={modelCopy.enableMediaModel || "Enable media model"}
                checked={Boolean(selection.enabled)}
                onChange={(checkedValue) => {
                  selection.enabled = checkedValue;
                  if (selection.enabled && !selection.providerId) {
                    selection.providerId = state.media.providers?.[0]?.id || "";
                  }
                  if (selection.enabled) {
                    selection.model = "";
                  }
                }}
              />
            </SettingsRow>
            <div className="model-select-row">
              {selection.enabled ? (
                <Form.Item className="ant-field-label" label={modelCopy.providerChoice || "Provider"}>
                  <Select
                    value={selection.providerId || ""}
                    disabled={state.mediaLoading}
                    options={(state.media.providers || []).map((provider: AnyRecord) => ({
                      value: provider.id,
                      label: provider.name || provider.id,
                    }))}
                    onChange={(value) => {
                      selection.providerId = value;
                      selection.model = "";
                    }}
                  />
                </Form.Item>
              ) : null}
              {selection.enabled ? (
                <Form.Item className="ant-field-label" label={modelCopy.modelChoice || "Model"}>
                  <Select
                    value={selection.model || ""}
                    disabled={state.mediaLoading}
                    options={providerModels.map((model: string) => ({ value: model, label: model }))}
                    onChange={(value) => (selection.model = value)}
                  />
                </Form.Item>
              ) : null}
              <Button disabled={state.mediaLoading || (selection.enabled && !selection.providerId)} loading={state.mediaLoading} onClick={() => client.saveMediaModel(category.key)}>
                {modelCopy.saveMediaModel || modelCopy.apply || "Save"}
              </Button>
            </div>
            {selection.enabled ? (
              <div className="custom-model-row">
                <Form.Item className="ant-field-label" label={modelCopy.customModel || "Custom model"}>
                  <Input value={state.mediaCustomModels[category.key] || ""} placeholder={modelCopy.customPlaceholder || ""} disabled={state.mediaLoading} spellCheck={false} onChange={(event) => (state.mediaCustomModels[category.key] = event.target.value)} />
                </Form.Item>
                <Button disabled={state.mediaLoading || !state.mediaCustomModels[category.key]} onClick={() => client.saveMediaModel(category.key, state.mediaCustomModels[category.key])}>
                  {modelCopy.useCustom || "Use custom"}
                </Button>
              </div>
            ) : null}
          </SettingsCard>
        );
      })}
    </section>
  );
}
