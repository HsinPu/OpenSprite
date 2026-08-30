import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { RunEvent, RunSnapshot } from "../src/api/agentChat";
import { ExecutionContext } from "../src/features/chat/ExecutionContext";


const run: RunSnapshot = {
  id: "11111111-1111-4111-8111-111111111111",
  conversationId: "22222222-2222-4222-8222-222222222222",
  userMessageId: "33333333-3333-4333-8333-333333333333",
  assistantMessageId: null,
  providerId: "openai",
  modelId: "gpt-5.6",
  responseMode: "default",
  status: "running",
  error: null,
  partialText: "",
  createdAt: "2026-08-29T08:00:00Z",
  startedAt: "2026-08-29T08:00:01Z",
  finishedAt: null,
};

const event: RunEvent = {
  sequence: 1,
  type: "run.started",
  runId: run.id,
  conversationId: run.conversationId,
  createdAt: run.startedAt!,
  data: {},
};

const compactionEvent: RunEvent = {
  ...event,
  sequence: 2,
  type: "context.compaction.started",
  createdAt: "2026-08-29T08:00:02Z",
};

const modelEvent: RunEvent = {
  ...event,
  sequence: 4,
  type: "model.started",
  createdAt: "2026-08-29T08:00:04Z",
  data: { providerId: "openai", modelId: run.modelId, responseMode: "default" },
};

describe("execution context disclosure", () => {
  it("starts collapsed and preserves its controlled state across Run updates", () => {
    const { rerender, container } = render(<ExecutionContext modelName="GPT-5.6" run={run} events={[]} timeZone="system" defaultExpanded={false} expanded={false} />);
    const body = container.querySelector<HTMLElement>(".chat-workspace__context-body");

    expect(body?.hidden).toBe(true);

    rerender(<ExecutionContext modelName="GPT-5.6" run={{ ...run, partialText: "更新" }} events={[event]} timeZone="system" defaultExpanded={false} expanded={true} />);
    expect(body?.hidden).toBe(false);
  });

  it("applies a confirmed preference change", () => {
    const { rerender, container } = render(<ExecutionContext modelName="GPT-5.6" run={run} events={[]} timeZone="system" defaultExpanded={false} />);
    const body = container.querySelector<HTMLElement>(".chat-workspace__context-body");
    expect(body?.hidden).toBe(true);

    rerender(<ExecutionContext modelName="GPT-5.6" run={run} events={[]} timeZone="system" defaultExpanded />);
    expect(body?.hidden).toBe(false);

    rerender(<ExecutionContext modelName="GPT-5.6" run={run} events={[]} timeZone="system" defaultExpanded={false} />);
    expect(body?.hidden).toBe(true);
  });

  it("uses the existing Run start event as minimal Context preparation progress", () => {
    render(<ExecutionContext modelName="GPT-5.6" run={run} events={[event]} timeZone="system" defaultExpanded />);

    expect(screen.getByText("準備對話內容")).toBeTruthy();
  });

  it("shows repeated Context compactions as one execution step", () => {
    render(<ExecutionContext modelName="GPT-5.6" run={run} events={[event, compactionEvent, modelEvent, { ...compactionEvent, sequence: 5, createdAt: "2026-08-29T08:00:05Z" }]} timeZone="system" defaultExpanded />);

    expect(screen.getAllByText("整理較早的對話內容")).toHaveLength(1);
    expect(screen.getByText("請求模型 gpt-5.6")).toBeTruthy();
    expect(document.querySelector(".chat-workspace__process-item--active")?.textContent).toContain("整理較早的對話內容");
  });

  it("renders a Drawer mode without a second collapse control", () => {
    render(<ExecutionContext modelName="GPT-5.6" run={run} events={[event]} timeZone="system" defaultExpanded={false} mode="drawer" />);

    expect(screen.queryByRole("button", { name: /展開本次執行|收合本次執行/ })).toBeNull();
    expect(screen.getByText("openai · gpt-5.6 · 廠商預設")).toBeTruthy();
  });

  it("opens historical inspection and restores the latest default", () => {
    const { rerender, container } = render(<ExecutionContext modelName="GPT-5.6" run={run} events={[]} timeZone="system" defaultExpanded={false} />);
    const body = container.querySelector<HTMLElement>(".chat-workspace__context-body");
    expect(body?.hidden).toBe(true);

    rerender(<ExecutionContext modelName="GPT-5.6" run={{ ...run, status: "completed", assistantMessageId: "44444444-4444-4444-8444-444444444444", finishedAt: "2026-08-29T08:00:02Z" }} events={[event]} timeZone="system" defaultExpanded={false} historical inspectionRunId={run.id} />);
    expect(body?.hidden).toBe(false);

    rerender(<ExecutionContext modelName="GPT-5.6" run={run} events={[]} timeZone="system" defaultExpanded={false} />);
    expect(body?.hidden).toBe(true);
  });
});
