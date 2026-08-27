import { useCallback, useEffect, useRef, useState } from "react";

import {
  aiSettingsErrorText,
  getAiSettings,
  putAiSettings,
  type AiSettings,
  type ResponseMode,
} from "../../api/aiSettings";
import {
  listProviderConnections,
  type ProviderSummary,
} from "../../api/providerConnections";
import {
  localModelCatalog,
  type ModelChoice,
  type ModelSelection,
} from "./modelCatalog";

function staticModelChoices(providers: ReadonlyArray<ProviderSummary>): ReadonlyArray<ModelChoice> {
  return providers.flatMap((provider) => provider.connected
    ? localModelCatalog[provider.id].map((model) => ({
      selection: { providerId: provider.id, modelId: model.id },
      label: model.label,
    }))
    : []);
}

export function useAiSettings() {
  const [modelSelection, setModelSelection] = useState<ModelSelection | null>(null);
  const [responseMode, setResponseMode] = useState<ResponseMode>("default");
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [modelChoices, setModelChoices] = useState<ReadonlyArray<ModelChoice>>([]);
  const [providerCatalog, setProviderCatalog] = useState<ReadonlyArray<ProviderSummary> | null>(null);
  const loadGenerationRef = useRef(0);
  const saveGenerationRef = useRef(0);
  const saveQueueRef = useRef(Promise.resolve());

  useEffect(() => {
    const generation = loadGenerationRef.current + 1;
    loadGenerationRef.current = generation;
    void getAiSettings()
      .then((savedSettings) => {
        if (loadGenerationRef.current !== generation) return;
        setModelSelection(savedSettings.model);
        setResponseMode(savedSettings.responseMode);
        setLoaded(true);
        setError(null);
      })
      .catch((loadError: unknown) => {
        if (loadGenerationRef.current !== generation) return;
        setLoaded(false);
        setError(aiSettingsErrorText(loadError));
      });

    void listProviderConnections()
      .then((providers) => {
        setProviderCatalog(providers);
        setModelChoices(staticModelChoices(providers));
      })
      .catch(() => {
        setProviderCatalog(null);
        setModelChoices([]);
      });
  }, []);

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
          || saved.responseMode !== next.responseMode) {
          throw new Error("ai_settings_response_mismatch");
        }
        if (saveGenerationRef.current === generation) {
          setModelSelection(saved.model);
          setResponseMode(saved.responseMode);
          setError(null);
        }
        return null;
      } catch (saveError) {
        const message = aiSettingsErrorText(saveError);
        if (saveGenerationRef.current === generation) setError(message);
        return message;
      } finally {
        if (saveGenerationRef.current === generation) setSaving(false);
      }
    });
    saveQueueRef.current = operation.then(() => undefined, () => undefined);
    return operation;
  }, []);

  const saveModelSelection = useCallback(
    (next: ModelSelection | null) => save({ model: next, responseMode }),
    [responseMode, save],
  );
  const saveResponseMode = useCallback(
    (next: ResponseMode) => save({ model: modelSelection, responseMode: next }),
    [modelSelection, save],
  );

  useEffect(() => {
    if (!loaded || providerCatalog === null || saving) return;
    const connectedProviders = providerCatalog.filter((provider) => provider.connected);
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
  }, [loaded, modelChoices, modelSelection, providerCatalog, saveModelSelection, saving]);

  return {
    modelSelection,
    responseMode,
    saving,
    error,
    modelChoices,
    setModelChoices,
    saveModelSelection,
    saveResponseMode,
  };
}
