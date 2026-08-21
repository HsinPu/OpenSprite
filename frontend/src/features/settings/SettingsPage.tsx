import { Input, Modal, Popconfirm, Select } from "antd";
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";

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
import { localModelCatalog, modelLabel, openRouterModelCatalog, type ModelCatalogItem, type ModelSelection } from "./modelCatalog";
import "./settings.css";

export type SettingsSection = "general" | "models";

export type DemoSettings = {
  language: string;
  timezone: string;
  newConversation: boolean;
  restoreConversation: boolean;
  sendMode: string;
  taskNotifications: boolean;
  confirmNotifications: boolean;
  sound: boolean;
  responseSpeed: string;
  autoSelect: boolean;
  showNames: boolean;
};

export const defaultDemoSettings: DemoSettings = {
  language: "繁體中文", timezone: "依照系統設定", newConversation: true,
  restoreConversation: false, sendMode: "Enter 送出，Shift + Enter 換行",
  taskNotifications: true, confirmNotifications: true, sound: false,
  responseSpeed: "平衡",
  autoSelect: true, showNames: true,
};

type SettingsPageProps = {
  section: SettingsSection;
  onSectionChange: (section: SettingsSection) => void;
  settings: DemoSettings;
  onSettingsChange: (next: DemoSettings) => void;
  modelSelection: ModelSelection | null;
  modelSelectionSaving: boolean;
  modelSelectionError: string | null;
  onModelSelectionChange: (selection: ModelSelection | null) => Promise<string | null>;
  onModelChoicesChange: (choices: ReadonlyArray<{ selection: ModelSelection; label: string }>) => void;
  onClose: () => void;
  onProviderModalChange?: (open: boolean) => void;
};

type IconName = "settings" | "robot" | "database" | "connections" | "appearance" | "privacy" | "info" | "globe" | "rocket" | "bell" | "openai" | "anthropic" | "openrouter";

const categories: Array<{ id: SettingsSection | "memory" | "tools" | "appearance" | "privacy" | "about"; label: string; icon: IconName; enabled?: boolean }> = [
  { id: "general", label: "一般", icon: "settings", enabled: true }, { id: "models", label: "AI 模型", icon: "robot", enabled: true },
  { id: "memory", label: "記憶與資料", icon: "database" }, { id: "tools", label: "工具與連線", icon: "connections" },
  { id: "appearance", label: "外觀", icon: "appearance" }, { id: "privacy", label: "隱私", icon: "privacy" }, { id: "about", label: "關於", icon: "info" },
];

const providerStatusText: Record<ProviderStatus, string> = {
  disconnected: "尚未連線", connected: "已連線", invalid_credentials: "API 金鑰無效", provider_unreachable: "暫時無法連線",
  provider_timeout: "連線逾時", provider_rate_limited: "請求受限", credential_store_unavailable: "安全儲存服務無法使用",
};

function Icon({ name }: { name: IconName }) {
  if (name === "openai") return <span className="settings-brand-icon settings-brand-icon--openai" aria-hidden="true">◎</span>;
  if (name === "anthropic") return <span className="settings-brand-icon settings-brand-icon--anthropic" aria-hidden="true">AI</span>;
  if (name === "openrouter") return <span className="settings-brand-icon settings-brand-icon--openrouter" aria-hidden="true">OR</span>;
  const paths: Record<Exclude<IconName, "openai" | "anthropic" | "openrouter">, string> = {
    settings: "M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Zm8.2 3.5 1.6-1.2-1.7-2.9-1.9.7a8.1 8.1 0 0 0-1.5-.9l-.3-2h-3.4l-.3 2a8 8 0 0 0-1.5.9l-1.9-.7-1.7 2.9 1.6 1.2a7.3 7.3 0 0 0 0 1.8l-1.6 1.2 1.7 2.9 1.9-.7c.5.4 1 .7 1.5.9l.3 2h3.4l.3-2c.5-.2 1-.5 1.5-.9l1.9.7 1.7-2.9-1.6-1.2a7.3 7.3 0 0 0 0-1.8Z",
    robot: "M8 8h8a4 4 0 0 1 4 4v5H4v-5a4 4 0 0 1 4-4Zm4-4v4m-5 9v2m10-2v2M9 13h.1M15 13h.1",
    database: "M5 6c0-1.1 3.1-2 7-2s7 .9 7 2-3.1 2-7 2-7-.9-7-2Zm0 0v6c0 1.1 3.1 2 7 2s7-.9 7-2V6m-14 6v6c0 1.1 3.1 2 7 2s7-.9 7-2v-6",
    connections: "M8 12h8m-9-4a3 3 0 1 1 0-6 3 3 0 0 1 0 6Zm10 10a3 3 0 1 1 0-6 3 3 0 0 1 0 6ZM6 21a3 3 0 1 1 0-6 3 3 0 0 1 0 6Zm3-9 7 3m-7-6 7-3",
    appearance: "M12 3a9 9 0 0 0 0 18h1.2a1.8 1.8 0 0 0 1.7-2.4 1.8 1.8 0 0 1 1.7-2.4H19a2 2 0 0 0 2-2A9 9 0 0 0 12 3Zm-4 9h.1M8 8h.1m4-2h.1m4 3h.1",
    privacy: "M12 3 19 6v5c0 4.3-2.9 8.1-7 9-4.1-.9-7-4.7-7-9V6l7-3Zm-2 9 1.5 1.5L15 10",
    info: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-10v5m0-8h.1",
    globe: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm-8.5-9h17M12 3c2 2.2 3 5.2 3 9s-1 6.8-3 9c-2-2.2-3-5.2-3-9s1-6.8 3-9Z",
    rocket: "m14 4 6 6-3 1-4 4-1 3-3-3-3-1 4-4 1-3 3-3Zm-5 11-3 3m0-5-2 2m9-8h.1",
    bell: "M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9Zm-8 13h4",
  };
  return <svg className="settings-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>;
}

