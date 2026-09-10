import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
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

it("paginates failed execution output and retries only transport failures", async () => {
  const first = "x".repeat(4000);
  vi.mocked(listSubagents).mockResolvedValue({ items: [summary({ status: "failed", errorCode: "execution_failed" })] });
  vi.mocked(getSubagentResult)
    .mockResolvedValueOnce({ childId, status: "failed", error: "execution_failed", text: first, nextOffset: 4000 })
    .mockRejectedValueOnce(new Error("network_error"))
    .mockResolvedValueOnce({ childId, status: "failed", error: "execution_failed", text: "tail", nextOffset: null });
  render(<SubagentExecution parentRunId={parentRunId} parentActive={false} />);
  fireEvent.click(await screen.findByRole("button", { name: /reviewer/ }));
  await screen.findByText(first);
  expect(screen.queryByRole("button", { name: "重試" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /更多/ }));
  await screen.findByRole("alert");
  expect(screen.getByText(first)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "重試" }));
  await screen.findByText(first + "tail");
  expect(getSubagentResult).toHaveBeenLastCalledWith(parentRunId, childId, 4000);
  expect(screen.queryByRole("button", { name: "重試" })).toBeNull();
  expect(screen.getByText(/execution_failed/)).toBeTruthy();
});

it("preserves result text and retries the failed page without duplicating content", async () => {
  vi.mocked(getSubagentResult)
    .mockResolvedValueOnce({ childId, status: "completed", error: null, text: "first page", nextOffset: 4000 })
    .mockRejectedValueOnce(new Error("network_error"))
    .mockResolvedValueOnce({ childId, status: "completed", error: null, text: "last page", nextOffset: null });
  render(<SubagentExecution parentRunId={parentRunId} parentActive={false} />);
  fireEvent.click(await screen.findByRole("button", { name: /reviewer/ }));
  await screen.findByText("first page");
  fireEvent.click(screen.getByRole("button", { name: /更多/ }));
  await screen.findByRole("alert");
  expect(screen.getByText("first page")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "重試" }));
  await screen.findByText("first pagelast page");
  expect(getSubagentResult).toHaveBeenLastCalledWith(parentRunId, childId, 4000);
});

it("resets cancellation state when switching parent runs with a pending cancel", async () => {
  let resolveCancel!: (value: SubagentSummary) => void;
  vi.mocked(cancelSubagent).mockImplementationOnce(() => new Promise(resolve => { resolveCancel = resolve; }));
  vi.mocked(listSubagents).mockResolvedValue({ items: [summary({ status: "running" })] });
  const view = render(<SubagentExecution parentRunId={parentRunId} parentActive />);
  fireEvent.click(await screen.findByRole("button", { name: "取消" }));
  view.rerender(<SubagentExecution parentRunId="44444444-4444-4444-8444-444444444444" parentActive />);
  expect(await screen.findByRole("button", { name: "取消" })).toBeTruthy();
  await act(async () => { resolveCancel(summary({ status: "cancelling" })); });
  expect(screen.getByRole("button", { name: "取消" })).toBeTruthy();
});

it("concatenates result pages without changing their original text", async () => {
  const first = "a".repeat(4000);
  vi.mocked(getSubagentResult).mockResolvedValueOnce({ childId, status: "completed", error: null, text: first, nextOffset: 4000 }).mockResolvedValueOnce({ childId, status: "completed", error: null, text: "tail", nextOffset: null });
  render(<SubagentExecution parentRunId={parentRunId} parentActive={false} />);
  fireEvent.click(await screen.findByRole("button", { name: /reviewer/ }));
  await screen.findByText(first);
  fireEvent.click(screen.getByRole("button", { name: /更多/ }));
  await waitFor(() => expect(document.querySelector("pre")?.textContent).toBe(first + "tail"));
});

it("can retry a failed final refresh while retaining existing cards", async () => {
  vi.mocked(listSubagents).mockResolvedValueOnce({ items: [summary({ status: "running" })] }).mockRejectedValueOnce(new Error("network_error")).mockResolvedValue({ items: [summary()] });
  const view = render(<SubagentExecution parentRunId={parentRunId} parentActive />);
  await screen.findByText("reviewer");
  view.rerender(<SubagentExecution parentRunId={parentRunId} parentActive={false} />);
  await screen.findByRole("alert");
  expect(screen.getByText("reviewer")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "重試" }));
  expect(await screen.findByText("已完成")).toBeTruthy();
});

it("fetches final child state when the parent finishes between polls", async () => {
  vi.mocked(listSubagents).mockResolvedValueOnce({ items: [summary({ status: "running" })] }).mockResolvedValue({ items: [summary()] });
  const view = render(<SubagentExecution parentRunId={parentRunId} parentActive />);
  await screen.findByText("reviewer");
  view.rerender(<SubagentExecution parentRunId={parentRunId} parentActive={false} />);
  await waitFor(() => expect(listSubagents).toHaveBeenCalledTimes(2));
});

it("queues the final refresh behind an outstanding list request", async () => {
  let resolveList!: (value: { items: SubagentSummary[] }) => void;
  vi.mocked(listSubagents).mockImplementationOnce(() => new Promise((resolve) => { resolveList = resolve; })).mockResolvedValue({ items: [summary()] });
  const view = render(<SubagentExecution parentRunId={parentRunId} parentActive />);
  view.rerender(<SubagentExecution parentRunId={parentRunId} parentActive={false} />);
  expect(listSubagents).toHaveBeenCalledTimes(1);
  resolveList({ items: [summary({ status: "running" })] });
  await waitFor(() => expect(listSubagents).toHaveBeenCalledTimes(2));
  expect(await screen.findByText("已完成")).toBeTruthy();
});

it("refreshes a late pending result even after the final summary arrived", async () => {
  let resolveResult!: (value: Awaited<ReturnType<typeof getSubagentResult>>) => void;
  vi.mocked(listSubagents).mockResolvedValueOnce({ items: [summary({ status: "running" })] }).mockResolvedValue({ items: [summary()] });
  vi.mocked(getSubagentResult).mockImplementationOnce(() => new Promise((resolve) => { resolveResult = resolve; })).mockResolvedValue({ childId, status: "completed", error: null, text: "finished", nextOffset: null });
  const view = render(<SubagentExecution parentRunId={parentRunId} parentActive />);
  fireEvent.click(await screen.findByRole("button", { name: /reviewer/ }));
  view.rerender(<SubagentExecution parentRunId={parentRunId} parentActive={false} />);
  await screen.findByText("已完成");
  resolveResult({ childId, status: "running", error: null, text: "", nextOffset: null });
  expect(await screen.findByText("finished")).toBeTruthy();
  expect(getSubagentResult).toHaveBeenCalledTimes(2);
});

it("refreshes an expanded pending result after the child completes", async () => {
  vi.mocked(listSubagents).mockResolvedValueOnce({ items: [summary({ status: "running" })] }).mockResolvedValue({ items: [summary()] });
  vi.mocked(getSubagentResult).mockResolvedValueOnce({ childId, status: "running", error: null, text: "", nextOffset: null }).mockResolvedValue({ childId, status: "completed", error: null, text: "final answer", nextOffset: null });
  render(<SubagentExecution parentRunId={parentRunId} parentActive />);
  fireEvent.click(await screen.findByRole("button", { name: /reviewer/ }));
  await waitFor(() => expect(getSubagentResult).toHaveBeenCalledTimes(1));
  await waitFor(() => expect(screen.getByText("final answer")).toBeTruthy(), { timeout: 3500 });
});
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
