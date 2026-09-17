import { useCallback, useEffect, useState } from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AgentChatApiError, DEFAULT_WORKSPACE_ID, type RunEvent, type RunEventStream, type RunEventStreamHandlers } from "../src/api/agentChat";
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
    workspaceId: DEFAULT_WORKSPACE_ID,
    workspaceRevision: 1,
    workspaceName: "Default workspace",
    workspaceRootHash: null,
    workspaceMountManifestHash: "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
    userMessageId,
    assistantMessageId: status === "completed" ? assistantMessageId : null,
    providerId: "openrouter",
    modelId: "openrouter/auto",
    responseMode: "medium",
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
  const { setLocale, locale } = useI18n();
  const localeDependentUpdate = useCallback(() => { void locale; }, [locale]);
  const [sendResult, setSendResult] = useState<boolean | null>(null);
  const state = useConversationRun({
    conversationId: activeConversationId,
    onConversationAccepted: onAccepted ?? noop,
    onConversationUpdated: onUpdated ?? localeDependentUpdate,
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
      <div data-testid="sending">{String(state.isSending)}</div>
      <div data-testid="can-recover">{String(state.canRecover)}</div>
      <div data-testid="has-older">{String(state.hasOlderMessages)}</div>
      <button type="button" onClick={() => void state.send("hello")}>send</button>
      <button type="button" onClick={() => setLocale("en")}>change language</button>
      <div data-testid="send-result">{String(sendResult)}</div>
      <button type="button" onClick={() => void state.send("edited").then(setSendResult)}>send edited</button>
      <button type="button" onClick={() => void state.cancel()}>cancel</button>
      <button type="button" onClick={() => void state.recoverConnection()}>recover</button>
      <button type="button" onClick={() => void state.loadOlderMessages()}>load older</button>
    </div>
  );
}


beforeEach(() => {
  vi.unstubAllGlobals();
});


