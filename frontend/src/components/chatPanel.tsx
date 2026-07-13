import type { FormEvent, KeyboardEvent } from "react";
import { SendOutlined } from "@ant-design/icons";
import { Alert, Button, Input } from "antd";
import { noticeTone } from "./displayHelpers";
import { EmptyState, type EmptyStateCopy, type PromptOption } from "./emptyState";
import { MessageList } from "./messageList";
import type { MessageCopy } from "./messageMarkdown";
import type { RunViewState } from "../composables/chatClientRunHelpers";
import type { ChatMessage, LiveEntry } from "../composables/chatClientSessions";
import type { CommandCatalogItem, NoticeState } from "../composables/useChatClient";

type ValueRef<T> = { value: T };
type ChatPanelCopy = EmptyStateCopy &
  MessageCopy & {
    chat: {
      title: string;
    };
    composer: {
      commandSuggestions: string;
      disclaimer: string;
      placeholder: string;
      send: string;
      sendAria: string;
    };
  };

type ChatPanelState = {
  displayName: string;
  notice: NoticeState;
};

type ChatPanelClient = {
  copy: ValueRef<ChatPanelCopy>;
  composerHint: ValueRef<string>;
  prompts: ValueRef<PromptOption[]>;
  commandHints: ValueRef<CommandCatalogItem[]>;
  currentEntries: ValueRef<LiveEntry[]>;
  currentMessages: ValueRef<ChatMessage[]>;
  currentRuns: ValueRef<RunViewState[]>;
  currentSessionReadOnly: ValueRef<boolean>;
  messageText: ValueRef<string>;
  sendDisabled: ValueRef<boolean>;
  sessionMeta: ValueRef<string>;
  applyPrompt: (prompt: string) => void;
  applyCommandHint: (command: CommandCatalogItem) => void;
  handleComposerKeydown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
  resizeComposer: () => void;
  setMessageInputRef: (element: HTMLTextAreaElement | null) => void;
  setMessageStageRef: (element: HTMLElement | null) => void;
  setMessageText: (value: string) => void;
  state: ChatPanelState;
  submitMessage: (event: FormEvent<HTMLFormElement>) => void;
};

export function ChatPanel({ client, viewTraceForRun }: { client: ChatPanelClient; viewTraceForRun: (runId: string) => void }) {
  const copy = client.copy.value;
  const prompts = client.prompts.value || [];
  const notice = client.state.notice;

  return (
    <main className="chat-panel">
      <header className="topbar">
        <div className="topbar__title">
          <strong>{copy.chat.title}</strong>
          <span>{client.sessionMeta.value}</span>
        </div>
      </header>

      {notice.text ? (
        <Alert className="notice-banner" role="status" type={noticeTone(notice.tone)} showIcon message={notice.text} data-tone={notice.tone} />
      ) : null}

      <section ref={client.setMessageStageRef} className="message-stage" aria-live="polite">
        <div className="conversation-wrap">
          {!client.currentEntries.value.length && !client.currentMessages.value.length ? (
            <EmptyState copy={copy} prompts={prompts} applyPrompt={client.applyPrompt} />
          ) : null}
          <MessageList
            copy={copy}
            entries={client.currentEntries.value}
            messages={client.currentMessages.value}
            runs={client.currentRuns.value}
            displayName={client.state.displayName}
            viewTraceForRun={viewTraceForRun}
          />
        </div>
      </section>

      <form className="composer" onSubmit={client.submitMessage}>
        {client.commandHints.value?.length ? (
          <div className="composer__commands" aria-label={copy.composer.commandSuggestions}>
            {client.commandHints.value.map((command: CommandCatalogItem) => (
              <Button
                key={command.name || command.command || command.usage}
                type="text"
                className="composer__command"
                onClick={() => client.applyCommandHint(command)}
              >
                <code>{command.usage || command.command}</code>
                <span>{command.description}</span>
              </Button>
            ))}
          </div>
        ) : null}
        <div className="composer__box">
          <Input.TextArea
            className="composer__input"
            id="messageInput"
            ref={(input) => client.setMessageInputRef(input?.resizableTextArea?.textArea || null)}
            value={client.messageText.value}
            rows={1}
            placeholder={copy.composer.placeholder}
            readOnly={client.currentSessionReadOnly.value}
            autoComplete="off"
            autoSize={false}
            onChange={(event) => {
              client.setMessageText(event.target.value);
              client.resizeComposer();
            }}
            onKeyDown={client.handleComposerKeydown}
          />
          <Button
            className="send-button"
            type="primary"
            htmlType="submit"
            aria-label={copy.composer.sendAria}
            disabled={client.sendDisabled.value}
            icon={<SendOutlined />}
          >
            {copy.composer.send}
          </Button>
        </div>
        <div className="composer__footer">
          <span>{copy.composer.disclaimer}</span>
          <span>{client.composerHint.value}</span>
        </div>
      </form>
    </main>
  );
}
