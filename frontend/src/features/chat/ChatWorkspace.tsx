import { FormEvent, KeyboardEvent, useLayoutEffect, useRef, useState } from "react";

import { AgentChatApiError, agentChatErrorText } from "../../api/agentChat";
import type { ModelChoice, ModelSelection } from "../ai-settings/modelCatalog";
import type { TimeZoneSetting } from "../../api/generalSettings";
import type { SendBehavior } from "../../api/conversationSettings";
import { useI18n } from "../../i18n/I18nProvider";
import { formatMessageTime } from "../general-settings/dateTime";
import { ExecutionContext } from "./ExecutionContext";
import { useConversationRun } from "./useConversationRun";

import "./ChatWorkspace.css";


type ChatWorkspaceProps = {
  conversationId: string | null;
  modelName: string;
  modelSelection: ModelSelection | null;
  modelChoices: ReadonlyArray<ModelChoice>;
  modelSelectionSaving: boolean;
  timeZone: TimeZoneSetting;
  sendBehavior: SendBehavior;
  onModelSelectionChange: (selection: ModelSelection) => Promise<string | null>;
  onConversationAccepted: (conversationId: string, firstMessage: string) => void;
  onConversationUpdated: () => void;
  title?: string;
};


function OpenSpriteMark({ small = false }: { small?: boolean }) {
  return <span aria-hidden="true" className={`chat-workspace__mark${small ? " chat-workspace__mark--small" : ""}`} />;
}


function SendIcon() {
  return (
    <svg aria-hidden="true" focusable="false" viewBox="0 0 24 24">
      <path d="M12 19V5M6.5 10.5 12 5l5.5 5.5" />
    </svg>
  );
}


function StopIcon() {
  return (
    <svg aria-hidden="true" focusable="false" viewBox="0 0 24 24">
      <rect x="7" y="7" width="10" height="10" rx="2" />
    </svg>
  );
}


