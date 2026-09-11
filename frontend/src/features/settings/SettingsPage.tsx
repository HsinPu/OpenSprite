import { Button, Collapse, Drawer, Dropdown, Input, Modal, Select, Switch, Tooltip } from "antd";
import { ArrowLeftOutlined, EllipsisOutlined, MenuOutlined, ReloadOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";

import {
  deleteProviderConnection,
  providerErrorText,
  testProviderConnection,
  replaceProviderConnection,
  type ProviderId,
  type ProviderStatus,
  type ProviderSummary,
} from "../../api/providerConnections";
import type { ContextBudget, OutputBudget, OutputContinuation, ResponseDelivery, ResponseMode } from "../../api/aiSettings";
import type { MessageKey } from "../../i18n/catalog";
import { useI18n } from "../../i18n/I18nProvider";
import { localModelCatalog, type ModelSelection } from "../ai-settings/modelCatalog";
import { contextBudgetAvailable, contextBudgetLimit, contextBudgetValues, formatTokenLimit } from "../ai-settings/contextBudget";
import { outputBudgetAvailable, outputBudgetLimit, outputBudgetValues } from "../ai-settings/outputBudget";
import type { ProviderCatalogController } from "../ai-settings/useProviderCatalog";
import type { GeneralSettingsController } from "../general-settings/useGeneralSettings";
import type { ConversationSettingsController } from "../conversation-settings/useConversationSettings";
import type { ToolSettingsController } from "../tool-settings/useToolSettings";
import type { McpConnectionsController } from "../mcp-settings/useMcpConnections";
import { GeneralSettings } from "./GeneralSettings";
import { AboutSettings } from "./AboutSettings";
import { ToolsSettings } from "./ToolsSettings";
import { PrivacySettings } from "./PrivacySettings";
import { SchedulePage } from "../schedules/SchedulePage";
import { WorkspacesSettings } from "./WorkspacesSettings";
import type { WorkspaceController } from "../workspaces/useWorkspaces";
import { useAuthentication } from "../auth/AuthGate";
import { FutureSettingRow, Icon, SaveStatus, SettingsCard, type IconName } from "./SettingsPrimitives";
import type { SettingsSection } from "./settingsState";
import "./settings.css";
import { SkillsSettings } from "./SkillsSettings";
import { AgentsSettings } from "./AgentsSettings";
import { CustomProviderCreate } from "./CustomProviderCreate";

type SettingsPageProps = {
  section: SettingsSection;
  active: boolean;
  onSectionChange: (section: SettingsSection) => void;
  modelSelection: ModelSelection | null;
  responseMode: ResponseMode;
  outputContinuation: OutputContinuation;
  responseDelivery: ResponseDelivery;
  logFullPrompts: boolean;
  aiSettingsLoaded: boolean;
  aiSettingsSaving: boolean;
  aiSettingsError: string | null;
  onAiSettingsReload: () => Promise<void>;
  onModelSelectionChange: (selection: ModelSelection | null) => Promise<string | null>;
  onResponseModeChange: (responseMode: ResponseMode) => Promise<string | null>;
  onOutputContinuationChange: (policy: OutputContinuation) => Promise<string | null>;
  onResponseDeliveryChange: (delivery: ResponseDelivery) => Promise<string | null>;
  onLogFullPromptsChange: (enabled: boolean) => Promise<string | null>;
  providerCatalog: ProviderCatalogController;
  generalSettings: GeneralSettingsController;
  conversationSettings: ConversationSettingsController;
  toolSettings: ToolSettingsController;
  mcpConnections: McpConnectionsController;
  workspaces: WorkspaceController;
  onWorkspaceActivated: (workspaceId: string) => void;
  workspaceCreateRequest: number;
  onWorkspaceCreateRequestHandled: () => void;
  onWorkspaceOverlayChange?: (open: boolean) => void;
  onOpenScheduleConversation: (conversationId: string) => void;
  onClose: () => void;
  onProviderModalChange?: (open: boolean) => void;
  onScheduleOverlayChange?: (open: boolean) => void;
};

const categories: Array<{ id: SettingsSection | "memory" | "tools" | "appearance" | "privacy" | "about"; labelKey: MessageKey; icon: IconName; enabled?: boolean }> = [
  { id: "general", labelKey: "settings.category.general", icon: "settings", enabled: true },
  { id: "workspaces", labelKey: "settings.category.workspaces", icon: "folder", enabled: true },
  { id: "models", labelKey: "settings.category.models", icon: "robot", enabled: true },
  { id: "memory", labelKey: "settings.category.memory", icon: "database" },
  { id: "tools", labelKey: "settings.category.tools", icon: "connections", enabled: true },
  { id: "skills", labelKey: "settings.category.skills", icon: "folder", enabled: true },
  { id: "agents", labelKey: "settings.category.agents", icon: "robot", enabled: true },
  { id: "schedules", labelKey: "settings.category.schedules", icon: "schedules", enabled: true },
  { id: "appearance", labelKey: "settings.category.appearance", icon: "appearance" },
  { id: "privacy", labelKey: "settings.category.privacy", icon: "privacy", enabled: true },
  { id: "about", labelKey: "settings.category.about", icon: "info", enabled: true },
];

const providerStatusKeys: Record<ProviderStatus, MessageKey> = {
  disconnected: "models.status.disconnected", connected: "models.status.connected", invalid_credentials: "models.status.invalidCredentials", provider_unreachable: "models.status.unreachable",
  provider_timeout: "models.status.timeout", provider_rate_limited: "models.status.rateLimited", credential_store_unavailable: "models.status.storeUnavailable",
};

const contextBudgetLabelKeys: Record<ContextBudget, MessageKey> = {
  auto: "models.context.auto",
  "32k": "models.context.32k",
  "64k": "models.context.64k",
  "128k": "models.context.128k",
  "256k": "models.context.256k",
  max: "models.context.max",
};

const outputBudgetLabelKeys: Record<OutputBudget, MessageKey> = {
  auto: "models.output.auto",
  "8k": "models.output.8k",
  "16k": "models.output.16k",
  "32k": "models.output.32k",
  "64k": "models.output.64k",
  max: "models.output.max",
};

const outputContinuationLabelKeys: Record<OutputContinuation, MessageKey> = {
  off: "models.outputContinuation.off",
  "1": "models.outputContinuation.one",
  "2": "models.outputContinuation.two",
  "3": "models.outputContinuation.three",
  "5": "models.outputContinuation.five",
  "10": "models.outputContinuation.ten",
  "20": "models.outputContinuation.twenty",
  "50": "models.outputContinuation.fifty",
  unlimited: "models.outputContinuation.unlimited",
};
const outputContinuationValues: readonly OutputContinuation[] = ["off", "1", "2", "3", "5", "10", "20", "50", "unlimited"];
const responseDeliveryValues: readonly ResponseDelivery[] = ["stream", "complete"];
const responseDeliveryLabelKeys: Record<ResponseDelivery, MessageKey> = {
  stream: "models.responseDelivery.stream",
  complete: "models.responseDelivery.complete",
};
const responseDeliveryDescriptionKeys: Record<ResponseDelivery, MessageKey> = {
  stream: "models.responseDelivery.streamDescription",
  complete: "models.responseDelivery.completeDescription",
};

type ProviderFeedback = { message?: string; error?: string };
type ProviderOperation = Partial<Record<ProviderId, number>>;

type ModelsSettingsProps = {
  modelSelection: ModelSelection | null;
  responseMode: ResponseMode;
  outputContinuation: OutputContinuation;
  responseDelivery: ResponseDelivery;
  logFullPrompts: boolean;
  aiSettingsLoaded: boolean;
  aiSettingsSaving: boolean;
  aiSettingsError: string | null;
  onAiSettingsReload: () => Promise<void>;
  onModelSelectionChange: (selection: ModelSelection | null) => Promise<string | null>;
  onResponseModeChange: (responseMode: ResponseMode) => Promise<string | null>;
  onOutputContinuationChange: (policy: OutputContinuation) => Promise<string | null>;
  onResponseDeliveryChange: (delivery: ResponseDelivery) => Promise<string | null>;
  onLogFullPromptsChange: (enabled: boolean) => Promise<string | null>;
  providerCatalog: ProviderCatalogController;
  onProviderModalChange?: (open: boolean) => void;
  modalContainer: HTMLElement | null;
};

function ConnectionModal({ provider, container, onCancel, onSubmit }: { provider: ProviderSummary; container: HTMLElement; onCancel: () => void; onSubmit: (apiKey: string) => Promise<string | null> }) {
  const { t } = useI18n();
  const [apiKey, setApiKey] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submittingRef = useRef(false);
  const clearSecret = () => setApiKey("");

  useEffect(() => () => clearSecret(), []);

  const close = () => {
    clearSecret();
    setError(null);
    onCancel();
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submittingRef.current) return;
    if (!apiKey.trim()) {
      clearSecret();
      setError(t("models.keyRequired"));
      return;
    }

    submittingRef.current = true;
    setSubmitting(true);
    setError(null);
    const result = await onSubmit(apiKey);
    clearSecret();
    submittingRef.current = false;
    setSubmitting(false);
    if (result) setError(result);
  };

  return (
    <Modal
      className="provider-connection-modal"
      open
      title={t("models.keyTitle", { provider: provider.name })}
      footer={null}
      getContainer={() => container}
      onCancel={() => { if (!submittingRef.current) close(); }}
      keyboard={!submitting}
      destroyOnHidden
      mask={{ closable: !submitting }}
      closable={!submitting}
    >
      <form onSubmit={submit} onKeyDownCapture={(event) => { if (submitting && event.key === "Escape") event.stopPropagation(); }}>
        <p className="provider-modal-copy">{t("models.keyDescription")}</p>
        {provider.credentialPreview ? <p className="settings-helper-text">{provider.credentialPreview}</p> : null}
        <label className="provider-key-label" htmlFor="provider-api-key">{t("models.keyLabel")}</label>
        <Input.Password id="provider-api-key" name="apiKey" autoFocus autoComplete="new-password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} disabled={submitting} aria-invalid={Boolean(error)} aria-errormessage={error ? "provider-key-error" : undefined} />
        {error ? <p id="provider-key-error" className="provider-modal-error" role="alert">{error}</p> : null}
        <div className="provider-modal-actions">
          <button type="button" className="settings-secondary-button" onClick={close} disabled={submitting}>{t("common.cancel")}</button>
          <button type="submit" className="settings-outline-button" disabled={submitting}>{submitting ? t("models.validating") : t("models.validateSave")}</button>
        </div>
      </form>
    </Modal>
  );
}

