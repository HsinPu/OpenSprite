import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  AgentChatApiError,
  agentChatErrorText,
  cancelRun,
  getRun,
  listConversations,
  listConversationMessages,
  openRunEventStream,
  startRun,
} from "../src/api/agentChat";


const conversationId = "49d6c5e3-1724-44a7-9e69-0c0103176461";
const runId = "e7527bf5-81c9-4534-908c-a9a9bc501f26";
const userMessageId = "c01956dc-fdf0-435c-a3be-e7eb5fd65f22";


beforeEach(() => {
  vi.unstubAllGlobals();
});


describe("Agent chat HTTP contract", () => {
  it("maps Context failures to stable local guidance", () => {
    expect(agentChatErrorText(new AgentChatApiError("context_limit_exceeded"))).toContain("提高上限");
    expect(agentChatErrorText(new AgentChatApiError("context_preparation_failed"))).toContain("稍後再試");
  });

  it("strictly parses conversation and message pages", async () => {
    const fetchMock = vi.fn((path: string) => {
      if (path === "/api/conversations?limit=50") {
        return Promise.resolve(new Response(JSON.stringify({
          conversations: [{
            id: conversationId,
            title: "整理今天的工作",
            latestMessagePreview: "完成",
            createdAt: "2026-08-21T08:30:00Z",
            updatedAt: "2026-08-21T08:31:00Z",
          }],
          nextCursor: null,
        })));
      }
      if (path === `/api/conversations/${conversationId}/messages?limit=100`) {
        return Promise.resolve(new Response(JSON.stringify({
          messages: [{
            id: userMessageId,
            conversationId,
            runId,
            role: "user",
            content: "hello",
            sequence: 1,
            createdAt: "2026-08-21T08:30:00Z",
          }],
          nextBeforeSequence: null,
        })));
      }
      throw new Error(`unexpected request ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const conversations = await listConversations();
    const messages = await listConversationMessages(conversationId);

    expect(conversations.conversations[0]?.title).toBe("整理今天的工作");
    expect(messages.messages[0]?.content).toBe("hello");
  });

  it("sends an exact idempotent start request and parses Run state", async () => {
    const clientRequestId = "ba66c043-6229-469c-84b1-36f617cfc328";
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === "/api/runs") {
        expect(init).toEqual({
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            conversationId: null,
            clientRequestId,
            message: "hello",
          }),
        });
        return Promise.resolve(new Response(JSON.stringify({
          conversationId,
          runId,
          status: "queued",
        }), { status: 202 }));
      }
      if (path === `/api/runs/${runId}`) {
        return Promise.resolve(new Response(JSON.stringify({
          id: runId,
          conversationId,
          userMessageId,
          assistantMessageId: null,
          providerId: "openrouter",
          modelId: "openrouter/auto",
          responseMode: "default",
          status: "running",
          error: null,
          partialText: "回",
          createdAt: "2026-08-21T08:30:00Z",
          startedAt: "2026-08-21T08:30:01Z",
          finishedAt: null,
        })));
      }
      throw new Error(`unexpected request ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const accepted = await startRun({ conversationId: null, clientRequestId, message: "hello" });
    const run = await getRun(runId);

    expect(accepted).toEqual({ conversationId, runId, status: "queued" });
    expect(run.partialText).toBe("回");
  });

  it("maps only allowed status/code pairs and sends bodyless cancel", async () => {
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path.endsWith("/cancel")) {
        expect(init).toEqual({ method: "POST" });
        return Promise.resolve(new Response(JSON.stringify({
          error: { code: "run_not_active", message: "private", retryable: false },
        }), { status: 409 }));
      }
      throw new Error(`unexpected request ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(cancelRun(runId)).rejects.toMatchObject({
      code: "run_not_active",
    });
  });

  it("rejects extra fields and invalid identifiers as malformed", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(JSON.stringify({
      conversations: [],
      nextCursor: null,
      leaked: "field",
    })))));

    await expect(listConversations()).rejects.toEqual(
      new AgentChatApiError("malformed_response"),
    );
    await expect(getRun("not-a-uuid")).rejects.toEqual(
      new AgentChatApiError("malformed_response"),
    );
  });
});


describe("Agent chat SSE contract", () => {
  it("subscribes to named events and strictly emits safe data", () => {
    class FakeEventSource {
      static instance: FakeEventSource;
      listeners = new Map<string, (event: MessageEvent<string>) => void>();
      onerror: ((event: Event) => void) | null = null;
      closed = false;

      constructor(readonly url: string) {
        FakeEventSource.instance = this;
      }

      addEventListener(type: string, listener: EventListenerOrEventListenerObject) {
        this.listeners.set(type, listener as (event: MessageEvent<string>) => void);
      }

      close() { this.closed = true; }
    }
    vi.stubGlobal("EventSource", FakeEventSource);
    const events: unknown[] = [];
    const errors: unknown[] = [];

    const stream = openRunEventStream(runId, {
      onEvent: (event) => events.push(event),
      onError: (error) => errors.push(error),
    });
    const source = FakeEventSource.instance;
    source.listeners.get("context.compaction.started")?.(new MessageEvent("context.compaction.started", {
      data: JSON.stringify({
        sequence: 2,
        type: "context.compaction.started",
        runId,
        conversationId,
        createdAt: "2026-08-21T08:30:01Z",
        data: {},
      }),
    }));
    source.listeners.get("assistant.delta")?.(new MessageEvent("assistant.delta", {
      data: JSON.stringify({
        sequence: 3,
        type: "assistant.delta",
        runId,
        conversationId,
        createdAt: "2026-08-21T08:30:02Z",
        data: { text: "完成" },
      }),
    }));

    expect(source.url).toBe(`/api/runs/${runId}/events`);
    expect(events).toHaveLength(2);
    expect(events[0]).toMatchObject({ type: "context.compaction.started", data: {} });
    expect(errors).toEqual([]);
    stream.close();
    expect(source.closed).toBe(true);
  });

  it("closes and reports a malformed event with an uncontracted reasoning field", () => {
    class FakeEventSource {
      static instance: FakeEventSource;
      listeners = new Map<string, (event: MessageEvent<string>) => void>();
      onerror: ((event: Event) => void) | null = null;
      closed = false;
      constructor(_url: string) { FakeEventSource.instance = this; }
      addEventListener(type: string, listener: EventListenerOrEventListenerObject) { this.listeners.set(type, listener as (event: MessageEvent<string>) => void); }
      close() { this.closed = true; }
    }
    vi.stubGlobal("EventSource", FakeEventSource);
    const errors: AgentChatApiError[] = [];
    openRunEventStream(runId, { onEvent: () => undefined, onError: (error) => errors.push(error) });
    const source = FakeEventSource.instance;

    source.listeners.get("assistant.delta")?.(new MessageEvent("assistant.delta", {
      data: JSON.stringify({
        sequence: 3,
        type: "assistant.delta",
        runId,
        conversationId,
        createdAt: "2026-08-21T08:30:02Z",
        data: { text: "完成", reasoning: "hidden" },
      }),
    }));

    expect(source.closed).toBe(true);
    expect(errors[0]?.code).toBe("malformed_response");
  });
});
