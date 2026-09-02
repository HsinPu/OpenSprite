import { useCallback, useEffect, useRef, useState } from "react";

import {
  aiSettingsErrorText,
  getAiSettings,
  putAiSettings,
  type AiSettings,
  type OutputContinuation,
  type ResponseDelivery,
  type ResponseMode,
} from "../../api/aiSettings";
import type { ProviderSummary } from "../../api/providerConnections";
import { useI18n } from "../../i18n/I18nProvider";
import {
  type ModelChoice,
  type ModelSelection,
} from "./modelCatalog";

export function useAiSettings(
  providers: ReadonlyArray<ProviderSummary> | null,
  modelChoices: ReadonlyArray<ModelChoice>,
) {
  const { t } = useI18n();
  const [modelSelection, setModelSelection] = useState<ModelSelection | null>(null);
  const [responseMode, setResponseMode] = useState<ResponseMode>("default");
  const [outputContinuation, setOutputContinuation] = useState<OutputContinuation>("2");
  const [responseDelivery, setResponseDelivery] = useState<ResponseDelivery>("stream");
  const [logFullPrompts, setLogFullPrompts] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loadGenerationRef = useRef(0);
  const saveGenerationRef = useRef(0);
  const saveQueueRef = useRef(Promise.resolve());
  const confirmedSettingsRef = useRef<AiSettings | null>(null);
  const desiredSettingsRef = useRef<AiSettings | null>(null);
  const translatorRef = useRef(t);

  useEffect(() => {
    translatorRef.current = t;
  }, [t]);

  const reload = useCallback(async (): Promise<void> => {
    const generation = loadGenerationRef.current + 1;
    loadGenerationRef.current = generation;
    setLoaded(false);
    setError(null);
    try {
      const savedSettings = await getAiSettings();
      if (loadGenerationRef.current !== generation) return;
      setModelSelection(savedSettings.model);
      setResponseMode(savedSettings.responseMode);
      setOutputContinuation(savedSettings.outputContinuation);
      setResponseDelivery(savedSettings.responseDelivery);
      setLogFullPrompts(savedSettings.logFullPrompts);
      confirmedSettingsRef.current = savedSettings;
      desiredSettingsRef.current = savedSettings;
      setLoaded(true);
      setError(null);
    } catch (loadError: unknown) {
      if (loadGenerationRef.current !== generation) return;
      setLoaded(false);
      setError(aiSettingsErrorText(loadError, translatorRef.current));
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const save = useCallback((update: (current: AiSettings) => AiSettings): Promise<string | null> => {
    const current = desiredSettingsRef.current ?? {
      model: modelSelection,
      responseMode,
      outputContinuation,
      responseDelivery,
      logFullPrompts,
    };
    const next = update(current);
    desiredSettingsRef.current = next;
    loadGenerationRef.current += 1;
    const generation = saveGenerationRef.current + 1;
    saveGenerationRef.current = generation;
    setSaving(true);
    setError(null);
    const operation = saveQueueRef.current.then(async () => {
      try {
        const saved = await putAiSettings(next);
        if ((saved.model?.providerId ?? null) !== (next.model?.providerId ?? null)
          || (saved.model?.modelId ?? null) !== (next.model?.modelId ?? null)
          || (saved.model?.contextBudget ?? null) !== (next.model?.contextBudget ?? null)
          || (saved.model?.outputBudget ?? null) !== (next.model?.outputBudget ?? null)
          || saved.responseMode !== next.responseMode
          || saved.outputContinuation !== next.outputContinuation
          || saved.responseDelivery !== next.responseDelivery) {
          throw new Error("ai_settings_response_mismatch");
        }
        if (saved.logFullPrompts !== next.logFullPrompts) {
          throw new Error("ai_settings_response_mismatch");
        }
        confirmedSettingsRef.current = saved;
        if (saveGenerationRef.current === generation) {
          desiredSettingsRef.current = saved;
          setModelSelection(saved.model);
          setResponseMode(saved.responseMode);
          setOutputContinuation(saved.outputContinuation);
          setResponseDelivery(saved.responseDelivery);
          setLogFullPrompts(saved.logFullPrompts);
          setError(null);
        }
        return null;
      } catch (saveError) {
        const message = aiSettingsErrorText(saveError, t);
        if (saveGenerationRef.current === generation) {
          desiredSettingsRef.current = confirmedSettingsRef.current;
          setError(message);
        }
        return message;
      } finally {
        if (saveGenerationRef.current === generation) setSaving(false);
      }
    });
    saveQueueRef.current = operation.then(() => undefined, () => undefined);
    return operation;
  }, [logFullPrompts, modelSelection, outputContinuation, responseDelivery, responseMode, t]);

  const saveModelSelection = useCallback(
    (next: ModelSelection | null) => save((current) => ({ ...current, model: next })),
    [save],
  );
  const saveResponseMode = useCallback(
    (next: ResponseMode) => save((current) => ({ ...current, responseMode: next })),
    [save],
  );
  const saveOutputContinuation = useCallback(
    (next: OutputContinuation) => save((current) => ({ ...current, outputContinuation: next })),
    [save],
  );
  const saveResponseDelivery = useCallback(
    (next: ResponseDelivery) => save((current) => ({ ...current, responseDelivery: next })),
    [save],
  );
  const saveLogFullPrompts = useCallback(
    (next: boolean) => save((current) => ({ ...current, logFullPrompts: next })),
    [save],
  );

  useEffect(() => {
    if (!loaded || providers === null || saving) return;
    const connectedProviders = providers.filter((provider) => provider.connected);
    if (modelSelection?.providerId === "openrouter") return;
    const selectionIsAvailable = modelSelection !== null
      && modelChoices.some((choice) => choice.selection.providerId === modelSelection.providerId
        && choice.selection.modelId === modelSelection.modelId);
    if (selectionIsAvailable) return;
    const fallback = modelChoices[0];
    if (fallback) {
      void saveModelSelection(fallback.selection);
    } else if (modelSelection !== null && connectedProviders.length === 0) {
      void saveModelSelection(null);
    }
  }, [loaded, modelChoices, modelSelection, providers, saveModelSelection, saving]);

  return {
    modelSelection,
    responseMode,
    outputContinuation,
    responseDelivery,
    logFullPrompts,
    loaded,
    saving,
    error,
    reload,
    saveModelSelection,
    saveResponseMode,
    saveOutputContinuation,
    saveResponseDelivery,
    saveLogFullPrompts,
  };
}
