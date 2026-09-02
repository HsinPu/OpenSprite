import { useCallback, useEffect, useRef, useState } from "react";

import {
  getToolCatalog,
  getToolSettings,
  putToolSettings,
  toolSettingsErrorText,
  type ToolCatalog,
  type ToolSettings,
} from "../../api/toolSettings";
import { useI18n } from "../../i18n/I18nProvider";


const defaults: ToolSettings = { enabled: true, enabledTools: ["calculator"] };

export type ToolSettingsController = {
  catalog: ToolCatalog | null;
  settings: ToolSettings;
  loaded: boolean;
  saving: boolean;
  error: string | null;
  saveEnabled: (enabled: boolean) => Promise<string | null>;
  saveToolEnabled: (toolId: string, enabled: boolean) => Promise<string | null>;
  reload: () => Promise<void>;
};

export function useToolSettings(): ToolSettingsController {
  const { t } = useI18n();
  const [catalog, setCatalog] = useState<ToolCatalog | null>(null);
  const [settings, setSettings] = useState<ToolSettings>(defaults);
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loadGenerationRef = useRef(0);
  const saveGenerationRef = useRef(0);
  const saveQueueRef = useRef(Promise.resolve());
  const confirmedSettingsRef = useRef<ToolSettings | null>(null);
  const desiredSettingsRef = useRef<ToolSettings | null>(null);
  const translatorRef = useRef(t);

  useEffect(() => { translatorRef.current = t; }, [t]);

  const reload = useCallback(async (): Promise<void> => {
    const generation = loadGenerationRef.current + 1;
    loadGenerationRef.current = generation;
    setLoaded(false);
    setError(null);
    try {
      const [nextCatalog, saved] = await Promise.all([getToolCatalog(), getToolSettings()]);
      if (loadGenerationRef.current !== generation) return;
      const available = new Set(nextCatalog.items.filter((item) => item.available).map((item) => item.id));
      if (saved.enabledTools.some((toolId) => !available.has(toolId))) throw new Error("tool_settings_catalog_mismatch");
      setCatalog(nextCatalog);
      setSettings(saved);
      confirmedSettingsRef.current = saved;
      desiredSettingsRef.current = saved;
      setLoaded(true);
    } catch (loadError) {
      if (loadGenerationRef.current !== generation) return;
      setError(toolSettingsErrorText(loadError, translatorRef.current));
    }
  }, []);

  useEffect(() => { void reload(); }, [reload]);

  const save = useCallback((update: (current: ToolSettings) => ToolSettings): Promise<string | null> => {
    const current = desiredSettingsRef.current ?? settings;
    const next = update(current);
    desiredSettingsRef.current = next;
    loadGenerationRef.current += 1;
    const generation = saveGenerationRef.current + 1;
    saveGenerationRef.current = generation;
    setSaving(true);
    setError(null);
    const operation = saveQueueRef.current.then(async () => {
      try {
        const saved = await putToolSettings(next);
        if (saved.enabled !== next.enabled || saved.enabledTools.join("\0") !== [...next.enabledTools].sort().join("\0")) throw new Error("tool_settings_response_mismatch");
        confirmedSettingsRef.current = saved;
        if (saveGenerationRef.current === generation) {
          desiredSettingsRef.current = saved;
          setSettings(saved);
          setLoaded(true);
        }
        return null;
      } catch (saveError) {
        const message = toolSettingsErrorText(saveError, t);
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
  }, [settings, t]);

  const saveEnabled = useCallback((enabled: boolean) => save((current) => ({ ...current, enabled })), [save]);
  const saveToolEnabled = useCallback((toolId: string, enabled: boolean) => save((current) => {
    const enabledTools = new Set(current.enabledTools);
    if (enabled) enabledTools.add(toolId);
    else enabledTools.delete(toolId);
    return { ...current, enabledTools: [...enabledTools].sort() };
  }), [save]);

  return { catalog, settings, loaded, saving, error, saveEnabled, saveToolEnabled, reload };
}
