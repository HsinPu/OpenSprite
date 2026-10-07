import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ContextUsage, RunEvent } from "../src/api/agentChat";
import { ContextUsageIndicator, appendEventPreservingContextUsage, contextUsageFromEvents } from "../src/features/chat/ContextUsageIndicator";

const usage: ContextUsage = {
  providerId: "openrouter",
  modelId: "openrouter/auto",
  contextTokens: 4_096,
  contextLimitTokens: 262_144,
  inputBudgetTokens: 196_608,
};

const event = (data: Record<string, unknown>): RunEvent => ({
  sequence: 1,
  type: "model.started",
  runId: "11111111-1111-4111-8111-111111111111",
  conversationId: "22222222-2222-4222-8222-222222222222",
  createdAt: "2026-08-31T08:00:00Z",
  data,
});

describe("context usage indicator", () => {
  it("extracts the latest valid model context usage and ignores legacy events", () => {
    expect(contextUsageFromEvents([
      event({ providerId: "openrouter", modelId: "openrouter/auto", responseMode: "medium", maxOutputTokens: 32_768 }),
      event({ providerId: usage.providerId, modelId: usage.modelId, contextTokens: usage.contextTokens, contextLimitTokens: usage.contextLimitTokens, inputBudgetTokens: usage.inputBudgetTokens }),
    ])).toEqual(usage);
  });

  it("renders an unavailable numerator with the selected model limit", () => {
    render(<ContextUsageIndicator usage={null} fallbackLimitTokens={262_144} />);

    const indicator = screen.getByTestId("context-usage");
    expect(indicator.textContent).toBe("");
    expect(indicator.getAttribute("aria-label")).toContain("256K");
    expect(indicator.getAttribute("aria-label")).toContain("尚無使用量資料");
  });

  it("preserves Run start, execution plugins and the latest Context after more than 500 events", () => {
    const runStarted: RunEvent = { ...event({}), type: "run.started" };
    const executionSelected: RunEvent = { ...event({ loopId: "custom.loop", loopVersion: "1.2.3", policyId: "no_recovery", policyVersion: "1.0.0", apiVersion: 1 }), type: "execution.selected", sequence: 2 };
    const context = { ...event({ ...usage }), sequence: 3 };
    const filled = Array.from({ length: 600 }, (_, index): RunEvent => ({
      sequence: index + 4,
      type: "assistant.delta",
      runId: context.runId,
      conversationId: context.conversationId,
      createdAt: context.createdAt,
      data: { text: "x" },
    }));

    const latestContext = { ...context, sequence: 604, data: { ...usage, contextTokens: 8_192 } };
    const retained = [...filled, latestContext].reduce(appendEventPreservingContextUsage, [runStarted, executionSelected, context]);

    expect(retained).toHaveLength(500);
    expect(contextUsageFromEvents(retained)).toEqual({ ...usage, contextTokens: 8_192 });
    expect(retained[0]).toEqual(runStarted);
    expect(retained[1]).toEqual(executionSelected);
    expect(retained.at(-1)).toEqual(latestContext);
    expect(retained).not.toContainEqual(context);
  });

  it("marks the indicator while Context is being compacted", () => {
    render(<ContextUsageIndicator usage={usage} fallbackLimitTokens={null} compacting />);

    const indicator = screen.getByTestId("context-usage");
    expect(indicator.getAttribute("aria-label")).toContain("4K");
    expect(indicator.getAttribute("aria-label")).toContain("整理中");
  });

  it.each([0, 25, 76, 100, 105])("shows %s percent against context limit rather than input budget", (percent) => {
    render(<ContextUsageIndicator usage={{ ...usage, contextTokens: percent * 100, contextLimitTokens: 10000, inputBudgetTokens: 8000 }} fallbackLimitTokens={null} />);
    expect(screen.getByTestId("context-usage").getAttribute("aria-label")).toContain(`已使用 ${percent}%`);
  });

  it("opens details on click and closes with Escape", async () => {
    render(<ContextUsageIndicator usage={usage} fallbackLimitTokens={null} />);
    const button = screen.getByTestId("context-usage");
    fireEvent.click(button);
    expect(await screen.findByText("4K / 256K tokens")).toBeTruthy();
    expect(button.getAttribute("aria-expanded")).toBe("true");
    fireEvent.keyDown(button, { key: "Escape" });
    expect(button.getAttribute("aria-expanded")).toBe("false");
  });

  it("opens on hover and keyboard focus without a click", async () => {
    render(<ContextUsageIndicator usage={usage} fallbackLimitTokens={null} />);
    const button = screen.getByTestId("context-usage");
    fireEvent.mouseEnter(button);
    await waitFor(() => expect(button.getAttribute("aria-expanded")).toBe("true"));
    fireEvent.mouseLeave(button);
    await waitFor(() => expect(button.getAttribute("aria-expanded")).toBe("false"));
    fireEvent.focus(button);
    await waitFor(() => expect(button.getAttribute("aria-expanded")).toBe("true"));
    fireEvent.blur(button);
    await waitFor(() => expect(button.getAttribute("aria-expanded")).toBe("false"));
  });

  it.each([0, -1, Number.NaN])("does not report a percentage with invalid limit %s", (limit) => {
    render(<ContextUsageIndicator usage={{ ...usage, contextLimitTokens: limit }} fallbackLimitTokens={null} />);
    expect(screen.getByTestId("context-usage").getAttribute("aria-label")).toContain("尚無使用量資料");
  });
});