function ModelsSettings({ modelSelection, responseMode, outputContinuation, responseDelivery, logFullPrompts, aiSettingsLoaded, aiSettingsSaving, aiSettingsError, onAiSettingsReload, onModelSelectionChange, onResponseModeChange, onOutputContinuationChange, onResponseDeliveryChange, onLogFullPromptsChange, providerCatalog, onProviderModalChange, modalContainer }: ModelsSettingsProps) {
  const { t } = useI18n();
  const {
    providers,
    catalogError,
    openRouterModels,
    openRouterModelLoadStatus,
    openRouterModelError,
    refreshProviders,
    readProviderSummary,
    updateProviderSummary,
    loadOpenRouterModels,
    invalidateOpenRouterModels,
  } = providerCatalog;
  const [operations, setOperations] = useState<ProviderOperation>({});
  const [feedback, setFeedback] = useState<Partial<Record<ProviderId, ProviderFeedback>>>({});
  const [modalProvider, setModalProvider] = useState<ProviderSummary | null>(null);
  const [removingProvider, setRemovingProvider] = useState<ProviderSummary | null>(null);
  const providerMenuOpener = useRef<HTMLElement | null>(null);
  const [selectionError, setSelectionError] = useState<string | null>(null);
  const generationsRef = useRef<Record<ProviderId, number>>({ openai: 0, anthropic: 0, openrouter: 0 });
  const activeOperationsRef = useRef<ProviderOperation>({});
  const reconciliationRef = useRef<string | null>(null);
  const outputReconciliationRef = useRef<string | null>(null);
  useEffect(() => { onProviderModalChange?.(modalProvider !== null || removingProvider !== null); }, [modalProvider, removingProvider, onProviderModalChange]);

  const beginOperation = (provider: ProviderSummary, action: string) => {
    if (activeOperationsRef.current[provider.id] !== undefined) return null;
    const generation = generationsRef.current[provider.id] + 1;
    generationsRef.current[provider.id] = generation;
    activeOperationsRef.current = { ...activeOperationsRef.current, [provider.id]: generation };
    setOperations(activeOperationsRef.current);
    setFeedback((current) => ({ ...current, [provider.id]: { message: t("models.operationProgress", { provider: provider.name, action }) } }));
    return generation;
  };
  const isCurrentOperation = (providerId: ProviderId, generation: number) => activeOperationsRef.current[providerId] === generation;
  const finishOperation = (providerId: ProviderId, generation: number) => {
    if (!isCurrentOperation(providerId, generation)) return;
    const { [providerId]: _, ...remaining } = activeOperationsRef.current;
    activeOperationsRef.current = remaining;
    setOperations(remaining);
  };
  const setProviderFeedback = (providerId: ProviderId, next: ProviderFeedback) => {
    setFeedback((current) => ({ ...current, [providerId]: next }));
  };
  const clearProviderFeedback = (providerId: ProviderId) => {
    setFeedback((current) => {
      const { [providerId]: _, ...remaining } = current;
      return remaining;
    });
  };
  const refreshFailedProvider = async (providerId: ProviderId, generation: number) => {
    const persistedSummary = await readProviderSummary(providerId);
    if (!isCurrentOperation(providerId, generation)) return;
    if (persistedSummary) updateProviderSummary(persistedSummary);
  };
  const testConnection = async (provider: ProviderSummary) => {
    const generation = beginOperation(provider, t("models.operationTesting"));
    if (generation === null) return;
    try {
      const summary = await testProviderConnection(provider.id);
      if (isCurrentOperation(provider.id, generation)) {
        updateProviderSummary(summary);
        setProviderFeedback(provider.id, { message: t("models.feedback", { provider: provider.name, message: t(providerStatusKeys[summary.status]) }) });
      }
    } catch (requestError) {
      if (isCurrentOperation(provider.id, generation)) {
        setProviderFeedback(provider.id, { error: t("models.feedback", { provider: provider.name, message: providerErrorText(requestError, t) }) });
        await refreshFailedProvider(provider.id, generation);
      }
    } finally {
      finishOperation(provider.id, generation);
    }
  };
  const disconnect = async (provider: ProviderSummary) => {
    const generation = beginOperation(provider, t("models.operationRemoving"));
    if (generation === null) return;
    try {
      await deleteProviderConnection(provider.id);
      if (isCurrentOperation(provider.id, generation)) {
        updateProviderSummary({ ...provider, connected: false, status: "disconnected", credentialPreview: null, lastCheckedAt: null });
        if (provider.id === "openrouter") invalidateOpenRouterModels();
        setProviderFeedback(provider.id, { message: t("models.disconnected", { provider: provider.name }) });
      }
    } catch (requestError) {
      if (isCurrentOperation(provider.id, generation)) setProviderFeedback(provider.id, { error: t("models.feedback", { provider: provider.name, message: providerErrorText(requestError, t) }) });
    } finally {
      finishOperation(provider.id, generation);
    }
  };
  const connect = async (provider: ProviderSummary, apiKey: string): Promise<string | null> => {
    const generation = beginOperation(provider, t("models.operationSaving"));
    if (generation === null) return t("models.operationBusy");
    try {
      const summary = await replaceProviderConnection(provider.id, apiKey);
      if (!isCurrentOperation(provider.id, generation)) return t("models.operationSuperseded");
      updateProviderSummary(summary);
      setProviderFeedback(provider.id, { message: t("models.connected", { provider: summary.name }) });
      if (summary.id === "openrouter") {
        invalidateOpenRouterModels();
        void loadOpenRouterModels(true);
      }
      setModalProvider((current) => current?.id === provider.id ? null : current);
      return null;
    } catch (requestError) {
      const message = providerErrorText(requestError, t);
      if (isCurrentOperation(provider.id, generation)) clearProviderFeedback(provider.id);
      return message;
    } finally {
      finishOperation(provider.id, generation);
    }
  };

  const modelsFor = useCallback((id: ProviderId) => localModelCatalog[id] ?? providerCatalog.modelChoices.filter((choice) => choice.selection.providerId === id).map((choice) => ({
    id: choice.selection.modelId, label: choice.label, contextWindowTokens: choice.contextWindowTokens ?? 8192, maxOutputTokens: choice.maxOutputTokens ?? 2048,
  })), [providerCatalog.modelChoices]);
  const connectedProviders = useMemo(() => providers?.filter((provider) => provider.connected || (!(provider.id in localModelCatalog) && modelsFor(provider.id).length > 0)) ?? [], [providers, modelsFor]);
  const selectedProvider = modelSelection
    ? connectedProviders.find((provider) => provider.id === modelSelection.providerId)
    : connectedProviders.length === 1 ? connectedProviders[0] : undefined;
  const selectedModels = selectedProvider
    ? selectedProvider.id === "openrouter" ? openRouterModels ?? [] : modelsFor(selectedProvider.id)
    : [];
  const selectedModelIsAvailable = modelSelection !== null && selectedModels.some((model) => model.id === modelSelection.modelId);
  const openRouterModelsPending = connectedProviders.some((provider) => provider.id === "openrouter") && openRouterModels === null && (openRouterModelLoadStatus === "idle" || openRouterModelLoadStatus === "loading");
  const requestSelection = useCallback(async (next: ModelSelection | null) => {
    setSelectionError(null);
    const error = await onModelSelectionChange(next);
    if (error) setSelectionError(error);
  }, [onModelSelectionChange]);

  useEffect(() => {
    if (!aiSettingsLoaded || providers === null || aiSettingsSaving) return;
    if (modelSelection && !["openai", "anthropic", "openrouter"].includes(modelSelection.providerId)) return;
    // Discovery is not permission to replace a user's persisted selection.
    // A missing model remains selected until the user explicitly chooses another.
    if (modelSelection !== null && selectedProvider?.id === "openrouter") return;
    if (modelSelection !== null && selectedProvider && selectedModelIsAvailable) { reconciliationRef.current = null; return; }
    const key = `${modelSelection?.providerId ?? "none"}:${modelSelection?.modelId ?? "none"}:${connectedProviders.map((provider) => `${provider.id}:${provider.connected}`).join(",")}:${openRouterModelLoadStatus}:${openRouterModels?.map((model) => model.id).join(",") ?? ""}`;
    if (reconciliationRef.current === key) return;
    reconciliationRef.current = key;
    const fallback = connectedProviders.map((provider) => ({ provider, models: provider.id === "openrouter" ? (openRouterModelLoadStatus === "success" ? openRouterModels ?? [] : []) : modelsFor(provider.id) })).find((candidate) => candidate.models.length > 0);
    const model = fallback?.models[0];
    if (fallback && model) void requestSelection({ providerId: fallback.provider.id, modelId: model.id, contextBudget: "auto", outputBudget: "auto" });
    else if (modelSelection !== null && connectedProviders.length === 0) void requestSelection(null);
  }, [aiSettingsLoaded, aiSettingsSaving, connectedProviders, modelSelection, openRouterModelLoadStatus, openRouterModels, providers, requestSelection, selectedModelIsAvailable, selectedProvider]);

  const getSettingsPopupContainer = () => modalContainer ?? document.body;
  const outputContinuationOptions = outputContinuationValues.map((value) => ({
    value,
    label: t(outputContinuationLabelKeys[value]),
  }));
  const outputContinuationDescription = outputContinuation === "off"
    ? t("models.outputContinuation.offDescription")
    : outputContinuation === "unlimited"
      ? t("models.outputContinuation.unlimitedDescription")
      : t("models.outputContinuation.limitedDescription", { count: outputContinuation });
  const providerOptions = connectedProviders.map((provider) => ({ value: provider.id, label: provider.name }));
  const modelOptions = selectedModels.map((model) => ({ value: model.id, label: <span className="settings-model-option"><strong>{model.label}</strong><small>{model.id}</small></span>, searchText: `${model.label} ${model.id}` }));
  const selectedModel = modelSelection ? selectedModels.find((model) => model.id === modelSelection.modelId) : undefined;
  const contextOptions = selectedModel ? contextBudgetValues.map((value) => ({
    value,
    label: t(contextBudgetLabelKeys[value]),
    disabled: !contextBudgetAvailable(value, selectedModel.contextWindowTokens),
  })) : [];
  const effectiveContextLimit = selectedModel && modelSelection
    ? contextBudgetLimit(modelSelection.contextBudget, selectedModel.contextWindowTokens)
    : null;
  const outputOptions = selectedModel && effectiveContextLimit !== null ? outputBudgetValues.map((value) => ({
    value,
    label: t(outputBudgetLabelKeys[value]),
    disabled: !outputBudgetAvailable(value, effectiveContextLimit, selectedModel.maxOutputTokens),
  })) : [];
  const effectiveOutputLimit = selectedModel && modelSelection && effectiveContextLimit !== null
    ? outputBudgetLimit(modelSelection.outputBudget, effectiveContextLimit, selectedModel.maxOutputTokens)
    : null;
  useEffect(() => {
    if (!aiSettingsLoaded || !modelSelection || !selectedModel || effectiveContextLimit === null || aiSettingsSaving) return;
    if (outputBudgetAvailable(modelSelection.outputBudget, effectiveContextLimit, selectedModel.maxOutputTokens)) {
      outputReconciliationRef.current = null;
      return;
    }
    const key = `${modelSelection.providerId}:${modelSelection.modelId}:${modelSelection.contextBudget}:${modelSelection.outputBudget}:${selectedModel.maxOutputTokens}`;
    if (outputReconciliationRef.current === key) return;
    outputReconciliationRef.current = key;
    void requestSelection({ ...modelSelection, outputBudget: "auto" });
  }, [aiSettingsLoaded, aiSettingsSaving, effectiveContextLimit, modelSelection, requestSelection, selectedModel]);
  const modelDisabled = !aiSettingsLoaded || !selectedProvider || (selectedProvider.id === "openrouter" && (openRouterModelsPending || selectedModels.length === 0));
  const openRouterConnected = connectedProviders.some((provider) => provider.id === "openrouter");
  const helperText = connectedProviders.length === 0
    ? t("models.helper.connect")
    : selectedProvider?.id === "openrouter" && openRouterModelsPending ? t("models.helper.loadingOpenRouter")
    : selectedProvider?.id === "openrouter" && selectedModels.length === 0 ? t("models.helper.emptyOpenRouter")
    : modelSelection ? t("models.helper.selected") : t("models.helper.select");

  const responseModes: ReadonlyArray<{ value: ResponseMode; label: string }> = [{ value: "default", label: t("models.response.default") }, { value: "fast", label: t("models.response.fast") }, { value: "balanced", label: t("models.response.balanced") }, { value: "deep", label: t("models.response.deep") }];
  const responseDeliveryOptions = responseDeliveryValues.map((value) => ({ value, label: t(responseDeliveryLabelKeys[value]) }));
  return (
    <div className="settings-form-stack settings-models-layout">
      <SettingsCard icon="connections" title={t("models.providers")}>
        <p className="settings-card-description">{t("models.providersDescription")}</p>
        {providers === null && !catalogError ? <p className="settings-provider-feedback" role="status" aria-live="polite">{t("models.loadingProviders")}</p> : null}
        {catalogError ? <div className="settings-provider-feedback settings-provider-feedback--error" role="alert"><p>{catalogError}</p><button type="button" className="settings-secondary-button" onClick={() => void refreshProviders()}>{t("common.retry")}</button></div> : null}
        {!aiSettingsLoaded && !aiSettingsError ? <p className="settings-provider-feedback" role="status">{t("models.loadingSettings")}</p> : null}
        {providers ? (
          <div className="settings-service-list">
            {providers.filter((provider) => ["openai", "anthropic", "openrouter"].includes(provider.id)).map((provider) => {
              const busy = operations[provider.id] !== undefined;
              const statusClass = provider.status === "connected" ? "settings-online" : "settings-offline";
              return (
                <div className="settings-service-card" key={provider.id} aria-label={t("models.providerConnection", { provider: provider.name })} aria-busy={busy}>
                  <div className="settings-service-identity"><Icon name={provider.id === "openai" || provider.id === "anthropic" || provider.id === "openrouter" ? provider.id : "robot"} /><span><strong>{provider.name}</strong><span className={statusClass}><i aria-hidden="true" />{t(providerStatusKeys[provider.status])}</span></span></div>
                  <div className="settings-service-actions" role="group" aria-label={t("models.providerActions", { provider: provider.name })} aria-busy={busy}>
                    <button type="button" className="settings-secondary-button" onClick={() => setModalProvider(provider)} disabled={busy}>{provider.connected ? t("models.manage") : t("models.connect")}</button>
                    {provider.connected ? <Dropdown trigger={["click"]} getPopupContainer={getSettingsPopupContainer} menu={{ items: [
                      { key: "test", label: t("models.testConnection"), onClick: () => void testConnection(provider) },
                      { type: "divider" },
                      { key: "remove", danger: true, label: t("models.removeConnection"), onClick: () => setRemovingProvider(provider) },
                    ] }}><Button type="text" aria-label={t("models.providerActions", { provider: provider.name })} icon={<EllipsisOutlined aria-hidden="true" />} disabled={busy} onClick={(event) => { providerMenuOpener.current = event.currentTarget; }} /></Dropdown> : null}
                  </div>
                  {feedback[provider.id] ? <p className={feedback[provider.id]?.error ? "settings-action-error settings-provider-row-feedback" : "settings-action-status settings-provider-row-feedback"} role={feedback[provider.id]?.error ? "alert" : "status"}>{feedback[provider.id]?.error ?? feedback[provider.id]?.message}</p> : null}
                </div>
              );
            })}
          </div>
        ) : null}
        <div className="settings-service-list"><CustomProviderCreate onChanged={refreshProviders} container={modalContainer} onOverlayChange={onProviderModalChange} hasCustomProviders={providers?.some((provider) => provider.id !== "openai" && provider.id !== "anthropic" && provider.id !== "openrouter") ?? false} /></div>
      </SettingsCard>
      <SettingsCard icon="robot" title={t("models.selectModel")}>
        <div className="settings-model-selection">
          <div className="settings-select-row"><label htmlFor="settings-model-provider">{t("models.provider")}</label><Select id="settings-model-provider" aria-describedby="settings-model-helper" value={selectedProvider?.id} placeholder={t("models.selectProvider")} options={providerOptions} getPopupContainer={getSettingsPopupContainer} disabled={!aiSettingsLoaded || providers === null || connectedProviders.length === 0 || aiSettingsSaving} onChange={(providerId) => { const provider = providerOptions.find((option) => option.value === providerId); const models = providerId === "openrouter" ? openRouterModels ?? [] : modelsFor(providerId as ProviderId); const model = models[0]; if (provider && model) void requestSelection({ providerId: providerId as ProviderId, modelId: model.id, contextBudget: "auto", outputBudget: "auto" }); }} /></div>
<div className="settings-select-row"><label htmlFor="settings-default-model">{t("models.model")}</label><div className="settings-model-picker"><Select id="settings-default-model" aria-describedby="settings-model-helper" showSearch value={selectedModelIsAvailable && modelSelection ? modelSelection.modelId : undefined} placeholder={selectedProvider ? t("models.selectModelPlaceholder") : t("models.connectProviderFirst")} options={modelOptions} getPopupContainer={getSettingsPopupContainer} filterOption={(input, option) => String((option as { searchText?: string } | undefined)?.searchText).toLowerCase().includes(input.toLowerCase())} disabled={modelDisabled || aiSettingsSaving} loading={openRouterModelsPending || aiSettingsSaving} notFoundContent={selectedProvider?.id === "openrouter" && !openRouterModelsPending ? t("models.noModels") : undefined} onChange={(modelId) => { if (selectedProvider) void requestSelection({ providerId: selectedProvider.id, modelId, contextBudget: "auto", outputBudget: "auto" }); }} />{selectedProvider?.id === "openrouter" ? <Tooltip title={t("models.refreshModels")} getPopupContainer={getSettingsPopupContainer}><Button className="settings-model-refresh" type="text" aria-label={t("models.refreshModels")} icon={<ReloadOutlined aria-hidden="true" />} loading={openRouterModelLoadStatus === "loading"} disabled={aiSettingsSaving || operations.openrouter !== undefined || openRouterModelLoadStatus === "loading"} onClick={() => void loadOpenRouterModels(true)} /></Tooltip> : null}</div></div>
          {openRouterConnected && openRouterModelLoadStatus === "error" ? <div className="settings-model-load-error" role="alert"><p>{openRouterModelError}</p><button type="button" className="settings-secondary-button settings-model-retry" onClick={() => void loadOpenRouterModels(true)}>{t("models.retryModels")}</button></div> : null}
          {selectionError ? <p className="settings-model-load-error" role="alert">{selectionError}</p> : null}
          {aiSettingsError ? <div className="settings-model-load-error" role="alert"><p>{aiSettingsError}</p><button type="button" className="settings-secondary-button" onClick={() => void onAiSettingsReload()}>{t("common.retry")}</button></div> : null}
          <p id="settings-model-helper" className="settings-helper-text">{helperText}</p>
        </div>
        <div className="settings-preference-row"><span>{t("models.responseMode")}</span><div className="settings-segmented" role="group" aria-label={t("models.responseMode")}>{responseModes.map((option) => <button key={option.value} type="button" disabled={!aiSettingsLoaded || aiSettingsSaving} className={responseMode === option.value ? "is-selected" : ""} aria-pressed={responseMode === option.value} onClick={() => void onResponseModeChange(option.value)}>{option.label}</button>)}</div></div>
      </SettingsCard>
      <SettingsCard icon="settings" title={t("models.replySettings")}>
        <div className="settings-budget-field">
          <div className="settings-select-row"><label htmlFor="settings-context-budget">{t("models.contextBudget")}</label><Select id="settings-context-budget" aria-describedby="settings-context-helper" value={modelSelection?.contextBudget ?? "auto"} options={contextOptions} getPopupContainer={getSettingsPopupContainer} disabled={!aiSettingsLoaded || !selectedModel || !modelSelection || aiSettingsSaving} onChange={(contextBudget: ContextBudget) => { if (modelSelection && selectedModel) { const contextLimit = contextBudgetLimit(contextBudget, selectedModel.contextWindowTokens); const outputBudget = outputBudgetAvailable(modelSelection.outputBudget, contextLimit, selectedModel.maxOutputTokens) ? modelSelection.outputBudget : "auto"; void requestSelection({ ...modelSelection, contextBudget, outputBudget }); } }} /></div>
          {selectedModel && effectiveContextLimit !== null ? <p id="settings-context-helper" className="settings-helper-text">{t("models.contextSummary", { maximum: formatTokenLimit(selectedModel.contextWindowTokens), effective: formatTokenLimit(effectiveContextLimit) })}</p> : null}
        </div>
        <div className="settings-budget-field">
          <div className="settings-select-row"><label htmlFor="settings-output-budget">{t("models.outputBudget")}</label><Select id="settings-output-budget" aria-describedby="settings-output-helper" value={modelSelection?.outputBudget ?? "auto"} options={outputOptions} getPopupContainer={getSettingsPopupContainer} disabled={!aiSettingsLoaded || !selectedModel || !modelSelection || aiSettingsSaving} onChange={(outputBudget: OutputBudget) => { if (modelSelection) void requestSelection({ ...modelSelection, outputBudget }); }} /></div>
          {selectedModel && effectiveOutputLimit !== null ? <p id="settings-output-helper" className="settings-helper-text">{t("models.outputSummary", { maximum: formatTokenLimit(selectedModel.maxOutputTokens), effective: formatTokenLimit(effectiveOutputLimit) })}</p> : null}
        </div>
        <div className="settings-select-row"><label className="settings-continuation-label" htmlFor="settings-response-delivery"><span className="settings-control-label">{t("models.responseDelivery")}</span><span className="settings-control-description">{t(responseDeliveryDescriptionKeys[responseDelivery])}</span></label><Select id="settings-response-delivery" aria-label={t("models.responseDelivery")} value={responseDelivery} options={responseDeliveryOptions} getPopupContainer={getSettingsPopupContainer} disabled={!aiSettingsLoaded || aiSettingsSaving} onChange={(delivery: ResponseDelivery) => void onResponseDeliveryChange(delivery)} /></div>
        <div className="settings-select-row"><label className="settings-continuation-label" htmlFor="settings-output-continuation"><span className="settings-control-label">{t("models.outputContinuation")}</span><span className="settings-control-description">{outputContinuationDescription}</span></label><Select id="settings-output-continuation" aria-label={t("models.outputContinuation")} value={outputContinuation} options={outputContinuationOptions} getPopupContainer={getSettingsPopupContainer} disabled={!aiSettingsLoaded || aiSettingsSaving} onChange={(policy: OutputContinuation) => void onOutputContinuationChange(policy)} /></div>
      </SettingsCard>
      <Collapse className="settings-model-disclosures" items={[
        { key: "advanced", label: <span className="settings-disclosure-label">{t("models.advanced")}{logFullPrompts ? <small>{t("models.loggingEnabled")}</small> : null}</span>, children: <>
        <div className="settings-toggle-row"><span><span className="settings-control-label">{t("models.logFullPrompts")}</span><span className="settings-control-description">{t("models.logFullPromptsDescription")}</span></span><Switch aria-label={t("models.logFullPrompts")} checked={logFullPrompts} disabled={!aiSettingsLoaded || aiSettingsSaving} onChange={(enabled) => void onLogFullPromptsChange(enabled)} /></div>
        </> },
        { key: "planned", label: t("models.planned"), children: <>
        <FutureSettingRow label={t("models.autoModel")} description={t("models.autoModelDescription")} />
        <FutureSettingRow label={t("models.showModelName")} description={t("models.showModelNameDescription")} />
        </> },
      ]} />
      {modalProvider && modalContainer ? <ConnectionModal provider={modalProvider} container={modalContainer} onCancel={() => setModalProvider(null)} onSubmit={(apiKey) => connect(modalProvider, apiKey)} /> : null}
      <Modal open={removingProvider !== null} getContainer={modalContainer ?? false} title={removingProvider ? t("models.removeConfirmTitle", { provider: removingProvider.name }) : undefined} okText={t("common.remove")} cancelText={t("common.cancel")} okButtonProps={{ danger: true }} afterClose={() => providerMenuOpener.current?.focus()} onCancel={() => setRemovingProvider(null)} onOk={() => { if (removingProvider) { void disconnect(removingProvider); setRemovingProvider(null); } }}><p>{t("models.removeConfirmDescription")}</p></Modal>
    </div>
  );
}