function SaveStatus({ saved }: { saved: boolean }) { return <p className={`settings-save-status${saved ? " settings-save-status--saved" : ""}`} role="status" aria-live="polite"><span className="settings-save-dot" aria-hidden="true">{saved ? "✓" : "•"}</span>{saved ? "已儲存" : "儲存中…"}</p>; }
function DemoSwitch({ checked, label, description, onChange }: { checked: boolean; label: string; description?: string; onChange: (checked: boolean) => void }) { return <label className="settings-switch-row"><span><span className="settings-control-label">{label}</span>{description ? <span className="settings-control-description">{description}</span> : null}</span><input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} /><span className="settings-switch" aria-hidden="true"><span /></span></label>; }
function SelectField({ id, label, value, options, onChange }: { id: string; label: string; value: string; options: string[]; onChange: (value: string) => void }) { return <label className="settings-select-row" htmlFor={id}><span>{label}</span><select id={id} value={value} onChange={(event) => onChange(event.target.value)}>{options.map((option) => <option key={option}>{option}</option>)}</select></label>; }
function SettingsCard({ icon, title, children }: { icon: IconName; title: string; children: ReactNode }) { return <section className="settings-card" aria-labelledby={`${title}-heading`}><h3 id={`${title}-heading`} className="settings-card-title"><Icon name={icon} />{title}</h3><div className="settings-card-body">{children}</div></section>; }

function GeneralSettings({ settings, onChange }: { settings: DemoSettings; onChange: <K extends keyof DemoSettings>(key: K, value: DemoSettings[K]) => void }) {
  return <div className="settings-form-stack"><SettingsCard icon="globe" title="語言與地區"><SelectField id="settings-language" label="介面語言" value={settings.language} options={["繁體中文", "English", "日本語"]} onChange={(value) => onChange("language", value)} /><SelectField id="settings-timezone" label="日期與時間" value={settings.timezone} options={["依照系統設定", "Asia/Taipei (UTC+8)", "UTC"]} onChange={(value) => onChange("timezone", value)} /></SettingsCard><SettingsCard icon="rocket" title="啟動與對話"><DemoSwitch checked={settings.newConversation} label="開啟 OpenSprite 時建立新對話" description="每次啟動都從乾淨的對話開始" onChange={(value) => onChange("newConversation", value)} /><DemoSwitch checked={settings.restoreConversation} label="保留上次開啟的對話" description="回到上次使用中的對話" onChange={(value) => onChange("restoreConversation", value)} /><SelectField id="settings-send-mode" label="送出訊息" value={settings.sendMode} options={["Enter 送出，Shift + Enter 換行", "Ctrl + Enter 送出，Enter 換行"]} onChange={(value) => onChange("sendMode", value)} /></SettingsCard><SettingsCard icon="bell" title="通知"><DemoSwitch checked={settings.taskNotifications} label="任務完成時通知我" onChange={(value) => onChange("taskNotifications", value)} /><DemoSwitch checked={settings.confirmNotifications} label="需要我確認時通知我" onChange={(value) => onChange("confirmNotifications", value)} /><DemoSwitch checked={settings.sound} label="播放提示音" onChange={(value) => onChange("sound", value)} /></SettingsCard></div>;
}

