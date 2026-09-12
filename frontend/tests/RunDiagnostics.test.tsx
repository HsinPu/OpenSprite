import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { RunDiagnostics } from "../src/features/chat/RunDiagnostics";
import type { RunEvent } from "../src/api/agentChat";

const runId = "e7527bf5-81c9-4534-908c-a9a9bc501f26";
const conversationId = "49d6c5e3-1724-44a7-9e69-0c0103176461";
const event = (sequence: number): RunEvent => ({ sequence, runId, conversationId,
  type: "context.compaction.started", createdAt: "2026-08-21T08:30:00Z", data: {} });
afterEach(() => vi.unstubAllGlobals());

it("loads only on demand, pages forward and backward", async () => {
  const fetcher = vi.fn(async (url: string) => new Response(JSON.stringify(url.includes("afterSequence=100")
    ? { events: [event(101)], nextAfterSequence: null }
    : { events: [event(100)], nextAfterSequence: 100 })));
  vi.stubGlobal("fetch", fetcher);
  render(<RunDiagnostics runId={runId} conversationId={conversationId} />);
  expect(fetcher).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("開啟診斷明細"));
  await screen.findByText("事件範圍：100–100");
  fireEvent.click(screen.getByText("下一頁"));
  await screen.findByText("事件範圍：101–101");
  fireEvent.click(screen.getByText("上一頁"));
  await screen.findByText("事件範圍：100–100");
  expect(fetcher).toHaveBeenCalledTimes(3);
  fireEvent.click(screen.getByRole("button", { name: "Close" }));
  await waitFor(() => expect(document.activeElement).toBe(screen.getByText("開啟診斷明細").closest("button")));
});

it("ignores an old run's delayed response", async () => {
  let resolve!: (response: Response) => void;
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(done => { resolve = done; })));
  const view = render(<RunDiagnostics runId={runId} conversationId={conversationId} />);
  fireEvent.click(screen.getByText("開啟診斷明細"));
  view.rerender(<RunDiagnostics runId={conversationId} conversationId={conversationId} />);
  resolve(new Response(JSON.stringify({ events: [event(99)], nextAfterSequence: null })));
  await waitFor(() => expect(screen.queryByText("事件範圍：99–99")).toBeNull());
});
