import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AgentChatApiError, type RunEvent, type RunEventStreamHandlers, type RunSnapshot } from "../src/api/agentChat";
import { useRunInspection } from "../src/features/chat/useRunInspection";

const conversationId = "49d6c5e3-1724-44a7-9e69-0c0103176461";
const otherConversationId = "c7d17356-d2e6-4a5f-bbd7-7b5d6ac37875";
const firstRunId = "e7527bf5-81c9-4534-908c-a9a9bc501f26";
const secondRunId = "11111111-1111-4111-8111-111111111111";

function snapshot(id: string): RunSnapshot {
  return {
    id,
    conversationId,
    workspaceId: "00000000-0000-4000-8000-000000000000",
    workspaceRevision: 1,
    workspaceName: "Unassigned workspace",
    workspaceRootHash: null,
    userMessageId: "c01956dc-fdf0-435c-a3be-e7eb5fd65f22",
    assistantMessageId: "7e660e86-4838-4af5-99d5-ab926428b1c0",
    providerId: "openrouter",
    modelId: "openrouter/auto",
    responseMode: "default",
    status: "completed",
    completionReason: "stop",
    error: null,
    partialText: "完成",
    createdAt: "2026-08-21T08:30:00Z",
    startedAt: "2026-08-21T08:30:01Z",
    finishedAt: "2026-08-21T08:30:03Z",
  };
}

function event(runId: string, sequence: number, type: RunEvent["type"]): RunEvent {
  return {
    sequence,
    type,
    runId,
    conversationId,
    createdAt: `2026-08-21T08:30:0${sequence}Z`,
    data: type === "run.completed" ? { assistantMessageId: "7e660e86-4838-4af5-99d5-ab926428b1c0", completionReason: "stop" } : {},
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

type HarnessProps = {
  conversationId: string | null;
  getRunRequest: (runId: string) => Promise<RunSnapshot>;
  eventStreamFactory: (runId: string, handlers: RunEventStreamHandlers) => { close: () => void };
};

function Harness({ conversationId: activeConversationId, getRunRequest, eventStreamFactory }: HarnessProps) {
  const inspection = useRunInspection({
    conversationId: activeConversationId,
    getRunRequest,
    eventStreamFactory,
  });
  return <div>
    <span data-testid="selected">{inspection.selectedRunId ?? "latest"}</span>
    <span data-testid="run">{inspection.run?.id ?? "none"}</span>
    <span data-testid="events">{inspection.events.length}</span>
    <span data-testid="loading">{String(inspection.loading)}</span>
    <span data-testid="error">{inspection.error ?? ""}</span>
    <button type="button" onClick={() => void inspection.inspectRun(firstRunId)}>first</button>
    <button type="button" onClick={() => void inspection.inspectRun(secondRunId)}>second</button>
    <button type="button" onClick={inspection.returnToLatest}>latest</button>
    <button type="button" onClick={() => void inspection.retry()}>retry</button>
  </div>;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useRunInspection", () => {
  it("loads a historical snapshot and its events, then returns to latest", async () => {
    let handlers: RunEventStreamHandlers | null = null;
    const close = vi.fn();
    const getRunRequest = vi.fn(async (runId: string) => snapshot(runId));
    const eventStreamFactory = vi.fn((_runId: string, nextHandlers: RunEventStreamHandlers) => {
      handlers = nextHandlers;
      return { close };
    });
    render(<Harness conversationId={conversationId} getRunRequest={getRunRequest} eventStreamFactory={eventStreamFactory} />);

    fireEvent.click(screen.getByRole("button", { name: "first" }));
    await waitFor(() => expect(screen.getByTestId("run").textContent).toBe(firstRunId));
    expect(eventStreamFactory).toHaveBeenCalledWith(firstRunId, expect.any(Object));

    act(() => {
      handlers!.onEvent(event(firstRunId, 1, "run.started"));
      handlers!.onEvent(event(firstRunId, 2, "run.completed"));
    });
    expect(screen.getByTestId("events").textContent).toBe("2");
    expect(close).toHaveBeenCalledOnce();

    fireEvent.click(screen.getByRole("button", { name: "latest" }));
    expect(screen.getByTestId("selected").textContent).toBe("latest");
    expect(screen.getByTestId("run").textContent).toBe("none");
  });

  it("ignores a stale Run response after a newer selection", async () => {
    const first = deferred<RunSnapshot>();
    const second = deferred<RunSnapshot>();
    const getRunRequest = vi.fn((runId: string) => runId === firstRunId ? first.promise : second.promise);
    const eventStreamFactory = vi.fn(() => ({ close: vi.fn() }));
    render(<Harness conversationId={conversationId} getRunRequest={getRunRequest} eventStreamFactory={eventStreamFactory} />);

    fireEvent.click(screen.getByRole("button", { name: "first" }));
    fireEvent.click(screen.getByRole("button", { name: "second" }));
    await act(async () => first.resolve(snapshot(firstRunId)));
    expect(screen.getByTestId("selected").textContent).toBe(secondRunId);
    expect(screen.getByTestId("run").textContent).toBe("none");

    await act(async () => second.resolve(snapshot(secondRunId)));
    await waitFor(() => expect(screen.getByTestId("run").textContent).toBe(secondRunId));
    expect(eventStreamFactory).toHaveBeenCalledTimes(1);
    expect(eventStreamFactory).toHaveBeenCalledWith(secondRunId, expect.any(Object));
  });

  it("clears the inspected Run when the conversation changes", async () => {
    const close = vi.fn();
    const props = {
      getRunRequest: vi.fn(async (runId: string) => snapshot(runId)),
      eventStreamFactory: vi.fn(() => ({ close })),
    };
    function ConversationHarness() {
      const [activeConversationId, setActiveConversationId] = useState(conversationId);
      return <><Harness conversationId={activeConversationId} {...props} /><button type="button" onClick={() => setActiveConversationId(otherConversationId)}>switch conversation</button></>;
    }
    render(<ConversationHarness />);
    fireEvent.click(screen.getByRole("button", { name: "first" }));
    await waitFor(() => expect(screen.getByTestId("run").textContent).toBe(firstRunId));

    fireEvent.click(screen.getByRole("button", { name: "switch conversation" }));
    await waitFor(() => expect(screen.getByTestId("selected").textContent).toBe("latest"));
    expect(close).toHaveBeenCalledOnce();
  });

  it("exposes a safe error and retries the same Run", async () => {
    const getRunRequest = vi.fn()
      .mockRejectedValueOnce(new AgentChatApiError("database_unavailable"))
      .mockResolvedValueOnce(snapshot(firstRunId));
    const eventStreamFactory = vi.fn(() => ({ close: vi.fn() }));
    render(<Harness conversationId={conversationId} getRunRequest={getRunRequest} eventStreamFactory={eventStreamFactory} />);

    fireEvent.click(screen.getByRole("button", { name: "first" }));
    await waitFor(() => expect(screen.getByTestId("error").textContent).not.toBe(""));
    fireEvent.click(screen.getByRole("button", { name: "retry" }));

    await waitFor(() => expect(screen.getByTestId("run").textContent).toBe(firstRunId));
    expect(getRunRequest).toHaveBeenCalledTimes(2);
  });
});
