import { Button, Card, Space, Tag, Typography } from "antd";
import { runStatusColor } from "./displayHelpers";
import type { RunInspectorClient } from "./runInspector";

type AnyRecord = Record<string, any>;

export function WorkStateCard({ client, workState }: { client: RunInspectorClient; workState: AnyRecord }) {
  const copy = client.copy.value;
  const objective = workState.objective || workState.title || workState.current_task || copy.runSummary.fallbackObjective;
  const status = workState.status || workState.phase || "active";

  return (
    <Card size="small" className="work-state-card">
      <Space direction="vertical" size={8}>
        <Typography.Text type="secondary">{copy.workState?.currentTask || copy.runSummary.objective}</Typography.Text>
        <Typography.Title level={5}>{objective}</Typography.Title>
        <Tag color={runStatusColor(status)}>{status}</Tag>
        {Array.isArray(workState.next_steps) && workState.next_steps.length ? (
          <ul>
            {workState.next_steps.slice(0, 4).map((step: string, index: number) => (
              <li key={`${step}-${index}`}>{step}</li>
            ))}
          </ul>
        ) : null}
        <Space wrap>
          <Button size="small" onClick={() => client.resumeFollowUp(copy.workState?.continuePrompt || "continue")}>
            {copy.workState?.continue || "Continue"}
          </Button>
          <Button size="small" onClick={() => client.runVerification(copy.workState?.verifyPrompt || "verify")}>
            {copy.workState?.verify || "Verify"}
          </Button>
        </Space>
      </Space>
    </Card>
  );
}