type ProviderFeedback = { message?: string; error?: string };
type ProviderOperation = Partial<Record<ProviderId, number>>;
type ModelLoadStatus = "idle" | "loading" | "success" | "error";

type ModelsSettingsProps = {
  settings: DemoSettings;
  onChange: <K extends keyof DemoSettings>(key: K, value: DemoSettings[K]) => void;
  modelSelection: ModelSelection | null;
  modelSelectionSaving: boolean;
  modelSelectionError: string | null;
  onModelSelectionChange: (selection: ModelSelection | null) => Promise<string | null>;
  onModelChoicesChange: (choices: ReadonlyArray<{ selection: ModelSelection; label: string }>) => void;
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
      setError("請輸入 API 金鑰。");
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
      title={`${provider.name} API 金鑰`}
      footer={null}
      getContainer={() => container}
      onCancel={() => { if (!submittingRef.current) close(); }}
      keyboard={!submitting}
      destroyOnHidden
      mask={{ closable: !submitting }}
      closable={!submitting}
    >
      <form onSubmit={submit} onKeyDownCapture={(event) => { if (submitting && event.key === "Escape") event.stopPropagation(); }}>
        <p className="provider-modal-copy">輸入新的金鑰會先驗證，再安全地取代目前儲存的連線。OpenSprite 不會顯示或預先填入既有金鑰。</p>
        <label className="provider-key-label" htmlFor="provider-api-key">API 金鑰</label>
        <Input.Password id="provider-api-key" name="apiKey" autoFocus autoComplete="new-password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} disabled={submitting} aria-invalid={Boolean(error)} aria-errormessage={error ? "provider-key-error" : undefined} />
        {error ? <p id="provider-key-error" className="provider-modal-error" role="alert">{error}</p> : null}
        <div className="provider-modal-actions">
          <button type="button" className="settings-secondary-button" onClick={close} disabled={submitting}>取消</button>
          <button type="submit" className="settings-outline-button" disabled={submitting}>{submitting ? "驗證中…" : "驗證並儲存"}</button>
        </div>
      </form>
    </Modal>
  );
}

