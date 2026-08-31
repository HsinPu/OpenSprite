import { useEffect } from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AgentChatApiError, type RunEvent, type RunEventStream, type RunEventStreamHandlers } from "../src/api/agentChat";
import type { ResponseDelivery } from "../src/api/aiSettings";
import { useConversationRun } from "../src/features/chat/useConversationRun";
import { I18nProvider, useI18n } from "../src/i18n/I18nProvider";
import type { Locale } from "../src/i18n/catalog";


const conversationId = "49d6c5e3-1724-44a7-9e69-0c0103176461";
const runId = "e7527bf5-81c9-4534-908c-a9a9bc501f26";
const userMessageId = "c01956dc-fdf0-435c-a3be-e7eb5fd65f22";
const assistantMessageId = "7e660e86-4838-4af5-99d5-ab926428b1c0";
const requestId = "ba66c043-6229-469c-84b1-36f617cfc328";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}


const userMessage = {
  id: userMessageId,
  conversationId,
  runId,
  role: "user",
  content: "hello",
  sequence: 1,
  createdAt: "2026-08-21T08:30:00Z",
};

const assistantMessage = {
  id: assistantMessageId,
  conversationId,
  runId,
  role: "assistant",
  content: "完成",
  sequence: 2,
  createdAt: "2026-08-21T08:30:03Z",
};

function run(status: "running" | "cancelling" | "completed") {
  return {
    id: runId,
    conversationId,
    userMessageId,
    assistantMessageId: status === "completed" ? assistantMessageId : null,
    providerId: "openrouter",
    modelId: "openrouter/auto",
    responseMode: "default",
    status,
    completionReason: status === "completed" ? "stop" : null,
    error: null,
    partialText: status === "completed" ? "完成" : "",
    createdAt: "2026-08-21T08:30:00Z",
    startedAt: "2026-08-21T08:30:01Z",
    finishedAt: status === "completed" ? "2026-08-21T08:30:03Z" : null,
  };
}

type HarnessProps = {
  activeConversationId: string | null;
  streamFactory: (runId: string, handlers: RunEventStreamHandlers) => RunEventStream;
  responseDelivery?: ResponseDelivery;
  onAccepted?: (conversationId: string, firstMessage: string) => void;
  onUpdated?: () => void;
};

const noop = () => undefined;

function LocaleSetter({ locale }: { locale: Locale }) {
  const { setLocale } = useI18n();

  useEffect(() => {
    setLocale(locale);
  }, [locale, setLocale]);

  return null;
}

function Harness({ activeConversationId, streamFactory, responseDelivery = "stream", onAccepted, onUpdated }: HarnessProps) {
  const state = useConversationRun({
    conversationId: activeConversationId,
    onConversationAccepted: onAccepted ?? noop,
    onConversationUpdated: onUpdated ?? noop,
    responseDelivery,
    requestIdFactory: () => requestId,
    eventStreamFactory: streamFactory,
  });
  return (
    <div>
      <div data-testid="messages">{state.messages.map((message) => `${message.role}:${message.content}`).join("|")}</div>
      <div data-testid="message-runs">{state.messages.map((message) => message.runId ?? "pending").join("|")}</div>
      <div data-testid="streamed">{state.streamedText}</div>
      <div data-testid="status">{state.activeRun?.status ?? "none"}</div>
      <div data-testid="error">{state.error ?? ""}</div>
      <div data-testid="has-older">{String(state.hasOlderMessages)}</div>
      <button type="button" onClick={() => void state.send("hello")}>send</button>
      <button type="button" onClick={() => void state.cancel()}>cancel</button>
      <button type="button" onClick={() => void state.loadOlderMessages()}>load older</button>
    </div>
  );
}


beforeEach(() => {
  vi.unstubAllGlobals();
});


