import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { cancelSubagent, getSubagentResult, listSubagents, type SubagentSummary } from "../src/api/subagents";
import { SubagentExecution } from "../src/features/chat/SubagentExecution";

vi.mock("../src/api/subagents", async (importOriginal) => ({
  ...await importOriginal<typeof import("../src/api/subagents")>(),
  cancelSubagent: vi.fn(),
  getSubagentResult: vi.fn(),
  listSubagents: vi.fn(),
}));

const parentRunId = "11111111-1111-4111-8111-111111111111";
const childId = "22222222-2222-4222-8222-222222222222";
const summary = (overrides: Partial<SubagentSummary> = {}): SubagentSummary => ({
  id: childId,
  parentRunId: parentRunId,
  agentId: "33333333-3333-4333-8333-333333333333",
  name: "reviewer",
  revision: 1,
  providerId: "openai",
  modelId: "gpt-5.6",
  status: "completed",
  errorCode: null,
  createdAt: "2026-09-09T08:00:00Z",
  startedAt: "2026-09-09T08:00:01Z",
  finishedAt: "2026-09-09T08:00:04Z",
  ...overrides,
});

beforeEach(() => {
  vi.mocked(listSubagents).mockReset().mockResolvedValue({ items: [summary()] });
  vi.mocked(getSubagentResult).mockReset().mockResolvedValue({ childId, status: "completed", error: null, text: "plain result <b>not html</b>", nextOffset: null });
  vi.mocked(cancelSubagent).mockReset().mockResolvedValue(summary({ status: "cancelling" }));
});

it("loads child summaries first and fetches result text only on expansion", async () => {
  render(<SubagentExecution parentRunId={parentRunId} parentActive={false} />);
  expect(await screen.findByText("reviewer")).toBeTruthy();
  expect(getSubagentResult).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: /reviewer/ }));
  expect(await screen.findByText("plain result <b>not html</b>")).toBeTruthy();
  expect(getSubagentResult).toHaveBeenCalledWith(parentRunId, childId, 0);
  expect(screen.getByText("plain result <b>not html</b>").tagName).toBe("PRE");
});

it("cancels an active child without creating a conversation link", async () => {
  const running = summary({ status: "running" });
  vi.mocked(listSubagents).mockResolvedValue({ items: [running] });
  render(<SubagentExecution parentRunId={parentRunId} parentActive />);
  await screen.findByText("reviewer");
  fireEvent.click(screen.getByRole("button", { name: "取消" }));
  await waitFor(() => expect(cancelSubagent).toHaveBeenCalledWith(parentRunId, childId));
  expect(screen.queryByRole("link")).toBeNull();
});

it("keeps an API failure visible and retries", async () => {
  vi.mocked(listSubagents).mockRejectedValueOnce(new Error("network_error")).mockResolvedValueOnce({ items: [] });
  render(<SubagentExecution parentRunId={parentRunId} parentActive={false} />);
  expect((await screen.findByRole("alert")).textContent).toContain("network_error");
  fireEvent.click(screen.getByRole("button", { name: "重試" }));
  await waitFor(() => expect(screen.getByText("本次執行沒有使用 Subagents。")).toBeTruthy());
});

it("drops a stale response when the parent Run changes", async () => {
  const nextParent = "44444444-4444-4444-8444-444444444444";
  let resolveFirst!: (value: { items: SubagentSummary[] }) => void;
  vi.mocked(listSubagents).mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve; })).mockResolvedValueOnce({ items: [summary({ id: "55555555-5555-4555-8555-555555555555", parentRunId: nextParent, name: "new-child" })] });
  const view = render(<SubagentExecution parentRunId={parentRunId} parentActive={false} />);
  view.rerender(<SubagentExecution parentRunId={nextParent} parentActive={false} />);
  expect(await screen.findByText("new-child")).toBeTruthy();
  resolveFirst({ items: [summary()] });
  await waitFor(() => expect(screen.queryByText("reviewer")).toBeNull());
});
