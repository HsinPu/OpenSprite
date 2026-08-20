import { FormEvent, useId, useState } from 'react';

import './ChatWorkspace.css';

type ChatMessage = {
  id: number;
  role: 'user' | 'assistant';
  content: string;
};

type ChatWorkspaceProps = {
  modelName: string;
  title?: string;
  initiallyEmpty?: boolean;
};

const initialMessages: ChatMessage[] = [
  {
    id: 1,
    role: 'user',
    content: '幫我整理今天的重要工作，並找出還沒完成的項目',
  },
  {
    id: 2,
    role: 'assistant',
    content: '以下是今天的重要工作摘要與未完成項目：',
  },
];

function OpenSpriteMark({ small = false }: { small?: boolean }) {
  return <span aria-hidden="true" className={`chat-workspace__mark${small ? ' chat-workspace__mark--small' : ''}`} />;
}

function AssistantSummary() {
  return (
    <div className="chat-workspace__assistant-card">
      <p className="chat-workspace__assistant-intro">以下是今天的重要工作摘要與未完成項目：</p>

      <section aria-labelledby="summary-title">
        <h2 id="summary-title" className="chat-workspace__section-title">今日摘要</h2>
        <p className="chat-workspace__body-copy">
          你今天完成了專案進度更新與團隊會議，處理了客戶回覆與需求確認。目前仍有 3 項待完成，建議優先處理專案報告與設計審核。
        </p>
      </section>

      <section aria-labelledby="pending-title">
        <h2 id="pending-title" className="chat-workspace__section-title">待完成項目</h2>
        <ol className="chat-workspace__task-list">
          <li>完成專案進度報告並同步給利害關係人</li>
          <li>審核首頁設計稿並提供回饋</li>
          <li>整理客戶回饋並更新需求文件</li>
        </ol>
      </section>

      <details className="chat-workspace__process" open>
        <summary>
          <span>執行過程</span>
          <span aria-hidden="true" className="chat-workspace__chevron">⌃</span>
        </summary>
        <ol className="chat-workspace__process-list" aria-label="執行步驟">
          <li className="chat-workspace__process-item chat-workspace__process-item--complete">
            <span className="chat-workspace__step-icon" aria-hidden="true">✓</span>
            <span>讀取對話紀錄</span>
            <time dateTime="10:21:12">10:21:12</time>
          </li>
          <li className="chat-workspace__process-item chat-workspace__process-item--complete">
            <span className="chat-workspace__step-icon" aria-hidden="true">✓</span>
            <span>整理待辦事項</span>
            <time dateTime="10:21:14">10:21:14</time>
          </li>
          <li className="chat-workspace__process-item chat-workspace__process-item--active" aria-current="step">
            <span className="chat-workspace__step-icon" aria-hidden="true" />
            <span>產生摘要</span>
            <span className="chat-workspace__process-status">已完成</span>
          </li>
        </ol>
      </details>
    </div>
  );
}

function ExecutionContext({ modelName }: { modelName: string }) {
  const [isExpanded, setIsExpanded] = useState(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return true;
    return !window.matchMedia('(max-width: 767px)').matches;
  });
  const contextId = useId();
  const executionTitleId = `${contextId}-execution-title`;
  const executionBodyId = `${contextId}-execution-body`;
  const modelTitleId = `${contextId}-model-title`;
  const capabilitiesTitleId = `${contextId}-capabilities-title`;
  const executionInfoTitleId = `${contextId}-execution-info-title`;

  return (
    <aside
      className={`chat-workspace__context${isExpanded ? '' : ' chat-workspace__context--collapsed'}`}
      aria-labelledby={executionTitleId}
    >
      <div className="chat-workspace__context-heading">
        <h2 id={executionTitleId}>本次執行</h2>
        <button
          type="button"
          className="chat-workspace__context-toggle"
          aria-expanded={isExpanded}
          aria-controls={executionBodyId}
          aria-label={isExpanded ? '收合本次執行' : '展開本次執行'}
          title={isExpanded ? '收合本次執行' : '展開本次執行'}
          onClick={() => setIsExpanded((current) => !current)}
        >
          <span aria-hidden="true" className="chat-workspace__context-toggle-icon chat-workspace__context-toggle-icon--horizontal">{isExpanded ? '›' : '‹'}</span>
          <span aria-hidden="true" className="chat-workspace__context-toggle-icon chat-workspace__context-toggle-icon--vertical">{isExpanded ? '⌃' : '⌄'}</span>
        </button>
      </div>

      <div className="chat-workspace__context-summary" aria-hidden={isExpanded}>
        <span>已完成</span>
        <span>{modelName}</span>
        <span>3 / 3</span>
      </div>

      <div id={executionBodyId} className="chat-workspace__context-body" hidden={!isExpanded}>
        <section className="chat-workspace__context-section" aria-labelledby={modelTitleId}>
          <h3 id={modelTitleId}>模型</h3>
          <div className="chat-workspace__model-card">
            <OpenSpriteMark small />
            <span>{modelName}</span>
            <span className="chat-workspace__connected-pill"><i aria-hidden="true" />本機執行</span>
          </div>
        </section>

        <section className="chat-workspace__context-section" aria-labelledby={capabilitiesTitleId}>
          <h3 id={capabilitiesTitleId}>已連線的能力</h3>
          <ul className="chat-workspace__capability-list">
            <li><span className="chat-workspace__capability-icon" aria-hidden="true">⌕</span><span>搜尋</span><i aria-label="已連線" /></li>
            <li><span className="chat-workspace__capability-icon" aria-hidden="true">□</span><span>檔案</span><i aria-label="已連線" /></li>
            <li><span className="chat-workspace__capability-icon" aria-hidden="true">⌄</span><span>記憶</span><i aria-label="已連線" /></li>
          </ul>
        </section>

        <section className="chat-workspace__context-section chat-workspace__execution-info" aria-labelledby={executionInfoTitleId}>
          <h3 id={executionInfoTitleId}>執行資訊</h3>
          <dl className="chat-workspace__stats">
            <div><dt>開始時間</dt><dd>10:21:10</dd></div>
            <div><dt>執行時長</dt><dd>00:00:18</dd></div>
            <div><dt>步驟</dt><dd>3 / 3</dd></div>
            <div><dt>來源</dt><dd>對話、檔案、記憶</dd></div>
          </dl>
        </section>

        <details className="chat-workspace__record-details">
          <summary><span>詳細紀錄</span><span aria-hidden="true">⌄</span></summary>
          <p>本次執行未產生額外警告。</p>
        </details>
      </div>
    </aside>
  );
}

