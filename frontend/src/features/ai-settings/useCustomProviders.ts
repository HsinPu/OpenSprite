import { useCallback, useEffect, useRef, useState } from "react";
import {
  createCustomModel, createCustomProvider, CustomProviderApiError, listCustomProviders,
  refreshCustomModels, type CustomProvider, type ModelDraft, type ProviderDraft,
  updateCustomProvider, deleteCustomProvider, updateCustomModel, deleteCustomModel,
} from "../../api/customProviders";

type Catalog = { revision: number; providers: CustomProvider[] };

export function useCustomProviders(autoLoad = true) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(false);
  const generation = useRef(0);
  const mutation = useRef(false);
  const report = (failure: unknown) => failure instanceof CustomProviderApiError ? failure.code : "network_error";

  const reload = useCallback(async () => {
    const token = ++generation.current;
    setLoading(true);
    setError(null);
    try {
      const result = await listCustomProviders();
      if (mounted.current && token === generation.current) setCatalog(result);
      return result;
    } catch (failure) {
      if (mounted.current && token === generation.current) setError(report(failure));
      return null;
    } finally {
      if (mounted.current && token === generation.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    if (autoLoad) void reload();
    return () => { mounted.current = false; generation.current += 1; };
  }, [autoLoad, reload]);

  const perform = useCallback(async (operation: () => Promise<unknown>): Promise<boolean> => {
    if (mutation.current) return false;
    mutation.current = true;
    generation.current += 1;
    setLoading(false);
    setSaving(true);
    setError(null);
    try {
      await operation();
      // Mutation is committed even when the subsequent refresh fails. The UI
      // must not offer a second submission of the same create operation.
      if (mounted.current) await reload();
      return true;
    } catch (failure) {
      if (mounted.current) setError(report(failure));
      return false;
    } finally {
      mutation.current = false;
      if (mounted.current) setSaving(false);
    }
  }, [reload]);

  const create = (draft: Omit<ProviderDraft, "expectedRevision">) => catalog === null
    ? Promise.resolve(false)
    : perform(() => createCustomProvider({ ...draft, expectedRevision: catalog.revision }));
  const refreshModels = (provider: CustomProvider) => perform(() => refreshCustomModels(provider.id, provider.revision));
  const addModel = (provider: CustomProvider, draft: Omit<ModelDraft, "expectedRevision">) =>
    perform(() => createCustomModel(provider.id, { ...draft, expectedRevision: provider.revision }));
  const update = (provider: CustomProvider, draft: Omit<ProviderDraft, "expectedRevision">) =>
    perform(() => updateCustomProvider(provider.id, { ...draft, expectedRevision: provider.revision }));
  const remove = (provider: CustomProvider) => perform(() => deleteCustomProvider(provider.id, provider.revision));
  const editModel = (provider: CustomProvider, key: string, draft: Omit<ModelDraft, "expectedRevision">) =>
    perform(() => updateCustomModel(provider.id, key, { ...draft, expectedRevision: provider.revision }));
  const removeModel = (provider: CustomProvider, key: string) => perform(() => deleteCustomModel(provider.id, key, provider.revision));
  return { catalog, loading, saving, error, reload, create, update, remove, refreshModels, addModel, editModel, removeModel };
}
