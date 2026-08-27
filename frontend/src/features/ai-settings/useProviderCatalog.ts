import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  listOpenRouterModels,
  listProviderConnections,
  providerErrorText,
  type ProviderId,
  type ProviderSummary,
} from "../../api/providerConnections";
import { useI18n } from "../../i18n/I18nProvider";
import {
  localModelCatalog,
  openRouterModelCatalog,
  type ModelCatalogItem,
  type ModelChoice,
} from "./modelCatalog";

export type ModelLoadStatus = "idle" | "loading" | "success" | "error";

export type ProviderCatalogController = {
  providers: ReadonlyArray<ProviderSummary> | null;
  catalogError: string | null;
  openRouterModels: ReadonlyArray<ModelCatalogItem> | null;
  openRouterModelLoadStatus: ModelLoadStatus;
  openRouterModelError: string | null;
  modelChoices: ReadonlyArray<ModelChoice>;
  refreshProviders: () => Promise<ReadonlyArray<ProviderSummary> | null>;
  readProviderSummary: (providerId: ProviderId) => Promise<ProviderSummary | null>;
  updateProviderSummary: (summary: ProviderSummary) => void;
  loadOpenRouterModels: (force?: boolean) => Promise<void>;
  invalidateOpenRouterModels: () => void;
};

type ActiveLoads = Partial<Record<ProviderId, number>>;

export function useProviderCatalog(): ProviderCatalogController {
  const { t } = useI18n();
  const [providers, setProviders] = useState<ReadonlyArray<ProviderSummary> | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [openRouterModels, setOpenRouterModels] = useState<ReadonlyArray<ModelCatalogItem> | null>(null);
  const [openRouterModelLoadStatus, setOpenRouterModelLoadStatus] = useState<ModelLoadStatus>("idle");
  const [openRouterModelError, setOpenRouterModelError] = useState<string | null>(null);
  const modelGenerationRef = useRef(0);
  const activeModelLoadsRef = useRef<ActiveLoads>({});
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  const refreshProviders = useCallback(async () => {
    setCatalogError(null);
    try {
      const summaries = await listProviderConnections();
      if (mountedRef.current) setProviders(summaries);
      return summaries;
    } catch (requestError) {
      if (mountedRef.current) {
        setProviders(null);
        setCatalogError(providerErrorText(requestError, t));
      }
      return null;
    }
  }, [t]);

  const readProviderSummary = useCallback(async (providerId: ProviderId) => {
    try {
      const summaries = await listProviderConnections();
      return summaries.find((summary) => summary.id === providerId) ?? null;
    } catch {
      return null;
    }
  }, []);

  const loadOpenRouterModels = useCallback(async (force = false) => {
    if (!force && openRouterModels !== null) return;
    if (activeModelLoadsRef.current.openrouter !== undefined) return;
    const generation = modelGenerationRef.current + 1;
    modelGenerationRef.current = generation;
    activeModelLoadsRef.current = { ...activeModelLoadsRef.current, openrouter: generation };
    setOpenRouterModelLoadStatus("loading");
    setOpenRouterModelError(null);
    try {
      const models = await listOpenRouterModels();
      if (mountedRef.current && activeModelLoadsRef.current.openrouter === generation && modelGenerationRef.current === generation) {
        setOpenRouterModels(openRouterModelCatalog(models));
        setOpenRouterModelLoadStatus("success");
        setOpenRouterModelError(null);
      }
    } catch (requestError) {
      if (mountedRef.current && activeModelLoadsRef.current.openrouter === generation && modelGenerationRef.current === generation) {
        setOpenRouterModelLoadStatus("error");
        setOpenRouterModelError(providerErrorText(requestError, t));
      }
    } finally {
      if (activeModelLoadsRef.current.openrouter === generation) {
        const { openrouter: _, ...remaining } = activeModelLoadsRef.current;
        activeModelLoadsRef.current = remaining;
      }
    }
  }, [openRouterModels, t]);

  const invalidateOpenRouterModels = useCallback(() => {
    modelGenerationRef.current += 1;
    const { openrouter: _, ...remaining } = activeModelLoadsRef.current;
    activeModelLoadsRef.current = remaining;
    setOpenRouterModels(null);
    setOpenRouterModelLoadStatus("idle");
    setOpenRouterModelError(null);
  }, []);

  const updateProviderSummary = useCallback((summary: ProviderSummary) => {
    setProviders((current) => current?.map((provider) => provider.id === summary.id ? summary : provider) ?? current);
  }, []);

  useEffect(() => { void refreshProviders(); }, [refreshProviders]);
  useEffect(() => {
    const openRouterConnected = providers?.some((provider) => provider.id === "openrouter" && provider.connected) ?? false;
    if (openRouterConnected && openRouterModels === null && openRouterModelLoadStatus !== "error") void loadOpenRouterModels();
  }, [loadOpenRouterModels, openRouterModelLoadStatus, openRouterModels, providers]);

  const modelChoices = useMemo(() => (providers ?? []).flatMap((provider) => {
    if (!provider.connected) return [];
    const models = provider.id === "openrouter"
      ? (openRouterModelLoadStatus === "success" ? openRouterModels ?? [] : [])
      : localModelCatalog[provider.id];
    return models.map((model) => ({
      selection: { providerId: provider.id, modelId: model.id },
      label: model.label,
    }));
  }), [openRouterModelLoadStatus, openRouterModels, providers]);

  return {
    providers,
    catalogError,
    openRouterModels,
    openRouterModelLoadStatus,
    openRouterModelError,
    modelChoices,
    refreshProviders,
    readProviderSummary,
    updateProviderSummary,
    loadOpenRouterModels,
    invalidateOpenRouterModels,
  };
}