export function ChatWorkspace({
  modelName,
  title = '整理今天的工作',
  initiallyEmpty = false,
}: ChatWorkspaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>(
    initiallyEmpty ? [] : initialMessages,
  );
  const [draft, setDraft] = useState('');
  const [nextId, setNextId] = useState(3);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const content = draft.trim();
    if (!content) return;

    setMessages((current) => [
      ...current,
      { id: nextId, role: 'user', content },
      { id: nextId + 1, role: 'assistant', content: '收到，我已把這項需求加入今天的工作摘要。' },
    ]);
    setNextId((current) => current + 2);
    setDraft('');
  };

  return (
    <section className="chat-workspace" aria-label="AI 對話工作台">
      <div className="chat-workspace__main">
        <header className="chat-workspace__header">
          <h1>{title}</h1>
          <div className="chat-workspace__header-actions">
            <button
              type="button"
              className="chat-workspace__model-select"
              disabled
              title="Demo 中無法切換模型"
              aria-label={`目前模型 ${modelName}，Demo 中無法切換`}
            >
              {modelName} <span aria-hidden="true">⌄</span>
            </button>
            <span className="chat-workspace__local-status"><i aria-hidden="true" />本機執行</span>
            <button
              type="button"
              className="chat-workspace__icon-button"
              disabled
              title="Demo 中沒有更多對話選項"
              aria-label="更多對話選項（Demo 中無法使用）"
            >
              ⋮
            </button>
          </div>
        </header>

        <div className="chat-workspace__conversation" aria-live="polite">
          {messages.length === 0 ? (
            <div className="chat-workspace__empty-state">
              <OpenSpriteMark />
              <h2>今天想完成什麼？</h2>
              <p>輸入一件想處理的事，OpenSprite 會在這裡顯示 Demo 回應。</p>
            </div>
          ) : null}
          {messages.map((message) => message.role === 'user' ? (
            <div className="chat-workspace__user-row" key={message.id}>
              <p className="chat-workspace__user-message">{message.content}</p>
              <span className="chat-workspace__user-avatar" aria-hidden="true">♙</span>
            </div>
          ) : (
            <div className="chat-workspace__assistant-row" key={message.id}>
              <OpenSpriteMark />
              {message.id === 2 ? <AssistantSummary /> : <div className="chat-workspace__assistant-card chat-workspace__assistant-card--compact"><p>{message.content}</p></div>}
            </div>
          ))}
        </div>

        <form className="chat-workspace__composer" onSubmit={handleSubmit}>
          <label htmlFor="chat-message" className="chat-workspace__composer-label">輸入訊息</label>
          <textarea
            id="chat-message"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="輸入訊息，或描述你想完成的事..."
            rows={2}
          />
          <div className="chat-workspace__composer-actions">
            <div>
              <button
                type="button"
                className="chat-workspace__tool-button"
                disabled
                title="Demo 中無法附加檔案"
                aria-label="附加檔案（Demo 中無法使用）"
              >
                ⌕
              </button>
              <button
                type="button"
                className="chat-workspace__tool-button"
                disabled
                title="Demo 中無法調整訊息選項"
                aria-label="調整訊息選項（Demo 中無法使用）"
              >
                ☷
              </button>
            </div>
            <button type="submit" className="chat-workspace__send-button" disabled={!draft.trim()} aria-label="送出訊息">➤</button>
          </div>
        </form>
      </div>

      <ExecutionContext modelName={modelName} />
    </section>
  );
}
