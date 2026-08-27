import { Input, Modal, Popconfirm, Select } from "antd";
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";

import {
  deleteProviderConnection,
  listOpenRouterModels,
  listProviderConnections,
  providerErrorText,
  testProviderConnection,
  replaceProviderConnection,
  type ProviderId,
  type ProviderStatus,
  type ProviderSummary,
} from "../../api/providerConnections";
import type { ResponseMode } from "../../api/aiSettings";
import type { MessageKey } from "../../i18n/catalog";
import { useI18n } from "../../i18n/I18nProvider";
import { GeneralSettings } from "./GeneralSettings";
import { localModelCatalog, openRouterModelCatalog, type ModelCatalogItem, type ModelChoice, type ModelSelection } from "./modelCatalog";
import { FutureSettingRow, Icon, SaveStatus, SettingsCard, type IconName } from "./SettingsPrimitives";
import type { DemoSettings, SettingsSection } from "./settingsState";
import "./settings.css";

type SettingsPageProps = {
  section: SettingsSection;
  onSectionChange: (section: SettingsSection) => void;
  settings: DemoSettings;
  onSettingsChange: (next: DemoSettings) => void;
  modelSelection: ModelSelection | null;
  responseMode: ResponseMode;
  aiSettingsSaving: boolean;
  aiSettingsError: string | null;
  onModelSelectionChange: (selection: ModelSelection | null) => Promise<string | null>;
  onResponseModeChange: (responseMode: ResponseMode) => Promise<string | null>;
  onModelChoicesChange: (choices: ReadonlyArray<ModelChoice>) => void;
  onClose: () => void;
  onProviderModalChange?: (open: boolean) => void;
};

const categories: Array<{ id: SettingsSection | "memory" | "tools" | "appearance" | "privacy" | "about"; labelKey: MessageKey; icon: IconName; enabled?: boolean }> = [
  { id: "general", labelKey: "settings.category.general", icon: "settings", enabled: true }, { id: "models", labelKey: "settings.category.models", icon: "robot", enabled: true },
  { id: "memory", labelKey: "settings.category.memory", icon: "database" }, { id: "tools", labelKey: "settings.category.tools", icon: "connections" },
  { id: "appearance", labelKey: "settings.category.appearance", icon: "appearance" }, { id: "privacy", labelKey: "settings.category.privacy", icon: "privacy" }, { id: "about", labelKey: "settings.category.about", icon: "info" },
];

const providerStatusKeys: Record<ProviderStatus, MessageKey> = {
  disconnected: "models.status.disconnected", connected: "models.status.connected", invalid_credentials: "models.status.invalidCredentials", provider_unreachable: "models.status.unreachable",
  provider_timeout: "models.status.timeout", provider_rate_limited: "models.status.rateLimited", credential_store_unavailable: "models.status.storeUnavailable",
};

type ProviderFeedback = { message?: string; error?: string };
type ProviderOperation = Partial<Record<ProviderId, number>>;
type ModelLoadStatus = "idle" | "loading" | "success" | "error";