export function ChatWorkspace({
  conversationId,
  modelName,
  modelSelection,
  modelChoices,
  modelSelectionSaving,
  timeZone,
  sendBehavior,
  onModelSelectionChange,
  onConversationAccepted,
  onConversationUpdated,
  title,
}: ChatWorkspaceProps) {
  const { locale, t } = useI18n();
  const [draft, setDraft] = useState("");
  const composerInputRef = useRef<HTMLTextAreaElement>(null);
  const chat = useConversationRun({
    conversationId,
    onConversationAccepted,
    onConversationUpdated,
  });
  const currentSelectionValue = modelSelection ? JSON.stringify([modelSelection.providerId, modelSelection.modelId]) : "";
  const currentSelectionIsAvailable = modelSelection !== null && modelChoices.some((choice) => choice.selection.providerId === modelSelection.providerId && choice.selection.modelId === modelSelection.modelId);
  const choicesByProvider = ["openai", "anthropic", "openrouter"].map((providerId) => ({
    providerId,
    label: providerId === "openai" ? "OpenAI" : providerId === "anthropic" ? "Anthropic" : "OpenRouter",
    choices: modelChoices.filter((choice) => choice.selection.providerId === providerId),
  })).filter((group) => group.choices.length > 0);
  const liveText = chat.streamedText || chat.activeRun?.partialText || "";
  const hasDurableAssistant = chat.activeRun?.assistantMessageId !== null
    && chat.activeRun?.assistantMessageId !== undefined
    && chat.messages.some((message) => message.id === chat.activeRun?.assistantMessageId);
  const showLiveAssistant = chat.isRunning
    || (chat.activeRun?.status === "completed" && Boolean(liveText) && !hasDurableAssistant);
  const showTerminalNotice = chat.activeRun !== null && ["failed", "cancelled", "interrupted"].includes(chat.activeRun.status);
  const canSend = Boolean(draft.trim() && modelSelection && !modelSelectionSaving && !chat.loading);

  useLayoutEffect(() => {
    const input = composerInputRef.current;
    if (!input) return;
    input.style.height = "0px";
    input.style.height = `${Math.min(Math.max(input.scrollHeight, 36), 144)}px`;
  }, [draft]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const content = draft.trim();
    if (!content || chat.isRunning || !modelSelection) return;
    setDraft("");
    void chat.send(content);
  };

  const handleComposerKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.nativeEvent.isComposing) return;
    const shouldSend = sendBehavior === "enter"
      ? !event.shiftKey
      : !event.shiftKey && (event.ctrlKey || event.metaKey);
    if (!shouldSend) return;
    event.preventDefault();
    event.currentTarget.form?.requestSubmit();
  };

  return (
    <section className="chat-workspace" aria-label={t("chat.workspace")}>
      <div className="chat-workspace__main">
        <header className="chat-workspace__header">
          <h1>{title ?? t("app.newConversationTitle")}</h1>
        </header>

        <div className="chat-workspace__conversation" aria-live="polite" aria-busy={chat.loading || chat.isRunning}>
          <div className="chat-workspace__conversation-rail">
            {chat.error ? <div className="chat-workspace__error" role="alert">{chat.error}</div> : null}
            {chat.loading ? <div className="chat-workspace__loading">{t("chat.loadingConversation")}</div> : null}
            {chat.hasOlderMessages ? (
              <button
                type="button"
                className="chat-workspace__load-older"
                disabled={chat.loadingOlderMessages}
                onClick={() => void chat.loadOlderMessages()}
              >
                {chat.loadingOlderMessages
                  ? t("chat.loadingOlderMessages")
                  : t("chat.loadOlderMessages")}
              </button>
            ) : null}
            {!chat.loading && chat.messages.length === 0 && !showLiveAssistant ? (
              <div className="chat-workspace__empty-state">
                <OpenSpriteMark />
                <h2>{t("chat.emptyTitle")}</h2>
                <p>{t("chat.emptyDescription")}</p>
              </div>
            ) : null}
            {chat.messages.map((message) => message.role === "user" ? (
              <div className="chat-workspace__user-row" key={message.id}>
                <div>
                  <p className="chat-workspace__user-message">{message.content}</p>
                  <div className="chat-workspace__message-meta">
                    <time className="chat-workspace__message-time" dateTime={message.createdAt}>{formatMessageTime(message.createdAt, locale, timeZone)}</time>
                    {message.delivery === "sending" ? <span className="chat-workspace__delivery">{t("chat.sending")}</span> : null}
                    {message.delivery === "failed" ? <span className="chat-workspace__delivery chat-workspace__delivery--failed">{t("chat.sendFailed")}</span> : null}
                  </div>
                </div>
              </div>
            ) : (
              <div className="chat-workspace__assistant-row" key={message.id}>
                <OpenSpriteMark />
                <div className="chat-workspace__assistant-content">
                  <div className="chat-workspace__assistant-card chat-workspace__assistant-card--compact"><p>{message.content}</p></div>
                  <time className="chat-workspace__message-time" dateTime={message.createdAt}>{formatMessageTime(message.createdAt, locale, timeZone)}</time>
                </div>
              </div>
            ))}
            {showLiveAssistant ? (
              <div className="chat-workspace__assistant-row" data-testid="streaming-assistant">
                <OpenSpriteMark />
                <div className="chat-workspace__assistant-content">
                  <div className={`chat-workspace__assistant-card chat-workspace__assistant-card--compact${chat.isRunning ? " chat-workspace__assistant-card--streaming" : ""}`}>
                    {liveText ? <p>{liveText}</p> : <p className="chat-workspace__thinking"><span aria-hidden="true" />{t("chat.thinking")}</p>}
                  </div>
                  {chat.activeRun ? <time className="chat-workspace__message-time" dateTime={chat.activeRun.createdAt}>{formatMessageTime(chat.activeRun.createdAt, locale, timeZone)}</time> : null}
                </div>
              </div>
            ) : null}
            {showTerminalNotice ? (
              <div className="chat-workspace__run-notice" role="status">
                {chat.activeRun?.status === "cancelled"
                  ? t("chat.cancelled")
                  : chat.activeRun?.error
                    ? agentChatErrorText(new AgentChatApiError(chat.activeRun.error.code), t)
                    : t("chat.incomplete")}
              </div>
            ) : null}
          </div>
        </div>

        <form className="chat-workspace__composer" onSubmit={handleSubmit}>
          <label htmlFor="chat-message" className="chat-workspace__composer-label">{t("chat.inputLabel")}</label>
          <textarea
            id="chat-message"
            ref={composerInputRef}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleComposerKeyDown}
            placeholder={modelSelection ? t("chat.inputPlaceholder") : t("chat.selectModelPlaceholder")}
            rows={1}
            disabled={chat.isRunning}
          />
          <div className="chat-workspace__composer-actions">
            <div>
              <button type="button" className="chat-workspace__tool-button" disabled title={t("chat.attachmentTitle")} aria-label={t("chat.attachmentLabel")}>⌕</button>
              <button type="button" className="chat-workspace__tool-button" disabled title={t("chat.optionsTitle")} aria-label={t("chat.optionsLabel")}>☷</button>
            </div>
            <div className="chat-workspace__composer-primary-actions">
              <select
                className="chat-workspace__model-select chat-workspace__model-select--composer"
                disabled={modelChoices.length === 0 || modelSelectionSaving || chat.isRunning}
                title={modelChoices.length === 0 ? t("chat.modelNoChoicesTitle") : currentSelectionIsAvailable ? t("chat.modelSwitchTitle") : t("chat.modelUnavailableTitle")}
                aria-label={modelChoices.length === 0 ? t("chat.modelNoChoicesLabel", { model: modelName }) : currentSelectionIsAvailable ? t("chat.modelSwitchLabel", { model: modelName }) : t("chat.modelUnavailableLabel", { model: modelName })}
                value={currentSelectionValue}
                onChange={(event) => {
                  try {
                    const [providerId, modelId] = JSON.parse(event.target.value) as [ModelSelection["providerId"], string];
                    if (typeof modelId === "string") void onModelSelectionChange({ providerId, modelId });
                  } catch {
                    // Values can only originate from the rendered strict choices.
                  }
                }}
              >
                {modelSelection === null ? <option value="">{t("model.none")}</option> : null}
                {modelSelection !== null && !currentSelectionIsAvailable ? <option value={currentSelectionValue} disabled>{modelName}</option> : null}
                {choicesByProvider.map((group) => (
                  <optgroup key={group.providerId} label={group.label}>
                    {group.choices.map((choice) => <option key={`${choice.selection.providerId}:${choice.selection.modelId}`} value={JSON.stringify([choice.selection.providerId, choice.selection.modelId])}>{choice.label}</option>)}
                  </optgroup>
                ))}
              </select>
              {chat.isRunning ? (
                <button type="button" className="chat-workspace__send-button chat-workspace__send-button--stop" disabled={chat.activeRun?.status === "cancelling"} aria-label={t("chat.stop")} title={t("chat.stop")} onClick={() => void chat.cancel()}><StopIcon /></button>
              ) : (
                <button type="submit" className="chat-workspace__send-button" disabled={!canSend} aria-label={t("chat.send")} title={t("chat.send")}><SendIcon /></button>
              )}
            </div>
          </div>
        </form>
      </div>

      <ExecutionContext modelName={modelName} run={chat.activeRun} events={chat.events} timeZone={timeZone} />
    </section>
  );
}
