import { render, screen } from "@testing-library/react";
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
      event({ providerId: "openrouter", modelId: "openrouter/auto", responseMode: "default", maxOutputTokens: 32_768 }),
      event({ providerId: usage.providerId, modelId: usage.modelId, contextTokens: usage.contextTokens, contextLimitTokens: usage.contextLimitTokens, inputBudgetTokens: usage.inputBudgetTokens }),
    ])).toEqual(usage);
  });

  it("renders an unavailable numerator with the selected model limit", () => {
    render(<ContextUsageIndicator usage={null} fallbackLimitTokens={262_144} />);

    const indicator = screen.getByTestId("context-usage");
    expect(indicator.textContent).toContain("Context — / 256K");
    expect(indicator.getAttribute("aria-label")).toContain("256K");
    expect(indicator.className).toContain("is-unavailable");
  });

  it("preserves the latest valid context event when the visible event window is full", () => {
    const first = event({ providerId: usage.providerId, modelId: usage.modelId, contextTokens: usage.contextTokens, contextLimitTokens: usage.contextLimitTokens, inputBudgetTokens: usage.inputBudgetTokens });
    const filled = Array.from({ length: 500 }, (_, index): RunEvent => ({
      sequence: index + 2,
      type: "assistant.delta",
      runId: first.runId,
      conversationId: first.conversationId,
      createdAt: first.createdAt,
      data: { text: "x" },
    }));

    const retained = appendEventPreservingContextUsage([first, ...filled.slice(0, 499)], filled[499]!);

    expect(retained).toHaveLength(500);
    expect(contextUsageFromEvents(retained)).toEqual(usage);
    expect(retained[0]?.sequence).toBe(first.sequence);
    expect(retained.at(-1)?.sequence).toBe(501);
  });

  it("marks the indicator while Context is being compacted", () => {
    render(<ContextUsageIndicator usage={usage} fallbackLimitTokens={null} compacting />);

    const indicator = screen.getByTestId("context-usage");
    expect(indicator.textContent).toContain("Context 4K / 256K");
    expect(indicator.textContent).toContain("整理中");
    expect(indicator.className).toContain("is-compacting");
  });
});
