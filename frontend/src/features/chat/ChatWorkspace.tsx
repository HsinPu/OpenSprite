import { FormEvent, useState } from "react";

import type { ModelChoice, ModelSelection } from "../settings/modelCatalog";
import { ExecutionContext } from "./ExecutionContext";
import { useConversationRun } from "./useConversationRun";

import "./ChatWorkspace.css";


type ChatWorkspaceProps = {
  conversationId: string | null;
  modelName: string;
  modelSelection: ModelSelection | null;
  modelChoices: ReadonlyArray<ModelChoice>;
  modelSelectionSaving: boolean;
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
  onModelSelectionChange,
  onConversationAccepted,
  onConversationUpdated,
  title = "新對話",
}: ChatWorkspaceProps) {
  const [draft, setDraft] = useState("");
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

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const content = draft.trim();
    if (!content || chat.isRunning || !modelSelection) return;
    setDraft("");
    void chat.send(content);
  };

  return (
    <section className="chat-workspace" aria-label="AI 對話工作台">
      <div className="chat-workspace__main">
        <header className="chat-workspace__header">
          <h1>{title}</h1>
          <div className="chat-workspace__header-actions">
            <select
              className="chat-workspace__model-select"
              disabled={modelChoices.length === 0 || modelSelectionSaving || chat.isRunning}
              title={modelChoices.length === 0 ? "尚無可切換的模型；請先在設定中連接模型廠家。" : currentSelectionIsAvailable ? "切換後續訊息使用的模型" : "目前模型未出現在清單中。"}
              aria-label={modelChoices.length === 0 ? `目前模型 ${modelName}，沒有其他可切換模型` : currentSelectionIsAvailable ? `目前模型 ${modelName}，切換後續訊息使用的模型` : `目前模型 ${modelName} 未出現在清單中`}
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
              {modelSelection === null ? <option value="">尚未選擇模型</option> : null}
              {modelSelection !== null && !currentSelectionIsAvailable ? <option value={currentSelectionValue} disabled>{modelName}</option> : null}
              {choicesByProvider.map((group) => (
                <optgroup key={group.providerId} label={group.label}>
                  {group.choices.map((choice) => <option key={`${choice.selection.providerId}:${choice.selection.modelId}`} value={JSON.stringify([choice.selection.providerId, choice.selection.modelId])}>{choice.label}</option>)}
                </optgroup>
              ))}
            </select>
            <span className="chat-workspace__local-status"><i aria-hidden="true" />本機 Agent</span>
            <button type="button" className="chat-workspace__icon-button" disabled title="更多對話功能尚未上線" aria-label="更多對話功能（尚未上線）">⋮</button>
          </div>
        </header>

        <div className="chat-workspace__conversation" aria-live="polite" aria-busy={chat.loading || chat.isRunning}>
          {chat.error ? <div className="chat-workspace__error" role="alert">{chat.error}</div> : null}
          {chat.loading ? <div className="chat-workspace__loading">正在讀取對話…</div> : null}
          {!chat.loading && chat.messages.length === 0 && !showLiveAssistant ? (
            <div className="chat-workspace__empty-state">
              <OpenSpriteMark />
              <h2>今天想完成什麼？</h2>
              <p>輸入一件想處理的事，OpenSprite 會建立對話並開始執行。</p>
            </div>
          ) : null}
          {chat.messages.map((message) => message.role === "user" ? (
            <div className="chat-workspace__user-row" key={message.id}>
              <div>
                <p className="chat-workspace__user-message">{message.content}</p>
                {message.delivery === "sending" ? <span className="chat-workspace__delivery">正在送出…</span> : null}
                {message.delivery === "failed" ? <span className="chat-workspace__delivery chat-workspace__delivery--failed">未能送出，訊息仍保留在畫面上。</span> : null}
              </div>
              <span className="chat-workspace__user-avatar" aria-hidden="true">♙</span>
            </div>
          ) : (
            <div className="chat-workspace__assistant-row" key={message.id}>
              <OpenSpriteMark />
              <div className="chat-workspace__assistant-card chat-workspace__assistant-card--compact"><p>{message.content}</p></div>
            </div>
          ))}
          {showLiveAssistant ? (
            <div className="chat-workspace__assistant-row" data-testid="streaming-assistant">
              <OpenSpriteMark />
              <div className={`chat-workspace__assistant-card chat-workspace__assistant-card--compact${chat.isRunning ? " chat-workspace__assistant-card--streaming" : ""}`}>
                {liveText ? <p>{liveText}</p> : <p className="chat-workspace__thinking"><span aria-hidden="true" />正在準備回覆…</p>}
              </div>
            </div>
          ) : null}
          {showTerminalNotice ? (
            <div className="chat-workspace__run-notice" role="status">
              {chat.activeRun?.status === "cancelled" ? "這次執行已停止。" : chat.activeRun?.error?.message ?? "這次執行未完成。"}
            </div>
          ) : null}
        </div>

        <form className="chat-workspace__composer" onSubmit={handleSubmit}>
          <label htmlFor="chat-message" className="chat-workspace__composer-label">輸入訊息</label>
          <textarea
            id="chat-message"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={modelSelection ? "輸入訊息，或描述你想完成的事..." : "請先在設定中選擇 AI 模型"}
            rows={2}
            disabled={chat.isRunning}
          />
          <div className="chat-workspace__composer-actions">
            <div>
              <button type="button" className="chat-workspace__tool-button" disabled title="附件功能尚未上線" aria-label="附加檔案（尚未上線）">⌕</button>
              <button type="button" className="chat-workspace__tool-button" disabled title="訊息選項尚未上線" aria-label="訊息選項（尚未上線）">☷</button>
            </div>
            {chat.isRunning ? (
              <button type="button" className="chat-workspace__send-button chat-workspace__send-button--stop" disabled={chat.activeRun?.status === "cancelling"} aria-label="停止回覆" title="停止回覆" onClick={() => void chat.cancel()}><StopIcon /></button>
            ) : (
              <button type="submit" className="chat-workspace__send-button" disabled={!canSend} aria-label="送出訊息" title="送出訊息"><SendIcon /></button>
            )}
          </div>
        </form>
      </div>

      <ExecutionContext modelName={modelName} run={chat.activeRun} events={chat.events} />
    </section>
  );
}
