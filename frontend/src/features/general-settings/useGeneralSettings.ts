import { useCallback, useEffect, useRef, useState } from "react";

import {
  generalSettingsErrorText,
  getGeneralSettings,
  putGeneralSettings,
  type GeneralSettings,
  type TimeZoneSetting,
} from "../../api/generalSettings";
import type { Locale } from "../../i18n/catalog";
import { useI18n } from "../../i18n/I18nProvider";

const defaults: GeneralSettings = { locale: "zh-TW", timeZone: "system" };

export type GeneralSettingsController = {
  settings: GeneralSettings;
  loaded: boolean;
  saving: boolean;
  error: string | null;
  saveLocale: (locale: Locale) => Promise<string | null>;
  saveTimeZone: (timeZone: TimeZoneSetting) => Promise<string | null>;
  reload: () => Promise<void>;
};

export function useGeneralSettings(): GeneralSettingsController {
  const { setLocale, t } = useI18n();
  const [settings, setSettings] = useState<GeneralSettings>(defaults);
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loadGenerationRef = useRef(0);
  const saveGenerationRef = useRef(0);
  const saveQueueRef = useRef(Promise.resolve());
  const confirmedSettingsRef = useRef<GeneralSettings | null>(null);
  const desiredSettingsRef = useRef<GeneralSettings | null>(null);
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
      const saved = await getGeneralSettings();
      if (loadGenerationRef.current !== generation) return;
      setSettings(saved);
      setLocale(saved.locale);
      confirmedSettingsRef.current = saved;
      desiredSettingsRef.current = saved;
      setLoaded(true);
      setError(null);
    } catch (loadError) {
      if (loadGenerationRef.current !== generation) return;
      setLoaded(false);
      setError(generalSettingsErrorText(loadError, translatorRef.current));
    }
  }, [setLocale]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const save = useCallback((update: (current: GeneralSettings) => GeneralSettings): Promise<string | null> => {
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
        const saved = await putGeneralSettings(next);
        if (saved.locale !== next.locale || saved.timeZone !== next.timeZone) throw new Error("general_settings_response_mismatch");
        confirmedSettingsRef.current = saved;
        if (saveGenerationRef.current === generation) {
          desiredSettingsRef.current = saved;
          setSettings(saved);
          setLocale(saved.locale);
          setLoaded(true);
          setError(null);
        }
        return null;
      } catch (saveError) {
        const message = generalSettingsErrorText(saveError, t);
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

  const saveLocale = useCallback((locale: Locale) => save((current) => ({ ...current, locale })), [save]);
  const saveTimeZone = useCallback((timeZone: TimeZoneSetting) => save((current) => ({ ...current, timeZone })), [save]);

  return { settings, loaded, saving, error, saveLocale, saveTimeZone, reload };
}
