import { useCallback, useEffect, useRef, useState } from "react";

import {
  conversationSettingsErrorText,
  getConversationSettings,
  putConversationSettings,
  type ConversationSettings,
  type SendBehavior,
  type StartupView,
} from "../../api/conversationSettings";
import { useI18n } from "../../i18n/I18nProvider";


const defaults: ConversationSettings = {
  startupView: "new",
  sendBehavior: "enter",
  autoScroll: true,
};

export type ConversationSettingsController = {
  settings: ConversationSettings;
  loaded: boolean;
  saving: boolean;
  error: string | null;
  saveStartupView: (startupView: StartupView) => Promise<string | null>;
  saveSendBehavior: (sendBehavior: SendBehavior) => Promise<string | null>;
  saveAutoScroll: (autoScroll: boolean) => Promise<string | null>;
  reload: () => Promise<void>;
};

export function useConversationSettings(): ConversationSettingsController {
  const { t } = useI18n();
  const [settings, setSettings] = useState<ConversationSettings>(defaults);
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
      const saved = await getConversationSettings();
      if (loadGenerationRef.current !== generation) return;
      setSettings(saved);
      setLoaded(true);
    } catch (loadError) {
      if (loadGenerationRef.current !== generation) return;
      setError(conversationSettingsErrorText(loadError, translatorRef.current));
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const save = useCallback((next: ConversationSettings): Promise<string | null> => {
    loadGenerationRef.current += 1;
    const generation = saveGenerationRef.current + 1;
    saveGenerationRef.current = generation;
    setSaving(true);
    setError(null);
    const operation = saveQueueRef.current.then(async () => {
      try {
        const saved = await putConversationSettings(next);
        if (saved.startupView !== next.startupView || saved.sendBehavior !== next.sendBehavior || saved.autoScroll !== next.autoScroll) throw new Error("conversation_settings_response_mismatch");
        if (saveGenerationRef.current === generation) {
          setSettings(saved);
          setLoaded(true);
        }
        return null;
      } catch (saveError) {
        const message = conversationSettingsErrorText(saveError, t);
        if (saveGenerationRef.current === generation) setError(message);
        return message;
      } finally {
        if (saveGenerationRef.current === generation) setSaving(false);
      }
    });
    saveQueueRef.current = operation.then(() => undefined, () => undefined);
    return operation;
  }, [t]);

  const saveStartupView = useCallback((startupView: StartupView) => save({ ...settings, startupView }), [save, settings]);
  const saveSendBehavior = useCallback((sendBehavior: SendBehavior) => save({ ...settings, sendBehavior }), [save, settings]);
  const saveAutoScroll = useCallback((autoScroll: boolean) => save({ ...settings, autoScroll }), [save, settings]);

  return {
    settings,
    loaded,
    saving,
    error,
    saveStartupView,
    saveSendBehavior,
    saveAutoScroll,
    reload,
  };
}
