import { fireEvent, render, screen } from "@testing-library/react";
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

describe("execution context disclosure", () => {
  it("starts collapsed and preserves a manual choice across Run updates", () => {
    const { rerender } = render(<ExecutionContext modelName="GPT-5.6" run={run} events={[]} timeZone="system" defaultExpanded={false} />);
    const toggle = screen.getByRole("button", { name: "展開本次執行" });
    const body = document.getElementById(toggle.getAttribute("aria-controls")!);

    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect(body?.hidden).toBe(true);
    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-expanded")).toBe("true");

    rerender(<ExecutionContext modelName="GPT-5.6" run={{ ...run, partialText: "更新" }} events={[event]} timeZone="system" defaultExpanded={false} />);
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
  });

  it("applies a confirmed preference change", () => {
    const { rerender } = render(<ExecutionContext modelName="GPT-5.6" run={run} events={[]} timeZone="system" defaultExpanded={false} />);
    expect(screen.getByRole("button", { name: "展開本次執行" })).toBeTruthy();

    rerender(<ExecutionContext modelName="GPT-5.6" run={run} events={[]} timeZone="system" defaultExpanded />);
    expect(screen.getByRole("button", { name: "收合本次執行" })).toBeTruthy();

    rerender(<ExecutionContext modelName="GPT-5.6" run={run} events={[]} timeZone="system" defaultExpanded={false} />);
    expect(screen.getByRole("button", { name: "展開本次執行" })).toBeTruthy();
  });

  it("opens historical inspection and restores the latest default", () => {
    const { rerender } = render(<ExecutionContext modelName="GPT-5.6" run={run} events={[]} timeZone="system" defaultExpanded={false} />);

    rerender(<ExecutionContext modelName="GPT-5.6" run={{ ...run, status: "completed", assistantMessageId: "44444444-4444-4444-8444-444444444444", finishedAt: "2026-08-29T08:00:02Z" }} events={[event]} timeZone="system" defaultExpanded={false} historical inspectionRunId={run.id} />);
    expect(screen.getByRole("button", { name: "收合執行詳情" })).toBeTruthy();

    rerender(<ExecutionContext modelName="GPT-5.6" run={run} events={[]} timeZone="system" defaultExpanded={false} />);
    expect(screen.getByRole("button", { name: "展開本次執行" })).toBeTruthy();
  });
});
