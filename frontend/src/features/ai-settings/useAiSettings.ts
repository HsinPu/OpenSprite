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

  const save = useCallback((next: AiSettings): Promise<string | null> => {
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
        if (saveGenerationRef.current === generation) {
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
        if (saveGenerationRef.current === generation) setError(message);
        return message;
      } finally {
        if (saveGenerationRef.current === generation) setSaving(false);
      }
    });
    saveQueueRef.current = operation.then(() => undefined, () => undefined);
    return operation;
  }, [t]);

  const saveModelSelection = useCallback(
    (next: ModelSelection | null) => save({ model: next, responseMode, outputContinuation, responseDelivery, logFullPrompts }),
    [logFullPrompts, outputContinuation, responseDelivery, responseMode, save],
  );
  const saveResponseMode = useCallback(
    (next: ResponseMode) => save({ model: modelSelection, responseMode: next, outputContinuation, responseDelivery, logFullPrompts }),
    [logFullPrompts, modelSelection, outputContinuation, responseDelivery, save],
  );
  const saveOutputContinuation = useCallback(
    (next: OutputContinuation) => save({ model: modelSelection, responseMode, outputContinuation: next, responseDelivery, logFullPrompts }),
    [logFullPrompts, modelSelection, responseDelivery, responseMode, save],
  );
  const saveResponseDelivery = useCallback(
    (next: ResponseDelivery) => save({ model: modelSelection, responseMode, outputContinuation, responseDelivery: next, logFullPrompts }),
    [logFullPrompts, modelSelection, outputContinuation, responseMode, save],
  );
  const saveLogFullPrompts = useCallback(
    (next: boolean) => save({ model: modelSelection, responseMode, outputContinuation, responseDelivery, logFullPrompts: next }),
    [modelSelection, outputContinuation, responseDelivery, responseMode, save],
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
