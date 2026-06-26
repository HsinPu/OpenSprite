import { Card, Empty, Timeline, Typography } from "antd";

type AnyRecord = Record<string, any>;

export function RunTimeline({ copy, events }: { copy: AnyRecord; events: AnyRecord[] }) {
  return (
    <Card size="small" className="run-timeline" title={copy.timeline?.title || copy.runHistory.title}>
      {events.length ? (
        <Timeline
          items={events.map((event) => ({
            color: event.tone === "error" ? "red" : event.tone === "success" ? "green" : "blue",
            children: (
              <div>
                <strong>{event.label || event.eventType}</strong>
                {event.detail ? <Typography.Paragraph type="secondary">{event.detail}</Typography.Paragraph> : null}
              </div>
            ),
          }))}
        />
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
      )}
    </Card>
  );
}
