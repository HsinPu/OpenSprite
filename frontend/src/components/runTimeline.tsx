import { Card, Empty, Timeline, Typography } from "antd";
import type { RunTimelineEventView } from "../composables/chatClientRunHelpers";

export type RunTimelineCopy = {
  timeline?: {
    title?: string;
  };
  runHistory: {
    title: string;
  };
};

function text(value: unknown, fallback = ""): string {
  return String(value || fallback).trim();
}

export function RunTimeline({ copy, events }: { copy: RunTimelineCopy; events: RunTimelineEventView[] }) {
  return (
    <Card size="small" className="run-timeline" title={copy.timeline?.title || copy.runHistory.title}>
      {events.length ? (
        <Timeline
          items={events.map((event) => {
            const tone = text(event.tone);
            const detail = text(event.detail);
            return {
              color: tone === "error" ? "red" : tone === "success" ? "green" : "blue",
              children: (
                <div>
                  <strong>{text(event.label, text(event.eventType))}</strong>
                  {detail ? <Typography.Paragraph type="secondary">{detail}</Typography.Paragraph> : null}
                </div>
              ),
            };
          })}
        />
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
      )}
    </Card>
  );
}
