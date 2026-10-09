import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { RunSteps } from "../src/features/chat/RunSteps";
import { listRunSteps } from "../src/api/agentChat";

const runId = "e7527bf5-81c9-4534-908c-a9a9bc501f26";
const stepId = "c01956dc-fdf0-435c-a3be-e7eb5fd65f22";
const step = { id: stepId, runId, sequence: 1, label: "review", channel: "draft",
  status: "completed", text: "variable "+crypto.randomUUID(), finishReason: "final",
  errorCode: null, inputTokens: 7, outputTokens: 3, retryOf: null,
  createdAt: "2026-10-09T00:00:00Z", finishedAt: "2026-10-09T00:00:01Z" };
afterEach(() => vi.unstubAllGlobals());

it("shows actual private step text when expanded and refreshes on revision", async () => {
  const fetcher = vi.fn(async () => new Response(JSON.stringify({ steps:[step], nextAfterSequence:null })));
  vi.stubGlobal("fetch", fetcher);
  const view = render(<RunSteps runId={runId} revision="1" />);
  fireEvent.click(await screen.findByRole("button", { name:/review/ }));
  expect(await screen.findByText(step.text)).toBeTruthy();
  expect(screen.getByText("草稿")).toBeTruthy();
  view.rerender(<RunSteps runId={runId} revision="2" />);
  await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
});

it.each([
  { ...step, runId: stepId }, { ...step, channel:"reasoning" },
  { ...step, inputTokens:-1 }, { ...step, rawCredential:"unapproved" },
])("rejects malformed or mismatched step snapshots", async value => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ steps:[value], nextAfterSequence:null }))));
  await expect(listRunSteps(runId)).rejects.toMatchObject({ code:"malformed_response" });
});

it("offers retry after a failed step-history request", async () => {
  const fetcher = vi.fn().mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(new Response(JSON.stringify({ steps:[step], nextAfterSequence:null })));
  vi.stubGlobal("fetch",fetcher);
  render(<RunSteps runId={runId} revision="1" />);
  fireEvent.click(await screen.findByRole("button",{ name:"重新載入" }));
  await screen.findByRole("button",{ name:/review/ });
});
