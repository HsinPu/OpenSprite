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

  useEffect(() => {
    const generation = loadGenerationRef.current + 1;
    loadGenerationRef.current = generation;
    void getGeneralSettings()
      .then((saved) => {
        if (loadGenerationRef.current !== generation) return;
        setSettings(saved);
        setLocale(saved.locale);
        setLoaded(true);
        setError(null);
      })
      .catch((loadError: unknown) => {
        if (loadGenerationRef.current !== generation) return;
        setLoaded(false);
        setError(generalSettingsErrorText(loadError, t));
      });
  }, []);

  const save = useCallback((next: GeneralSettings): Promise<string | null> => {
    loadGenerationRef.current += 1;
    const generation = saveGenerationRef.current + 1;
    saveGenerationRef.current = generation;
    setSaving(true);
    setError(null);
    const operation = saveQueueRef.current.then(async () => {
      try {
        const saved = await putGeneralSettings(next);
        if (saved.locale !== next.locale || saved.timeZone !== next.timeZone) throw new Error("general_settings_response_mismatch");
        if (saveGenerationRef.current === generation) {
          setSettings(saved);
          setLocale(saved.locale);
          setLoaded(true);
          setError(null);
        }
        return null;
      } catch (saveError) {
        const message = generalSettingsErrorText(saveError, t);
        if (saveGenerationRef.current === generation) setError(message);
        return message;
      } finally {
        if (saveGenerationRef.current === generation) setSaving(false);
      }
    });
    saveQueueRef.current = operation.then(() => undefined, () => undefined);
    return operation;
  }, [setLocale, t]);

  const saveLocale = useCallback((locale: Locale) => save({ ...settings, locale }), [save, settings]);
  const saveTimeZone = useCallback((timeZone: TimeZoneSetting) => save({ ...settings, timeZone }), [save, settings]);

  return { settings, loaded, saving, error, saveLocale, saveTimeZone };
}