describe("useConversationRun", () => {
  it("stops terminal hydration recovery after three automatic attempts", async () => {
    let offline = false;
    let failedReads = 0;
    let handlers: RunEventStreamHandlers | undefined;
    const streamFactory = (_id: string, value: RunEventStreamHandlers) => { handlers = value; return { close: noop }; };
    vi.stubGlobal("fetch", vi.fn((path: string) => {
      if (offline) { failedReads += 1; return Promise.reject(new Error("offline")); }
      if (path.includes("/messages")) return Promise.resolve(new Response(JSON.stringify({ messages: [userMessage], nextBeforeSequence: null })));
      return Promise.resolve(new Response(JSON.stringify(run("running"))));
    }));
    const view = render(<Harness activeConversationId={conversationId} streamFactory={streamFactory} />);
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("running"));
    vi.useFakeTimers();
    try {
      offline = true;
      await act(async () => handlers!.onEvent({ sequence: 4, type: "run.completed", runId, conversationId, createdAt: "2026-08-21T08:30:03Z", data: { assistantMessageId, completionReason: "stop" } }));
      for (const delay of [1000, 2000, 4000]) await act(async () => { await vi.advanceTimersByTimeAsync(delay); });
      expect(failedReads).toBe(5); // Two initial GETs, then one per failed recovery.
      await act(async () => { await vi.advanceTimersByTimeAsync(60000); });
      expect(failedReads).toBe(5);
    } finally {
      view.unmount();
      vi.useRealTimers();
    }
  });

  it("reconciles the original request after a lost response even when the draft changes", async () => {
    const requests: unknown[] = [];
    vi.stubGlobal("fetch", vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/runs" && init?.method === "POST") {
        requests.push(JSON.parse(String(init.body)));
        if (requests.length === 1) return Promise.reject(new Error("response lost"));
        return Promise.resolve(new Response(JSON.stringify({ runId, conversationId, workspaceId: DEFAULT_WORKSPACE_ID, status: "queued" }), { status: 202 }));
      }
      if (path.includes("/messages")) return Promise.resolve(new Response(JSON.stringify({ messages: [userMessage], nextBeforeSequence: null })));
      return Promise.resolve(new Response(JSON.stringify(run("running"))));
    }));
    render(<I18nProvider><Harness activeConversationId={null} streamFactory={() => ({ close: noop })} /></I18nProvider>);
    fireEvent.click(screen.getByText("send"));
    await waitFor(() => expect(screen.getByTestId("error").textContent).not.toBe(""));
    fireEvent.click(screen.getByText("change language"));
    expect(screen.getByTestId("can-recover").textContent).toBe("true");
    fireEvent.click(screen.getByText("recover"));
    fireEvent.click(screen.getByText("recover"));
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("running"));
    expect(requests).toHaveLength(2);
    expect(requests[1]).toEqual(requests[0]);
    expect(requests[1]).toMatchObject({ message: "hello", clientRequestId: requestId });
  });

  it("allows edited content after a definitive initial rejection", async () => {
    const requests: { message: string }[] = [];
    vi.stubGlobal("fetch", vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/runs" && init?.method === "POST") {
        requests.push(JSON.parse(String(init.body)));
        if (requests.length === 1) return Promise.resolve(new Response(JSON.stringify({ error: { code: "invalid_request", message: "invalid", retryable: false } }), { status: 400 }));
        return Promise.resolve(new Response(JSON.stringify({ runId, conversationId, workspaceId: DEFAULT_WORKSPACE_ID, status: "queued" }), { status: 202 }));
      }
      if (path.includes("/messages")) return Promise.resolve(new Response(JSON.stringify({ messages: [userMessage], nextBeforeSequence: null })));
      return Promise.resolve(new Response(JSON.stringify(run("running"))));
    }));
    render(<Harness activeConversationId={null} streamFactory={() => ({ close: noop })} />);
    fireEvent.click(screen.getByText("send"));
    await waitFor(() => expect(screen.getByTestId("error").textContent).not.toBe(""));
    fireEvent.click(screen.getByText("send edited"));
    await waitFor(() => expect(screen.getByTestId("send-result").textContent).toBe("true"));
    expect(requests.map(request => request.message)).toEqual(["hello", "edited"]);
  });

  it("automatically hydrates a terminal Run after a temporary read failure", async () => {
    let offline = false;
    let completed = false;
    let handlers: RunEventStreamHandlers | undefined;
    const streamFactory = vi.fn((_id: string, value: RunEventStreamHandlers) => {
      handlers = value;
      return { close: noop };
    });
    vi.stubGlobal("fetch", vi.fn((path: string) => {
      if (offline) return Promise.reject(new Error("offline"));
      if (path.includes("/messages")) return Promise.resolve(new Response(JSON.stringify({ messages: completed ? [userMessage, assistantMessage] : [userMessage], nextBeforeSequence: null })));
      return Promise.resolve(new Response(JSON.stringify(run(completed ? "completed" : "running"))));
    }));
    render(<Harness activeConversationId={conversationId} streamFactory={streamFactory} />);
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("running"));
    offline = true;
    completed = true;
    act(() => handlers!.onEvent({ sequence: 4, type: "run.completed", runId, conversationId, createdAt: "2026-08-21T08:30:03Z", data: { assistantMessageId, completionReason: "stop" } }));
    await waitFor(() => expect(screen.getByTestId("error").textContent).not.toBe(""));
    offline = false;
    await waitFor(() => expect(screen.getByTestId("messages").textContent).toContain("assistant:完成"), { timeout: 3000 });
    expect(screen.getByTestId("error").textContent).toBe("");
    expect(streamFactory).toHaveBeenCalledOnce();
  });

  it("recovers an accepted Run after hydration failure without another POST", async () => {
    let available = false;
    let posts = 0;
    const streamFactory = vi.fn(() => ({ close: noop }));
    vi.stubGlobal("fetch", vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/runs" && init?.method === "POST") {
        posts += 1;
        return Promise.resolve(new Response(JSON.stringify({ runId, conversationId, workspaceId: "00000000-0000-4000-8000-000000000000", status: "queued" }), { status: 202 }));
      }
      if (!available) return Promise.reject(new Error("temporarily offline"));
      if (path.startsWith(`/api/conversations/${conversationId}/messages`)) return Promise.resolve(new Response(JSON.stringify({ messages: [userMessage], nextBeforeSequence: null })));
      if (path === `/api/runs/${runId}`) return Promise.resolve(new Response(JSON.stringify(run("running"))));
      throw new Error(`unexpected ${path}`);
    }));
    render(<Harness activeConversationId={null} streamFactory={streamFactory}/>);
    fireEvent.click(screen.getByText("send"));
    await waitFor(() => expect(screen.getByTestId("error").textContent).not.toBe(""));
    fireEvent.click(screen.getByText("send"));
    expect(posts).toBe(1);
    available = true;
    fireEvent.click(screen.getByText("recover"));
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("running"));
    expect(posts).toBe(1);
    expect(streamFactory).toHaveBeenCalledOnce();
  });

  it("blocks concurrent POSTs and reuses the request identity after a failed response", async () => {
    const pending = deferred<Response>();
    const requests: string[] = [];
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/runs" && init?.method === "POST") {
        requests.push(String(init.body));
        return requests.length === 1 ? pending.promise : Promise.reject(new Error("offline"));
      }
      throw new Error(`unexpected ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<Harness activeConversationId={null} streamFactory={() => ({ close: noop })}/>);
    fireEvent.click(screen.getByText("send"));
    fireEvent.click(screen.getByText("send"));
    expect(requests).toHaveLength(1);
    expect(screen.getByTestId("sending").textContent).toBe("true");
    await act(async () => pending.reject(new Error("connection lost")));
    expect(screen.getByTestId("sending").textContent).toBe("false");
    fireEvent.click(screen.getByText("send"));
    await waitFor(() => expect(requests).toHaveLength(2));
    expect(requests[1]).toBe(requests[0]);
    expect(screen.getByTestId("messages").textContent).toBe("user:hello");
  });

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
      if (path === "/api/runs" && init?.method === "POST") return Promise.resolve(new Response(JSON.stringify({ conversationId, workspaceId: DEFAULT_WORKSPACE_ID, runId, status: "queued" }), { status: 202 }));
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

  it("coalesces rapid streamed deltas into one animation-frame update", async () => {
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path.includes("/messages")) return Promise.resolve(new Response(JSON.stringify({ messages: [userMessage], nextBeforeSequence: null })));
      if (path === `/api/runs/${runId}`) return Promise.resolve(new Response(JSON.stringify(run("running"))));
      if (path === "/api/runs" && init?.method === "POST") return Promise.resolve(new Response(JSON.stringify({ conversationId, workspaceId: DEFAULT_WORKSPACE_ID, runId, status: "queued" }), { status: 202 }));
      throw new Error(`unexpected request ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const frames: Array<FrameRequestCallback> = [];
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      frames.push(callback);
      return frames.length;
    });
    vi.stubGlobal("cancelAnimationFrame", vi.fn());
    let handlers: RunEventStreamHandlers | null = null;
    const streamFactory = vi.fn((_runId: string, nextHandlers: RunEventStreamHandlers) => {
      handlers = nextHandlers;
      return { close: vi.fn() };
    });
    render(<Harness activeConversationId={conversationId} streamFactory={streamFactory} />);
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("running"));

    act(() => {
      handlers!.onEvent({ sequence: 3, type: "assistant.delta", runId, conversationId, createdAt: "2026-08-21T08:30:02Z", data: { text: "一" } });
      handlers!.onEvent({ sequence: 4, type: "assistant.delta", runId, conversationId, createdAt: "2026-08-21T08:30:02Z", data: { text: "次" } });
    });
    expect(screen.getByTestId("streamed").textContent).toBe("");
    expect(frames).toHaveLength(1);

    act(() => {
      frames[0]!(0);
    });
    expect(screen.getByTestId("streamed").textContent).toBe("一次");
  });

  it("buffers deltas and reveals the assembled response in complete mode", async () => {
    let runReads = 0;
    let messageReads = 0;
    const completed = { ...run("completed"), partialText: "一次" };
    const completedAssistant = { ...assistantMessage, content: "一次" };
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/runs" && init?.method === "POST") return Promise.resolve(new Response(JSON.stringify({ conversationId, workspaceId: DEFAULT_WORKSPACE_ID, runId, status: "queued" }), { status: 202 }));
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
