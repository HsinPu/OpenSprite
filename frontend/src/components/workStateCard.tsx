import { Button, Card, Space, Tag, Typography } from "antd";
import { runStatusColor } from "./displayHelpers";
import type { RunInspectorClient } from "./runInspector";
import type { WorkStateView } from "../composables/runTraceNormalizers";

export function WorkStateCard({ client, workState }: { client: RunInspectorClient; workState: WorkStateView }) {
  const copy = client.copy.value;
  const objective = workState.objective || copy.runSummary.fallbackObjective;
  const status = workState.status || "active";
  const nextSteps = workState.pendingSteps.length ? workState.pendingSteps : workState.steps;

  return (
    <Card size="small" className="work-state-card">
      <Space direction="vertical" size={8}>
        <Typography.Text type="secondary">{copy.workState?.currentTask || copy.runSummary.objective}</Typography.Text>
        <Typography.Title level={5}>{objective}</Typography.Title>
        <Tag color={runStatusColor(status)}>{status}</Tag>
        {nextSteps.length ? (
          <ul>
            {nextSteps.slice(0, 4).map((step: string, index: number) => (
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