describe("useConversationRun", () => {
  it("loads persisted messages and the latest Run for a conversation", async () => {
    const fetchMock = vi.fn((path: string) => {
      if (path.includes("/messages")) return Promise.resolve(new Response(JSON.stringify({ messages: [userMessage, assistantMessage], nextBeforeSequence: null })));
      if (path === `/api/runs/${runId}`) return Promise.resolve(new Response(JSON.stringify(run("completed"))));
      throw new Error(`unexpected request ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const streamFactory = vi.fn(() => ({ close: vi.fn() }));

    render(<Harness activeConversationId={conversationId} streamFactory={streamFactory} />);

    await waitFor(() => expect(screen.getByTestId("messages").textContent).toContain("assistant:完成"));
    expect(screen.getByTestId("message-runs").textContent).toBe(`${runId}|${runId}`);
    expect(screen.getByTestId("status").textContent).toBe("completed");
    expect(streamFactory).toHaveBeenCalledWith(runId, expect.any(Object));
  });

  it("starts a new Run, streams text, then reloads durable messages at terminal", async () => {
    let runReads = 0;
    let messageReads = 0;
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/runs" && init?.method === "POST") return Promise.resolve(new Response(JSON.stringify({ conversationId, runId, status: "queued" }), { status: 202 }));
      if (path === `/api/runs/${runId}`) {
        runReads += 1;
        return Promise.resolve(new Response(JSON.stringify(run(runReads === 1 ? "running" : "completed"))));
      }
      if (path.includes("/messages")) {
        messageReads += 1;
        return Promise.resolve(new Response(JSON.stringify({ messages: messageReads === 1 ? [userMessage] : [userMessage, assistantMessage], nextBeforeSequence: null })));
      }
      throw new Error(`unexpected request ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    let handlers: RunEventStreamHandlers | null = null;
    const streamFactory = vi.fn((_runId: string, nextHandlers: RunEventStreamHandlers) => {
      handlers = nextHandlers;
      return { close: vi.fn() };
    });
    const accepted = vi.fn();
    const updated = vi.fn();
    render(<Harness activeConversationId={null} streamFactory={streamFactory} onAccepted={accepted} onUpdated={updated} />);

    fireEvent.click(screen.getByRole("button", { name: "send" }));
    await waitFor(() => expect(accepted).toHaveBeenCalledWith(conversationId, "hello"));
    expect(screen.getByTestId("messages").textContent).toContain("user:hello");
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("running"));

    const delta: RunEvent = { sequence: 3, type: "assistant.delta", runId, conversationId, createdAt: "2026-08-21T08:30:02Z", data: { text: "完成" } };
    act(() => handlers!.onEvent(delta));
    await waitFor(() => expect(screen.getByTestId("streamed").textContent).toBe("完成"));
    act(() => {
      handlers!.onEvent({ sequence: 4, type: "run.completed", runId, conversationId, createdAt: "2026-08-21T08:30:03Z", data: { assistantMessageId, completionReason: "stop" } });
    });

    await waitFor(() => expect(screen.getByTestId("messages").textContent).toContain("assistant:完成"));
    expect(screen.getByTestId("status").textContent).toBe("completed");
    expect(updated).toHaveBeenCalled();
  });

  it("buffers deltas and reveals the assembled response in complete mode", async () => {
    let runReads = 0;
    let messageReads = 0;
    const completed = { ...run("completed"), partialText: "一次" };
    const completedAssistant = { ...assistantMessage, content: "一次" };
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/runs" && init?.method === "POST") return Promise.resolve(new Response(JSON.stringify({ conversationId, runId, status: "queued" }), { status: 202 }));
      if (path === `/api/runs/${runId}`) {
        runReads += 1;
        return Promise.resolve(new Response(JSON.stringify(runReads === 1 ? run("running") : completed)));
      }
      if (path.includes("/messages")) {
        messageReads += 1;
        return Promise.resolve(new Response(JSON.stringify({ messages: messageReads === 1 ? [userMessage] : [userMessage, completedAssistant], nextBeforeSequence: null })));
      }
      throw new Error(`unexpected request ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    let handlers: RunEventStreamHandlers | null = null;
    const streamFactory = vi.fn((_runId: string, nextHandlers: RunEventStreamHandlers) => {
      handlers = nextHandlers;
      return { close: vi.fn() };
    });
    render(<Harness activeConversationId={null} streamFactory={streamFactory} responseDelivery="complete" />);

    fireEvent.click(screen.getByRole("button", { name: "send" }));
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("running"));
    act(() => handlers!.onEvent({ sequence: 3, type: "assistant.delta", runId, conversationId, createdAt: "2026-08-21T08:30:02Z", data: { text: "一" } }));
    act(() => handlers!.onEvent({ sequence: 4, type: "assistant.delta", runId, conversationId, createdAt: "2026-08-21T08:30:02Z", data: { text: "次" } }));
    expect(screen.getByTestId("streamed").textContent).toBe("");

    act(() => handlers!.onEvent({ sequence: 5, type: "run.completed", runId, conversationId, createdAt: "2026-08-21T08:30:03Z", data: { assistantMessageId, completionReason: "stop" } }));
    await waitFor(() => expect(screen.getByTestId("streamed").textContent).toBe("一次"));
    expect(screen.getByTestId("messages").textContent).toContain("assistant:一次");
  });

  it("keeps buffered partial text visible when complete mode ends with an error", async () => {
    let runReads = 0;
    const terminalError = { code: "provider_unreachable", message: "private", retryable: true } as const;
    const failed = { ...run("completed"), status: "failed", assistantMessageId: null, completionReason: null, partialText: "部分", error: terminalError };
    const fetchMock = vi.fn((path: string) => {
      if (path.includes("/messages")) return Promise.resolve(new Response(JSON.stringify({ messages: [userMessage], nextBeforeSequence: null })));
      if (path === `/api/runs/${runId}`) {
        runReads += 1;
        return Promise.resolve(new Response(JSON.stringify(runReads === 1 ? run("running") : failed)));
      }
      throw new Error(`unexpected request ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    let handlers: RunEventStreamHandlers | null = null;
    const streamFactory = vi.fn((_runId: string, nextHandlers: RunEventStreamHandlers) => {
      handlers = nextHandlers;
      return { close: vi.fn() };
    });
    render(<Harness activeConversationId={conversationId} streamFactory={streamFactory} responseDelivery="complete" />);
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("running"));

    act(() => handlers!.onEvent({ sequence: 3, type: "assistant.delta", runId, conversationId, createdAt: "2026-08-21T08:30:02Z", data: { text: "部分" } }));
    expect(screen.getByTestId("streamed").textContent).toBe("");
    act(() => handlers!.onEvent({ sequence: 4, type: "run.failed", runId, conversationId, createdAt: "2026-08-21T08:30:03Z", data: { error: terminalError } }));

    await waitFor(() => expect(screen.getByTestId("streamed").textContent).toBe("部分"));
    expect(screen.getByTestId("status").textContent).toBe("failed");
  });

  it("requests cancellation and exposes cancelling state", async () => {
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path.includes("/messages")) return Promise.resolve(new Response(JSON.stringify({ messages: [userMessage], nextBeforeSequence: null })));
      if (path === `/api/runs/${runId}`) return Promise.resolve(new Response(JSON.stringify(run("running"))));
      if (path === `/api/runs/${runId}/cancel` && init?.method === "POST") return Promise.resolve(new Response(JSON.stringify({ runId, status: "cancelling" }), { status: 202 }));
      throw new Error(`unexpected request ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const streamFactory = vi.fn(() => ({ close: vi.fn() }));
    render(<Harness activeConversationId={conversationId} streamFactory={streamFactory} />);
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("running"));

    fireEvent.click(screen.getByRole("button", { name: "cancel" }));

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("cancelling"));
  });

  it("leaves the active state and closes SSE immediately when terminal refresh fails", async () => {
    let runReads = 0;
    const fetchMock = vi.fn((path: string) => {
      if (path.includes("/messages")) return Promise.resolve(new Response(JSON.stringify({ messages: [userMessage], nextBeforeSequence: null })));
      if (path === `/api/runs/${runId}`) {
        runReads += 1;
        if (runReads === 1) return Promise.resolve(new Response(JSON.stringify(run("running"))));
        return Promise.reject(new Error("temporary read failure"));
      }
      throw new Error(`unexpected request ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    let handlers: RunEventStreamHandlers | null = null;
    const close = vi.fn();
    const streamFactory = vi.fn((_runId: string, nextHandlers: RunEventStreamHandlers) => {
      handlers = nextHandlers;
      return { close };
    });
    render(<Harness activeConversationId={conversationId} streamFactory={streamFactory} />);
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("running"));

    act(() => handlers!.onEvent({ sequence: 4, type: "run.completed", runId, conversationId, createdAt: "2026-08-21T08:30:03Z", data: { assistantMessageId, completionReason: "stop" } }));

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("completed"));
    expect(close).toHaveBeenCalledOnce();
    await waitFor(() => expect(screen.getByTestId("error").textContent).toContain("無法連線到本機服務"));
  });

  it("localizes a terminal Run error from its code instead of exposing the backend message", async () => {
    let runReads = 0;
    const backendMessage = "private backend detail";
    const terminalError = { code: "provider_unreachable", message: backendMessage, retryable: true } as const;
    const fetchMock = vi.fn((path: string) => {
      if (path.includes("/messages")) return Promise.resolve(new Response(JSON.stringify({ messages: [userMessage], nextBeforeSequence: null })));
      if (path === `/api/runs/${runId}`) {
        runReads += 1;
        const snapshot = runReads === 1
          ? run("running")
          : { ...run("completed"), status: "failed", assistantMessageId: null, completionReason: null, error: terminalError };
        return Promise.resolve(new Response(JSON.stringify(snapshot)));
      }
      throw new Error(`unexpected request ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    let handlers: RunEventStreamHandlers | null = null;
    const streamFactory = vi.fn((_runId: string, nextHandlers: RunEventStreamHandlers) => {
      handlers = nextHandlers;
      return { close: vi.fn() };
    });

    render(
      <I18nProvider>
        <LocaleSetter locale="en" />
        <Harness activeConversationId={conversationId} streamFactory={streamFactory} />
      </I18nProvider>,
    );
    await waitFor(() => expect(document.documentElement.lang).toBe("en"));
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("running"));

    act(() => handlers!.onEvent({
      sequence: 4,
      type: "run.failed",
      runId,
      conversationId,
      createdAt: "2026-08-21T08:30:03Z",
      data: { error: terminalError },
    }));

    await waitFor(() => expect(screen.getByTestId("error").textContent).toBe("The model provider is temporarily unreachable."));
    expect(screen.getByTestId("error").textContent).not.toContain(backendMessage);
  });

  it("keeps persisted partial text when SSE cannot start replaying", async () => {
    const fetchMock = vi.fn((path: string) => {
      if (path.includes("/messages")) return Promise.resolve(new Response(JSON.stringify({ messages: [userMessage], nextBeforeSequence: null })));
      if (path === `/api/runs/${runId}`) return Promise.resolve(new Response(JSON.stringify({ ...run("running"), partialText: "既有部分回覆" })));
      throw new Error(`unexpected request ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const streamFactory = vi.fn((_runId: string, handlers: RunEventStreamHandlers) => {
      handlers.onError(new AgentChatApiError("network_error"));
      return { close: vi.fn() };
    });

    render(<Harness activeConversationId={conversationId} streamFactory={streamFactory} />);

    await waitFor(() => expect(screen.getByTestId("streamed").textContent).toBe("既有部分回覆"));
  });

  it("does not show a stale cancellation error after switching conversations", async () => {
    const cancellation = deferred<Response>();
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path.includes("/messages")) return Promise.resolve(new Response(JSON.stringify({ messages: [userMessage], nextBeforeSequence: null })));
      if (path === `/api/runs/${runId}`) return Promise.resolve(new Response(JSON.stringify(run("running"))));
      if (path === `/api/runs/${runId}/cancel` && init?.method === "POST") return cancellation.promise;
      throw new Error(`unexpected request ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const streamFactory = vi.fn(() => ({ close: vi.fn() }));
    const rendered = render(<Harness activeConversationId={conversationId} streamFactory={streamFactory} />);
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("running"));
    fireEvent.click(screen.getByRole("button", { name: "cancel" }));

    rendered.rerender(<Harness activeConversationId={null} streamFactory={streamFactory} />);
    cancellation.reject(new Error("old request failed"));

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("none"));
    expect(screen.getByTestId("error").textContent).toBe("");
  });

  it("loads and prepends an older message page", async () => {
    const olderMessage = {
      ...userMessage,
      id: "8e56f1ba-2ec1-49ea-a414-cb59f50350cb",
      content: "older",
      sequence: 1,
    };
    const latestMessage = { ...userMessage, sequence: 101 };
    const fetchMock = vi.fn((path: string) => {
      if (path.endsWith("/messages?limit=100")) return Promise.resolve(new Response(JSON.stringify({ messages: [latestMessage], nextBeforeSequence: 101 })));
      if (path.endsWith("/messages?limit=100&beforeSequence=101")) return Promise.resolve(new Response(JSON.stringify({ messages: [olderMessage], nextBeforeSequence: null })));
      if (path === `/api/runs/${runId}`) return Promise.resolve(new Response(JSON.stringify(run("completed"))));
      throw new Error(`unexpected request ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<Harness activeConversationId={conversationId} streamFactory={() => ({ close: vi.fn() })} />);
    await waitFor(() => expect(screen.getByTestId("has-older").textContent).toBe("true"));

    fireEvent.click(screen.getByRole("button", { name: "load older" }));

    await waitFor(() => expect(screen.getByTestId("messages").textContent).toContain("user:older|user:hello"));
    expect(screen.getByTestId("has-older").textContent).toBe("false");
  });
});
