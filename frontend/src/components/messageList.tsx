import { useMemo } from "react";
import { EyeOutlined } from "@ant-design/icons";
import { Button, Card, Space, Tag, Typography } from "antd";
import { runStatusColor } from "./displayHelpers";
import { artifactStatusLabel, artifactTypeLabel, normalizeMessages } from "./messageData";
import { MessageTextRenderer } from "./messageMarkdown";

type AnyRecord = Record<string, any>;

export function MessageList({
  copy,
  entries,
  messages,
  runs,
  displayName,
  viewTraceForRun,
}: {
  copy: AnyRecord;
  entries: AnyRecord[];
  messages: AnyRecord[];
  runs: AnyRecord[];
  displayName: string;
  viewTraceForRun: (runId: string) => void;
}) {
  const renderedMessages = useMemo(
    () => normalizeMessages({ copy, entries, messages, runs, displayName }),
    [copy, entries, messages, runs, displayName],
  );

  return (
    <div className="message-list">
      {renderedMessages.map((message) => (
        <article key={message.id} className={`message message--${message.role}`}>
          <div className="message__avatar">{message.role === "user" ? copy.message.userAvatar : copy.message.assistantAvatar}</div>
          <div className="message__content">
            <div className="message__meta">
              <span>{message.meta || (message.role === "user" ? displayName : "OpenSprite")}</span>
              {message.timeLabel ? (
                <time className="message__time" dateTime={message.isoTime} title={message.fullTimeLabel}>
                  {message.timeLabel}
                </time>
              ) : null}
              {message.traceRunId ? (
                <Button
                  className="message__trace-button"
                  size="small"
                  icon={<EyeOutlined />}
                  onClick={() => viewTraceForRun(message.traceRunId)}
                >
                  {copy.message.viewTrace}
                </Button>
              ) : null}
            </div>
            {message.textBlocks.length ? (
              <div className="message__bubble">
                <MessageTextRenderer blocks={message.textBlocks} copy={copy} />
              </div>
            ) : null}
            {message.content?.length ? (
              <div className="message__parts">
                {message.content.map((part: AnyRecord) =>
                  part.type === "text" ? (
                    <div key={part.id} className="message__bubble">
                      <MessageTextRenderer blocks={part.textBlocks} copy={copy} />
                    </div>
                  ) : (
                    <Card key={part.id} size="small" className="message__artifact">
                      <Space>
                        <Tag>{artifactTypeLabel(copy, part.type)}</Tag>
                        {part.status ? <Tag color={runStatusColor(part.status)}>{artifactStatusLabel(copy, part.status)}</Tag> : null}
                      </Space>
                      <Typography.Title level={5}>{part.title || artifactTypeLabel(copy, part.type)}</Typography.Title>
                      {part.detail ? <Typography.Paragraph>{part.detail}</Typography.Paragraph> : null}
                    </Card>
                  ),
                )}
              </div>
            ) : null}
          </div>
        </article>
      ))}
    </div>
  );
}