type ModelsSettingsProps = {
  modelSelection: ModelSelection | null;
  responseMode: ResponseMode;
  aiSettingsSaving: boolean;
  aiSettingsError: string | null;
  onModelSelectionChange: (selection: ModelSelection | null) => Promise<string | null>;
  onResponseModeChange: (responseMode: ResponseMode) => Promise<string | null>;
  onModelChoicesChange: (choices: ReadonlyArray<ModelChoice>) => void;
  onProviderModalChange?: (open: boolean) => void;
  modalContainer: HTMLElement | null;
  openRouterModels: ReadonlyArray<ModelCatalogItem> | null;
  openRouterModelLoadStatus: ModelLoadStatus;
  openRouterModelError: string | null;
  onOpenRouterModelsChange: (models: ReadonlyArray<ModelCatalogItem>) => void;
  onOpenRouterModelLoadStateChange: (status: ModelLoadStatus, error: string | null) => void;
  onOpenRouterModelsReset: () => void;
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

function ModelsSettings({ modelSelection, responseMode, aiSettingsSaving, aiSettingsError, onModelSelectionChange, onResponseModeChange, onModelChoicesChange, onProviderModalChange, modalContainer, openRouterModels, openRouterModelLoadStatus, openRouterModelError, onOpenRouterModelsChange, onOpenRouterModelLoadStateChange, onOpenRouterModelsReset }: ModelsSettingsProps) {
  const { t } = useI18n();
  const [providers, setProviders] = useState<ProviderSummary[] | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [operations, setOperations] = useState<ProviderOperation>({});
  const [feedback, setFeedback] = useState<Partial<Record<ProviderId, ProviderFeedback>>>({});
  const [modalProvider, setModalProvider] = useState<ProviderSummary | null>(null);
  const [selectionError, setSelectionError] = useState<string | null>(null);
  const generationsRef = useRef<Record<ProviderId, number>>({ openai: 0, anthropic: 0, openrouter: 0 });
  const activeOperationsRef = useRef<ProviderOperation>({});
  const modelGenerationsRef = useRef<Record<ProviderId, number>>({ openai: 0, anthropic: 0, openrouter: 0 });
  const activeModelLoadsRef = useRef<ProviderOperation>({});
  const reconciliationRef = useRef<string | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  const refreshProviders = useCallback(async () => {
    setCatalogError(null);
    try {
      const summaries = await listProviderConnections();
      setProviders(summaries);
      return summaries;
    } catch (requestError) {
      setProviders(null);
      setCatalogError(providerErrorText(requestError, t));
      return null;
    }
  }, [t]);

  const loadOpenRouterModels = useCallback(async (force = false) => {
    if (!force && openRouterModels !== null) return;
    if (activeModelLoadsRef.current.openrouter !== undefined) return;
    const providerId: ProviderId = "openrouter";
    const generation = modelGenerationsRef.current[providerId] + 1;
    modelGenerationsRef.current[providerId] = generation;
    activeModelLoadsRef.current = { ...activeModelLoadsRef.current, [providerId]: generation };
    onOpenRouterModelLoadStateChange("loading", null);
    try {
      const models = await listOpenRouterModels();
      if (mountedRef.current && activeModelLoadsRef.current[providerId] === generation && modelGenerationsRef.current[providerId] === generation) {
        onOpenRouterModelsChange(openRouterModelCatalog(models));
        onOpenRouterModelLoadStateChange("success", null);
      }
    } catch (requestError) {
      if (mountedRef.current && activeModelLoadsRef.current[providerId] === generation && modelGenerationsRef.current[providerId] === generation) {
        onOpenRouterModelLoadStateChange("error", providerErrorText(requestError, t));
      }
    } finally {
      if (activeModelLoadsRef.current[providerId] === generation) {
        const { [providerId]: _, ...remaining } = activeModelLoadsRef.current;
        activeModelLoadsRef.current = remaining;
      }
    }
  }, [onOpenRouterModelLoadStateChange, onOpenRouterModelsChange, openRouterModels, t]);

  useEffect(() => { void refreshProviders(); }, [refreshProviders]);
  useEffect(() => {
    const openRouterConnected = providers?.some((provider) => provider.id === "openrouter" && provider.connected) ?? false;
    if (openRouterConnected && openRouterModels === null && openRouterModelLoadStatus !== "error") void loadOpenRouterModels();
  }, [loadOpenRouterModels, openRouterModelLoadStatus, openRouterModels, providers]);
  useEffect(() => { onProviderModalChange?.(modalProvider !== null); }, [modalProvider, onProviderModalChange]);

  const replaceSummary = (summary: ProviderSummary) => {
    setProviders((current) => current?.map((provider) => provider.id === summary.id ? summary : provider) ?? current);
  };
  const invalidateOpenRouterModels = () => {
    modelGenerationsRef.current.openrouter += 1;
    const { openrouter: _, ...remaining } = activeModelLoadsRef.current;
    activeModelLoadsRef.current = remaining;
    onOpenRouterModelsReset();
  };
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
    try {
      const summaries = await listProviderConnections();
      if (!isCurrentOperation(providerId, generation)) return;
      const persistedSummary = summaries.find((summary) => summary.id === providerId);
      if (persistedSummary) replaceSummary(persistedSummary);
    } catch {
      // Keep the operation error: a refresh may not hide the cause of the failed action.
    }
  };
  const testConnection = async (provider: ProviderSummary) => {
    const generation = beginOperation(provider, t("models.operationTesting"));
    if (generation === null) return;
    try {
      const summary = await testProviderConnection(provider.id);
      if (isCurrentOperation(provider.id, generation)) {
        replaceSummary(summary);
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
        replaceSummary({ ...provider, connected: false, status: "disconnected", credentialPreview: null, lastCheckedAt: null });
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
      replaceSummary(summary);
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

  const connectedProviders = useMemo(() => providers?.filter((provider) => provider.connected) ?? [], [providers]);
  const selectedProvider = modelSelection
    ? connectedProviders.find((provider) => provider.id === modelSelection.providerId)
    : connectedProviders.length === 1 ? connectedProviders[0] : undefined;
  const selectedModels = selectedProvider
    ? selectedProvider.id === "openrouter" ? openRouterModels ?? [] : localModelCatalog[selectedProvider.id]
    : [];
  const selectedModelIsAvailable = modelSelection !== null && selectedModels.some((model) => model.id === modelSelection.modelId);
  const openRouterModelsPending = connectedProviders.some((provider) => provider.id === "openrouter") && openRouterModels === null && (openRouterModelLoadStatus === "idle" || openRouterModelLoadStatus === "loading");
  const requestSelection = useCallback(async (next: ModelSelection | null) => {
    setSelectionError(null);
    const error = await onModelSelectionChange(next);
    if (error) setSelectionError(error);
  }, [onModelSelectionChange]);

  useEffect(() => {
    const choices = connectedProviders.flatMap((provider) => {
      const models = provider.id === "openrouter" ? (openRouterModelLoadStatus === "success" ? openRouterModels ?? [] : []) : localModelCatalog[provider.id];
      return models.map((model) => ({ selection: { providerId: provider.id, modelId: model.id }, label: model.label }));
    });
    onModelChoicesChange(choices);
  }, [connectedProviders, onModelChoicesChange, openRouterModelLoadStatus, openRouterModels]);

  useEffect(() => {
    if (providers === null || aiSettingsSaving) return;
    if (modelSelection !== null && selectedProvider?.id === "openrouter" && (openRouterModelLoadStatus !== "success" || selectedModelIsAvailable)) return;
    if (modelSelection !== null && selectedProvider && selectedModelIsAvailable) { reconciliationRef.current = null; return; }
    const key = `${modelSelection?.providerId ?? "none"}:${modelSelection?.modelId ?? "none"}:${connectedProviders.map((provider) => `${provider.id}:${provider.connected}`).join(",")}:${openRouterModelLoadStatus}:${openRouterModels?.map((model) => model.id).join(",") ?? ""}`;
    if (reconciliationRef.current === key) return;
    reconciliationRef.current = key;
    const fallback = connectedProviders.map((provider) => ({ provider, models: provider.id === "openrouter" ? (openRouterModelLoadStatus === "success" ? openRouterModels ?? [] : []) : localModelCatalog[provider.id] })).find((candidate) => candidate.models.length > 0);
    const model = fallback?.models[0];
    if (fallback && model) void requestSelection({ providerId: fallback.provider.id, modelId: model.id });
    else if (modelSelection !== null && connectedProviders.length === 0) void requestSelection(null);
  }, [aiSettingsSaving, connectedProviders, modelSelection, openRouterModelLoadStatus, openRouterModels, providers, requestSelection, selectedModelIsAvailable, selectedProvider]);

  const getSettingsPopupContainer = () => modalContainer ?? document.body;
  const providerOptions = connectedProviders.map((provider) => ({ value: provider.id, label: provider.name }));
  const modelOptions = selectedModels.map((model) => ({ value: model.id, label: <span className="settings-model-option"><strong>{model.label}</strong><small>{model.id}</small></span>, searchText: `${model.label} ${model.id}` }));
  const modelDisabled = !selectedProvider || (selectedProvider.id === "openrouter" && (openRouterModelsPending || selectedModels.length === 0));
  const openRouterConnected = connectedProviders.some((provider) => provider.id === "openrouter");
  const helperText = connectedProviders.length === 0
    ? t("models.helper.connect")
    : selectedProvider?.id === "openrouter" && openRouterModelsPending ? t("models.helper.loadingOpenRouter")
    : selectedProvider?.id === "openrouter" && selectedModels.length === 0 ? t("models.helper.emptyOpenRouter")
    : modelSelection ? t("models.helper.selected") : t("models.helper.select");

  const responseModes: ReadonlyArray<{ value: ResponseMode; label: string }> = [{ value: "default", label: t("models.response.default") }, { value: "fast", label: t("models.response.fast") }, { value: "balanced", label: t("models.response.balanced") }, { value: "deep", label: t("models.response.deep") }];
  return (
    <div className="settings-form-stack">
      <SettingsCard icon="connections" title={t("models.providers")}>
        <p className="settings-card-description">{t("models.providersDescription")}</p>
        {providers === null && !catalogError ? <p className="settings-provider-feedback" role="status" aria-live="polite">{t("models.loadingProviders")}</p> : null}
        {catalogError ? <div className="settings-provider-feedback settings-provider-feedback--error" role="alert"><p>{catalogError}</p><button type="button" className="settings-secondary-button" onClick={() => void refreshProviders()}>{t("common.retry")}</button></div> : null}
        {providers ? (
          <div className="settings-service-list">
            {providers.map((provider) => {
              const busy = operations[provider.id] !== undefined;
              const statusClass = provider.status === "connected" ? "settings-online" : "settings-offline";
              return (
                <div className="settings-service-card" key={provider.id} aria-label={t("models.providerConnection", { provider: provider.name })} aria-busy={busy}>
                  <div className="settings-service-identity"><Icon name={provider.id} /><span><strong>{provider.name}</strong><span className={statusClass}><i aria-hidden="true" />{t(providerStatusKeys[provider.status])}</span>{provider.credentialPreview ? <small>{provider.credentialPreview}</small> : null}</span></div>
                  <div className="settings-service-actions" role="group" aria-label={t("models.providerActions", { provider: provider.name })} aria-busy={busy}>
                    <button type="button" className="settings-secondary-button" onClick={() => setModalProvider(provider)} disabled={busy}>{provider.connected ? t("models.manage") : t("models.connect")}</button>
                    {provider.connected ? <><button type="button" className="settings-secondary-button" onClick={() => void testConnection(provider)} disabled={busy}>{busy ? t("common.processing") : t("models.testConnection")}</button><Popconfirm title={t("models.removeConfirmTitle", { provider: provider.name })} description={t("models.removeConfirmDescription")} okText={t("common.remove")} cancelText={t("common.cancel")} onConfirm={() => void disconnect(provider)} okButtonProps={{ loading: busy }}><button type="button" className="settings-danger-button" disabled={busy}>{t("common.remove")}</button></Popconfirm></> : null}
                  </div>
                </div>
              );
            })}
          </div>
        ) : null}
        <div className="settings-provider-announcement" aria-live="polite">{Object.entries(feedback).map(([providerId, item]) => item ? <p key={providerId} className={item.error ? "settings-action-error" : "settings-action-status"}>{item.error ?? item.message}</p> : null)}</div>
      </SettingsCard>
      <SettingsCard icon="robot" title={t("models.selectModel")}>
        <div className="settings-model-selection">
          <div className="settings-select-row"><label htmlFor="settings-model-provider">{t("models.provider")}</label><Select id="settings-model-provider" aria-describedby="settings-model-helper" value={selectedProvider?.id} placeholder={t("models.selectProvider")} options={providerOptions} getPopupContainer={getSettingsPopupContainer} disabled={providers === null || connectedProviders.length === 0 || aiSettingsSaving} onChange={(providerId) => { const provider = providerOptions.find((option) => option.value === providerId); const models = providerId === "openrouter" ? openRouterModels ?? [] : localModelCatalog[providerId as ProviderId]; const model = models[0]; if (provider && model) void requestSelection({ providerId: providerId as ProviderId, modelId: model.id }); }} /></div>
          <div className="settings-select-row"><label htmlFor="settings-default-model">{t("models.model")}</label><Select id="settings-default-model" aria-describedby="settings-model-helper" showSearch value={selectedModelIsAvailable && modelSelection ? modelSelection.modelId : undefined} placeholder={selectedProvider ? t("models.selectModelPlaceholder") : t("models.connectProviderFirst")} options={modelOptions} getPopupContainer={getSettingsPopupContainer} filterOption={(input, option) => String((option as { searchText?: string } | undefined)?.searchText).toLowerCase().includes(input.toLowerCase())} disabled={modelDisabled || aiSettingsSaving} loading={openRouterModelsPending || aiSettingsSaving} notFoundContent={selectedProvider?.id === "openrouter" && !openRouterModelsPending ? t("models.noModels") : undefined} onChange={(modelId) => { if (selectedProvider) void requestSelection({ providerId: selectedProvider.id, modelId }); }} /></div>
          {openRouterConnected && openRouterModelLoadStatus === "error" ? <div className="settings-model-load-error" role="alert"><p>{openRouterModelError}</p><button type="button" className="settings-secondary-button settings-model-retry" onClick={() => void loadOpenRouterModels(true)}>{t("models.retryModels")}</button></div> : null}
          {selectionError ?? aiSettingsError ? <p className="settings-model-load-error" role="alert">{selectionError ?? aiSettingsError}</p> : null}
          <p id="settings-model-helper" className="settings-helper-text">{helperText}</p>
        </div>
        <div className="settings-preference-row"><span>{t("models.responseMode")}</span><div className="settings-segmented" role="group" aria-label={t("models.responseMode")}>{responseModes.map((option) => <button key={option.value} type="button" disabled={aiSettingsSaving} className={responseMode === option.value ? "is-selected" : ""} aria-pressed={responseMode === option.value} onClick={() => void onResponseModeChange(option.value)}>{option.label}</button>)}</div></div>
        <FutureSettingRow label={t("models.autoModel")} description={t("models.autoModelDescription")} />
        <FutureSettingRow label={t("models.showModelName")} description={t("models.showModelNameDescription")} />
      </SettingsCard>
      {modalProvider && modalContainer ? <ConnectionModal provider={modalProvider} container={modalContainer} onCancel={() => setModalProvider(null)} onSubmit={(apiKey) => connect(modalProvider, apiKey)} /> : null}
    </div>
  );
}

export function SettingsPage({ section, onSectionChange, settings, onSettingsChange, modelSelection, responseMode, aiSettingsSaving, aiSettingsError, onModelSelectionChange, onResponseModeChange, onModelChoicesChange, onClose, onProviderModalChange }: SettingsPageProps) {
  const { t } = useI18n();
  const [saved, setSaved] = useState(true); useEffect(() => { if (saved) return; const timeout = window.setTimeout(() => setSaved(true), 650); return () => window.clearTimeout(timeout); }, [saved]);
  const [modalContainer, setModalContainer] = useState<HTMLElement | null>(null);
  const [openRouterModels, setOpenRouterModels] = useState<ReadonlyArray<ModelCatalogItem> | null>(null);
  const [openRouterModelLoadStatus, setOpenRouterModelLoadStatus] = useState<ModelLoadStatus>("idle");
  const [openRouterModelError, setOpenRouterModelError] = useState<string | null>(null);
  const updateSetting = <K extends keyof DemoSettings>(key: K, value: DemoSettings[K]) => { onSettingsChange({ ...settings, [key]: value }); setSaved(false); };
  return (
    <section ref={setModalContainer} className="settings-page" aria-labelledby="settings-page-title">
      <header className="settings-header">
        <div><h1 id="settings-page-title">{t("settings.title")}</h1><p>{t("settings.subtitle")}</p></div>
        <div className="settings-header-actions"><SaveStatus saved={saved && !aiSettingsSaving} /><button className="settings-close-button" type="button" onClick={onClose} aria-label={t("settings.close")} title={t("settings.close")}><span aria-hidden="true">×</span></button></div>
      </header>
      <div className="settings-layout">
        <nav className="settings-category-rail" aria-label={t("settings.categories")}>
          {categories.map((category) => {
            const isSelected = category.id === section;
            const isEnabled = category.enabled === true;
            return <button key={category.id} type="button" className={`settings-category${isSelected ? " is-selected" : ""}${!isEnabled ? " is-disabled" : ""}`} onClick={() => { if (isEnabled) onSectionChange(category.id as SettingsSection); }} disabled={!isEnabled} aria-current={isSelected ? "page" : undefined}><Icon name={category.icon} /><span>{t(category.labelKey)}</span>{!isEnabled ? <small>{t("common.demo")}</small> : null}</button>;
          })}
          <p className="settings-rail-note">{t("settings.moreCategoriesFuture")}</p>
        </nav>
        <div className="settings-content">
          {section === "general" ? <><div className="settings-intro"><h2>{t("settings.category.general")}</h2><p>{t("settings.generalIntro")}</p></div><GeneralSettings settings={settings} onChange={updateSetting} /></> : <><div className="settings-intro"><h2>{t("settings.category.models")}</h2><p>{t("settings.modelsIntro")}</p></div><ModelsSettings modelSelection={modelSelection} responseMode={responseMode} aiSettingsSaving={aiSettingsSaving} aiSettingsError={aiSettingsError} onModelSelectionChange={onModelSelectionChange} onResponseModeChange={onResponseModeChange} onModelChoicesChange={onModelChoicesChange} onProviderModalChange={onProviderModalChange} modalContainer={modalContainer} openRouterModels={openRouterModels} openRouterModelLoadStatus={openRouterModelLoadStatus} openRouterModelError={openRouterModelError} onOpenRouterModelsChange={setOpenRouterModels} onOpenRouterModelLoadStateChange={(status, error) => { setOpenRouterModelLoadStatus(status); setOpenRouterModelError(error); }} onOpenRouterModelsReset={() => { setOpenRouterModels(null); setOpenRouterModelLoadStatus("idle"); setOpenRouterModelError(null); }} /></>}
          <p className="settings-demo-note">{t("settings.sessionNote")}</p>
        </div>
      </div>
    </section>
  );
}

export default SettingsPage;
