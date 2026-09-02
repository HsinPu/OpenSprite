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
  executionPanelDefaultExpanded: false,
};

export type ConversationSettingsController = {
  settings: ConversationSettings;
  loaded: boolean;
  saving: boolean;
  error: string | null;
  saveStartupView: (startupView: StartupView) => Promise<string | null>;
  saveSendBehavior: (sendBehavior: SendBehavior) => Promise<string | null>;
  saveAutoScroll: (autoScroll: boolean) => Promise<string | null>;
  saveExecutionPanelDefaultExpanded: (expanded: boolean) => Promise<string | null>;
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
  const confirmedSettingsRef = useRef<ConversationSettings | null>(null);
  const desiredSettingsRef = useRef<ConversationSettings | null>(null);
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
      confirmedSettingsRef.current = saved;
      desiredSettingsRef.current = saved;
      setLoaded(true);
    } catch (loadError) {
      if (loadGenerationRef.current !== generation) return;
      setError(conversationSettingsErrorText(loadError, translatorRef.current));
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const save = useCallback((update: (current: ConversationSettings) => ConversationSettings): Promise<string | null> => {
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
        const saved = await putConversationSettings(next);
        if (saved.startupView !== next.startupView || saved.sendBehavior !== next.sendBehavior || saved.autoScroll !== next.autoScroll || saved.executionPanelDefaultExpanded !== next.executionPanelDefaultExpanded) throw new Error("conversation_settings_response_mismatch");
        confirmedSettingsRef.current = saved;
        if (saveGenerationRef.current === generation) {
          desiredSettingsRef.current = saved;
          setSettings(saved);
          setLoaded(true);
        }
        return null;
      } catch (saveError) {
        const message = conversationSettingsErrorText(saveError, t);
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

  const saveStartupView = useCallback((startupView: StartupView) => save((current) => ({ ...current, startupView })), [save]);
  const saveSendBehavior = useCallback((sendBehavior: SendBehavior) => save((current) => ({ ...current, sendBehavior })), [save]);
  const saveAutoScroll = useCallback((autoScroll: boolean) => save((current) => ({ ...current, autoScroll })), [save]);
  const saveExecutionPanelDefaultExpanded = useCallback((executionPanelDefaultExpanded: boolean) => save((current) => ({ ...current, executionPanelDefaultExpanded })), [save]);

  return {
    settings,
    loaded,
    saving,
    error,
    saveStartupView,
    saveSendBehavior,
    saveAutoScroll,
    saveExecutionPanelDefaultExpanded,
    reload,
  };
}