function ModelsSettings({ settings, onChange, modelSelection, modelSelectionSaving, modelSelectionError, onModelSelectionChange, onModelChoicesChange, onProviderModalChange, modalContainer, openRouterModels, openRouterModelLoadStatus, openRouterModelError, onOpenRouterModelsChange, onOpenRouterModelLoadStateChange, onOpenRouterModelsReset }: ModelsSettingsProps) {
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

  useEffect(() => () => { mountedRef.current = false; }, []);

  const refreshProviders = useCallback(async () => {
    setCatalogError(null);
    try {
      const summaries = await listProviderConnections();
      setProviders(summaries);
      return summaries;
    } catch (requestError) {
      setProviders(null);
      setCatalogError(providerErrorText(requestError));
      return null;
    }
  }, []);

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
        onOpenRouterModelLoadStateChange("error", providerErrorText(requestError));
      }
    } finally {
      if (activeModelLoadsRef.current[providerId] === generation) {
        const { [providerId]: _, ...remaining } = activeModelLoadsRef.current;
        activeModelLoadsRef.current = remaining;
      }
    }
  }, [onOpenRouterModelLoadStateChange, onOpenRouterModelsChange, openRouterModels]);

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
    setFeedback((current) => ({ ...current, [provider.id]: { message: `${provider.name} 正在${action}。` } }));
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
    const generation = beginOperation(provider, "測試連線");
    if (generation === null) return;
    try {
      const summary = await testProviderConnection(provider.id);
      if (isCurrentOperation(provider.id, generation)) {
        replaceSummary(summary);
        setProviderFeedback(provider.id, { message: `${provider.name}：${providerStatusText[summary.status]}` });
      }
    } catch (requestError) {
      if (isCurrentOperation(provider.id, generation)) {
        setProviderFeedback(provider.id, { error: `${provider.name}：${providerErrorText(requestError)}` });
        await refreshFailedProvider(provider.id, generation);
      }
    } finally {
      finishOperation(provider.id, generation);
    }
  };
  const disconnect = async (provider: ProviderSummary) => {
    const generation = beginOperation(provider, "移除連線");
    if (generation === null) return;
    try {
      await deleteProviderConnection(provider.id);
      if (isCurrentOperation(provider.id, generation)) {
        replaceSummary({ ...provider, connected: false, status: "disconnected", credentialPreview: null, lastCheckedAt: null });
        if (provider.id === "openrouter") invalidateOpenRouterModels();
        setProviderFeedback(provider.id, { message: `${provider.name} 已移除連線。` });
      }
    } catch (requestError) {
      if (isCurrentOperation(provider.id, generation)) setProviderFeedback(provider.id, { error: `${provider.name}：${providerErrorText(requestError)}` });
    } finally {
      finishOperation(provider.id, generation);
    }
  };
  const connect = async (provider: ProviderSummary, apiKey: string): Promise<string | null> => {
    const generation = beginOperation(provider, "驗證並儲存連線");
    if (generation === null) return "這個模型廠家正在處理另一個操作。";
    try {
      const summary = await replaceProviderConnection(provider.id, apiKey);
      if (!isCurrentOperation(provider.id, generation)) return "這個操作已被較新的連線狀態取代。";
      replaceSummary(summary);
      setProviderFeedback(provider.id, { message: `${summary.name} 已連線。` });
      if (summary.id === "openrouter") {
        invalidateOpenRouterModels();
        void loadOpenRouterModels(true);
      }
      setModalProvider((current) => current?.id === provider.id ? null : current);
      return null;
    } catch (requestError) {
      const message = providerErrorText(requestError);
      if (isCurrentOperation(provider.id, generation)) clearProviderFeedback(provider.id);
      return message;
    } finally {
      finishOperation(provider.id, generation);
    }
  };

  const connectedProviders = useMemo(() => providers?.filter((provider) => provider.connected) ?? [], [providers]);
  const selectedProvider = modelSelection ? connectedProviders.find((provider) => provider.id === modelSelection.providerId) : undefined;
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
    if (providers === null || modelSelectionSaving) return;
    if (modelSelection !== null && selectedProvider?.id === "openrouter" && (openRouterModelLoadStatus !== "success" || selectedModelIsAvailable)) return;
    if (modelSelection !== null && selectedProvider && selectedModelIsAvailable) { reconciliationRef.current = null; return; }
    const key = `${modelSelection?.providerId ?? "none"}:${modelSelection?.modelId ?? "none"}:${connectedProviders.map((provider) => `${provider.id}:${provider.connected}`).join(",")}:${openRouterModelLoadStatus}:${openRouterModels?.map((model) => model.id).join(",") ?? ""}`;
    if (reconciliationRef.current === key) return;
    reconciliationRef.current = key;
    const fallback = connectedProviders.map((provider) => ({ provider, models: provider.id === "openrouter" ? (openRouterModelLoadStatus === "success" ? openRouterModels ?? [] : []) : localModelCatalog[provider.id] })).find((candidate) => candidate.models.length > 0);
    const model = fallback?.models[0];
    if (fallback && model) void requestSelection({ providerId: fallback.provider.id, modelId: model.id });
    else if (modelSelection !== null && connectedProviders.length === 0) void requestSelection(null);
  }, [connectedProviders, modelSelection, modelSelectionSaving, openRouterModelLoadStatus, openRouterModels, providers, requestSelection, selectedModelIsAvailable, selectedProvider]);

  const providerOptions = connectedProviders.map((provider) => ({ value: provider.id, label: provider.name }));
  const modelOptions = selectedModels.map((model) => ({ value: model.id, label: <span className="settings-model-option"><strong>{model.label}</strong><small>{model.id}</small></span>, searchText: `${model.label} ${model.id}` }));
  const modelDisabled = !selectedProvider || (selectedProvider.id === "openrouter" && (openRouterModelsPending || selectedModels.length === 0));
  const openRouterConnected = connectedProviders.some((provider) => provider.id === "openrouter");
  const helperText = connectedProviders.length === 0
    ? "請先連接至少一個模型廠家，才能選擇可用模型。"
    : selectedProvider?.id === "openrouter" && openRouterModelsPending ? "正在讀取 OpenRouter 可用模型…"
    : selectedProvider?.id === "openrouter" && selectedModels.length === 0 ? "OpenRouter 目前沒有可用模型。"
    : modelSelection ? "新對話會優先使用這個模型" : "請選擇新對話要使用的模型。";

  return <div className="settings-form-stack"><SettingsCard icon="connections" title="模型廠家"><p className="settings-card-description">管理已儲存在本機安全憑證服務中的模型廠家連線。</p>{providers === null && !catalogError ? <p className="settings-provider-feedback" role="status" aria-live="polite">正在讀取模型廠家連線…</p> : null}{catalogError ? <div className="settings-provider-feedback settings-provider-feedback--error" role="alert"><p>{catalogError}</p><button type="button" className="settings-secondary-button" onClick={() => void refreshProviders()}>重試</button></div> : null}{providers ? <div className="settings-service-list">{providers.map((provider) => { const busy = operations[provider.id] !== undefined; const statusClass = provider.status === "connected" ? "settings-online" : "settings-offline"; return <div className="settings-service-card" key={provider.id} aria-label={`${provider.name} 連線`} aria-busy={busy}><div className="settings-service-identity"><Icon name={provider.id} /><span><strong>{provider.name}</strong><span className={statusClass}><i aria-hidden="true" />{providerStatusText[provider.status]}</span>{provider.credentialPreview ? <small>{provider.credentialPreview}</small> : null}</span></div><div className="settings-service-actions" role="group" aria-label={`${provider.name} 操作`} aria-busy={busy}><button type="button" className="settings-secondary-button" onClick={() => setModalProvider(provider)} disabled={busy}>{provider.connected ? "管理" : "連接"}</button>{provider.connected ? <><button type="button" className="settings-secondary-button" onClick={() => void testConnection(provider)} disabled={busy}>{busy ? "處理中…" : "測試連線"}</button><Popconfirm title={`移除 ${provider.name} 的已儲存 API 金鑰？`} description="移除後，這個模型廠家將無法供新對話使用。" okText="移除" cancelText="取消" onConfirm={() => void disconnect(provider)} okButtonProps={{ loading: busy }}><button type="button" className="settings-danger-button" disabled={busy}>移除</button></Popconfirm></> : null}</div></div>; })}</div> : null}<div className="settings-provider-announcement" aria-live="polite">{Object.entries(feedback).map(([providerId, item]) => item ? <p key={providerId} className={item.error ? "settings-action-error" : "settings-action-status"}>{item.error ?? item.message}</p> : null)}</div></SettingsCard><SettingsCard icon="robot" title="選擇模型"><div className="settings-model-selection"><div className="settings-select-row"><label htmlFor="settings-model-provider">模型廠家</label><Select id="settings-model-provider" aria-describedby="settings-model-helper" value={selectedProvider?.id} placeholder="選擇模型廠家" options={providerOptions} disabled={providers === null || connectedProviders.length === 0 || modelSelectionSaving} onChange={(providerId) => { const provider = providerOptions.find((option) => option.value === providerId); const models = providerId === "openrouter" ? openRouterModels ?? [] : localModelCatalog[providerId as ProviderId]; const model = models[0]; if (provider && model) void requestSelection({ providerId: providerId as ProviderId, modelId: model.id }); }} /></div><div className="settings-select-row"><label htmlFor="settings-default-model">預設模型</label><Select id="settings-default-model" aria-describedby="settings-model-helper" showSearch value={selectedModelIsAvailable && modelSelection ? modelSelection.modelId : undefined} placeholder={selectedProvider ? "選擇預設模型" : "請先連接模型廠家"} options={modelOptions} filterOption={(input, option) => String((option as { searchText?: string } | undefined)?.searchText).toLowerCase().includes(input.toLowerCase())} disabled={modelDisabled || modelSelectionSaving} loading={openRouterModelsPending || modelSelectionSaving} notFoundContent={selectedProvider?.id === "openrouter" && !openRouterModelsPending ? "沒有可用模型" : undefined} onChange={(modelId) => { if (selectedProvider) void requestSelection({ providerId: selectedProvider.id, modelId }); }} /></div>{openRouterConnected && openRouterModelLoadStatus === "error" ? <div className="settings-model-load-error" role="alert"><p>{openRouterModelError}</p><button type="button" className="settings-secondary-button settings-model-retry" onClick={() => void loadOpenRouterModels(true)}>重試讀取模型</button></div> : null}{selectionError ?? modelSelectionError ? <p className="settings-model-load-error" role="alert">{selectionError ?? modelSelectionError}</p> : null}<p id="settings-model-helper" className="settings-helper-text">{helperText}</p></div><div className="settings-preference-row"><span>回應速度</span><div className="settings-segmented" role="group" aria-label="回應速度">{["快速", "平衡", "深入"].map((option) => <button key={option} type="button" className={settings.responseSpeed === option ? "is-selected" : ""} aria-pressed={settings.responseSpeed === option} onClick={() => onChange("responseSpeed", option)}>{option}</button>)}</div></div><DemoSwitch checked={settings.autoSelect} label="自動選擇可用模型" onChange={(value) => onChange("autoSelect", value)} /><DemoSwitch checked={settings.showNames} label="顯示模型名稱" onChange={(value) => onChange("showNames", value)} /></SettingsCard>{modalProvider && modalContainer ? <ConnectionModal provider={modalProvider} container={modalContainer} onCancel={() => setModalProvider(null)} onSubmit={(apiKey) => connect(modalProvider, apiKey)} /> : null}</div>;
}