export function SettingsPage({ section, active, onSectionChange, modelSelection, responseMode, outputContinuation, responseDelivery, logFullPrompts, aiSettingsLoaded, aiSettingsSaving, aiSettingsError, onAiSettingsReload, onModelSelectionChange, onResponseModeChange, onOutputContinuationChange, onResponseDeliveryChange, onLogFullPromptsChange, providerCatalog, generalSettings, conversationSettings, toolSettings, mcpConnections, workspaces, onWorkspaceActivated, workspaceCreateRequest, onWorkspaceCreateRequestHandled, onWorkspaceOverlayChange, onOpenScheduleConversation, onClose, onProviderModalChange, onScheduleOverlayChange }: SettingsPageProps) {
  const { t } = useI18n();
  const { mode: authMode } = useAuthentication();
  const saving = aiSettingsSaving || generalSettings.saving || conversationSettings.saving || toolSettings.saving;
  const wasSavingRef = useRef(false);
  const [showSaveStatus, setShowSaveStatus] = useState(false);
  useEffect(() => {
    if (saving) {
      wasSavingRef.current = true;
      setShowSaveStatus(true);
      return;
    }
    if (!wasSavingRef.current) return;
    wasSavingRef.current = false;
    setShowSaveStatus(true);
    const timeout = window.setTimeout(() => setShowSaveStatus(false), 2000);
    return () => window.clearTimeout(timeout);
  }, [saving]);
  const [modalContainer, setModalContainer] = useState<HTMLElement | null>(null);
  const [categoriesOpen, setCategoriesOpen] = useState(false);
  useEffect(() => { if (!active) setCategoriesOpen(false); }, [active]);
  useEffect(() => {
    const closeDesktopDrawer = () => { if (window.innerWidth >= 768) setCategoriesOpen(false); };
    window.addEventListener("resize", closeDesktopDrawer);
    return () => window.removeEventListener("resize", closeDesktopDrawer);
  }, []);
  const categoryNavigation = <nav className="settings-category-rail" aria-label={t("settings.categories")}>
    {categories.map((category) => {
      const enabled = category.enabled === true;
      const selected = category.id === section;
      return <button key={category.id} type="button" className={`settings-category${selected ? " is-selected" : ""}${enabled ? "" : " is-disabled"}`} onClick={() => { if (enabled) { onSectionChange(category.id as SettingsSection); setCategoriesOpen(false); } }} disabled={!enabled} aria-current={selected ? "page" : undefined}><Icon name={category.icon} /><span>{t(category.labelKey)}</span>{enabled ? null : <small>{t("common.demo")}</small>}</button>;
    })}
    <p className="settings-rail-note">{t("settings.moreCategoriesFuture")}</p>
  </nav>;
  return (
    <section ref={setModalContainer} className="settings-page" aria-labelledby="settings-page-title">
      <div className="settings-layout">
        <aside className="settings-navigation">
          <header className="settings-navigation-header">
            <Button type="text" icon={<ArrowLeftOutlined aria-hidden="true" />} onClick={onClose}>{t("settings.returnToChat")}</Button>
            <h1 id="settings-page-title"><span className="settings-desktop-title">{t("settings.title")}</span><span className="settings-mobile-title">{t(categories.find(category => category.id === section)!.labelKey)}</span></h1>
            <Button className="settings-category-toggle" icon={<MenuOutlined />} aria-label={t("settings.categories")} aria-expanded={categoriesOpen} onClick={() => setCategoriesOpen(true)} />
            {showSaveStatus ? <SaveStatus saved={!saving} /> : null}
          </header>
          <div className="settings-desktop-categories">{categoryNavigation}</div>
        </aside>
        <div className="settings-content">
{section === "skills" ? <SkillsSettings workspaces={workspaces} container={modalContainer} onOverlayChange={onWorkspaceOverlayChange} /> : section === "agents" ? <AgentsSettings workspaces={workspaces} providerCatalog={providerCatalog} container={modalContainer} onOverlayChange={onWorkspaceOverlayChange} /> : section === "general" ? <><div className="settings-intro"><h2>{t("settings.category.general")}</h2><p>{t("settings.generalIntro")}</p></div><GeneralSettings generalSettings={generalSettings} conversationSettings={conversationSettings} /></> : section === "workspaces" ? <><WorkspacesSettings controller={workspaces} container={modalContainer} onActivated={onWorkspaceActivated} createRequest={workspaceCreateRequest} onCreateRequestHandled={onWorkspaceCreateRequestHandled} onOverlayChange={onWorkspaceOverlayChange} /></> : section === "models" ? <><div className="settings-intro"><h2>{t("settings.category.models")}</h2><p>{t("settings.modelsIntro")}</p></div><ModelsSettings modelSelection={modelSelection} responseMode={responseMode} outputContinuation={outputContinuation} responseDelivery={responseDelivery} logFullPrompts={logFullPrompts} aiSettingsLoaded={aiSettingsLoaded} aiSettingsSaving={aiSettingsSaving} aiSettingsError={aiSettingsError} onAiSettingsReload={onAiSettingsReload} onModelSelectionChange={onModelSelectionChange} onResponseModeChange={onResponseModeChange} onOutputContinuationChange={onOutputContinuationChange} onResponseDeliveryChange={onResponseDeliveryChange} onLogFullPromptsChange={onLogFullPromptsChange} providerCatalog={providerCatalog} onProviderModalChange={onProviderModalChange} modalContainer={modalContainer} /></> : section === "tools" ? <ToolsSettings controller={toolSettings} mcpConnections={mcpConnections} modalContainer={modalContainer} /> : section === "schedules" ? <><div className="settings-intro"><h2>{t("settings.category.schedules")}</h2><p>{t("settings.schedulesIntro")}</p></div><SchedulePage active={active && section === "schedules"} container={modalContainer} defaultTimeZone={generalSettings.settings.timeZone} modelSelection={modelSelection} modelChoices={providerCatalog.modelChoices} responseMode={responseMode} outputContinuation={outputContinuation} activeWorkspaceId={workspaces.catalog?.activeWorkspaceId} workspaces={workspaces.catalog?.workspaces ?? []} workspaceLoading={workspaces.loading} workspaceError={workspaces.error !== null} onWorkspaceRetry={() => void workspaces.reload()} onOpenConversation={onOpenScheduleConversation} onOverlayChange={onScheduleOverlayChange} /></> : section === "privacy" ? <><div className="settings-intro"><h2>{t("settings.category.privacy")}</h2><p>{t(authMode === "trusted_local" ? "auth.trustedLocalDescription" : "auth.changeDescription")}</p></div><PrivacySettings /></> : <><div className="settings-intro"><h2>{t("settings.category.about")}</h2><p>{t("about.intro")}</p></div><AboutSettings /></>}
        </div>
      </div>
      <Drawer title={t("settings.categories")} placement="left" open={categoriesOpen} onClose={() => setCategoriesOpen(false)} getContainer={() => modalContainer ?? document.body} size={280} className="settings-category-drawer">
        {categoryNavigation}
      </Drawer>
    </section>
  );
}

export default SettingsPage;