export function SettingsPage({ section, onSectionChange, settings, onSettingsChange, modelSelection, modelSelectionSaving, modelSelectionError, onModelSelectionChange, onModelChoicesChange, onClose, onProviderModalChange }: SettingsPageProps) {
  const [saved, setSaved] = useState(true); useEffect(() => { if (saved) return; const timeout = window.setTimeout(() => setSaved(true), 650); return () => window.clearTimeout(timeout); }, [saved]);
  const [modalContainer, setModalContainer] = useState<HTMLElement | null>(null);
  const [openRouterModels, setOpenRouterModels] = useState<ReadonlyArray<ModelCatalogItem> | null>(null);
  const [openRouterModelLoadStatus, setOpenRouterModelLoadStatus] = useState<ModelLoadStatus>("idle");
  const [openRouterModelError, setOpenRouterModelError] = useState<string | null>(null);
  const updateSetting = <K extends keyof DemoSettings>(key: K, value: DemoSettings[K]) => { onSettingsChange({ ...settings, [key]: value }); setSaved(false); };
  return <section ref={setModalContainer} className="settings-page" aria-labelledby="settings-page-title"><header className="settings-header"><div><h1 id="settings-page-title">設定</h1><p>調整 OpenSprite 的使用方式</p></div><div className="settings-header-actions"><SaveStatus saved={saved} /><button className="settings-close-button" type="button" onClick={onClose} aria-label="關閉設定" title="關閉設定"><span aria-hidden="true">×</span></button></div></header><div className="settings-layout"><nav className="settings-category-rail" aria-label="設定分類">{categories.map((category) => { const isSelected = category.id === section; const isEnabled = category.enabled === true; return <button key={category.id} type="button" className={`settings-category${isSelected ? " is-selected" : ""}${!isEnabled ? " is-disabled" : ""}`} onClick={() => { if (isEnabled) onSectionChange(category.id as SettingsSection); }} disabled={!isEnabled} aria-current={isSelected ? "page" : undefined}><Icon name={category.icon} /><span>{category.label}</span>{!isEnabled ? <small>Demo</small> : null}</button>; })}<p className="settings-rail-note">其他分類將在完整版本提供</p></nav><div className="settings-content">{section === "general" ? <><div className="settings-intro"><h2>一般</h2><p>設定語言、啟動方式與日常使用偏好。</p></div><GeneralSettings settings={settings} onChange={updateSetting} /></> : <><div className="settings-intro"><h2>AI 模型</h2><p>連接你要使用的 AI 服務，並選擇預設模型。</p></div><ModelsSettings settings={settings} onChange={updateSetting} modelSelection={modelSelection} modelSelectionSaving={modelSelectionSaving} modelSelectionError={modelSelectionError} onModelSelectionChange={onModelSelectionChange} onModelChoicesChange={onModelChoicesChange} onProviderModalChange={onProviderModalChange} modalContainer={modalContainer} openRouterModels={openRouterModels} openRouterModelLoadStatus={openRouterModelLoadStatus} openRouterModelError={openRouterModelError} onOpenRouterModelsChange={setOpenRouterModels} onOpenRouterModelLoadStateChange={(status, error) => { setOpenRouterModelLoadStatus(status); setOpenRouterModelError(error); }} onOpenRouterModelsReset={() => { setOpenRouterModels(null); setOpenRouterModelLoadStatus("idle"); setOpenRouterModelError(null); }} /></>}<p className="settings-demo-note">一般偏好只在本次工作階段暫存；模型選擇與模型廠家連線由本機服務安全管理。</p></div></div></section>;
}

export { modelLabel };
export default SettingsPage;
