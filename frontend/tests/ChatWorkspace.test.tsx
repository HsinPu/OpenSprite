import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { RunEvent, RunSnapshot } from "../src/api/agentChat";
import { ChatWorkspace } from "../src/features/chat/ChatWorkspace";
import { useConversationRun } from "../src/features/chat/useConversationRun";


vi.mock("../src/features/chat/useConversationRun", () => ({
  useConversationRun: vi.fn(),
}));

const run: RunSnapshot = {
  id: "11111111-1111-4111-8111-111111111111",
  conversationId: "22222222-2222-4222-8222-222222222222",
  userMessageId: "33333333-3333-4333-8333-333333333333",
  assistantMessageId: null,
  providerId: "openrouter",
  modelId: "openai/gpt-5.6",
  responseMode: "default",
  status: "running",
  error: null,
  partialText: "正在整理",
  createdAt: "2026-08-22T08:00:00Z",
  startedAt: "2026-08-22T08:00:01Z",
  finishedAt: null,
};

const events: RunEvent[] = [
  { sequence: 1, type: "run.started", runId: run.id, conversationId: run.conversationId, createdAt: "2026-08-22T08:00:01Z", data: {} },
  { sequence: 2, type: "model.started", runId: run.id, conversationId: run.conversationId, createdAt: "2026-08-22T08:00:02Z", data: { modelId: run.modelId } },
  { sequence: 3, type: "assistant.delta", runId: run.id, conversationId: run.conversationId, createdAt: "2026-08-22T08:00:03Z", data: { text: "正在整理" } },
];

const mockedUseConversationRun = vi.mocked(useConversationRun);

beforeEach(() => {
  mockedUseConversationRun.mockReset();
});

describe("live chat workspace", () => {
  it("shows the real run, exposes cancellation, and does not advertise fake tools", () => {
    const cancel = vi.fn(async () => undefined);
    mockedUseConversationRun.mockReturnValue({
      messages: [{
        id: run.userMessageId,
        role: "user",
        content: "整理今天的工作",
        createdAt: run.createdAt,
        delivery: "persisted",
      }],
      activeRun: run,
      events,
      streamedText: "正在整理",
      loading: false,
      error: null,
      isRunning: true,
      send: vi.fn(async () => true),
      cancel,
    });

    render(
      <ChatWorkspace
        conversationId={run.conversationId}
        modelName="GPT-5.6"
        modelSelection={{ providerId: "openrouter", modelId: run.modelId }}
        modelChoices={[{ selection: { providerId: "openrouter", modelId: run.modelId }, label: "GPT-5.6" }]}
        modelSelectionSaving={false}
        timeZone="system"
        onModelSelectionChange={vi.fn(async () => null)}
        onConversationAccepted={vi.fn()}
        onConversationUpdated={vi.fn()}
        title="整理今天的工作"
      />,
    );

    expect(screen.getByText("正在整理")).toBeTruthy();
    expect(screen.getByText("openrouter · openai/gpt-5.6 · 廠商預設")).toBeTruthy();
    expect(screen.getByText("本次執行沒有使用額外工具。")).toBeTruthy();
    expect(screen.queryByText("Search")).toBeNull();
    expect(screen.queryByText("File")).toBeNull();
    expect(screen.queryByText("Memory")).toBeNull();

    const stopButton = screen.getByRole("button", { name: "停止回覆" });
    expect(stopButton.querySelector("svg")).toBeTruthy();
    fireEvent.click(stopButton);
    expect(cancel).toHaveBeenCalledOnce();
  });

  it("uses a stable icon and enables send only after text is entered", () => {
    mockedUseConversationRun.mockReturnValue({
      messages: [],
      activeRun: null,
      events: [],
      streamedText: "",
      loading: false,
      error: null,
      isRunning: false,
      send: vi.fn(async () => true),
      cancel: vi.fn(async () => undefined),
    });

    render(
      <ChatWorkspace
        conversationId={null}
        modelName="GPT-5.6"
        modelSelection={{ providerId: "openai", modelId: "gpt-5.6" }}
        modelChoices={[{ selection: { providerId: "openai", modelId: "gpt-5.6" }, label: "GPT-5.6" }]}
        modelSelectionSaving={false}
        timeZone="system"
        onModelSelectionChange={vi.fn(async () => null)}
        onConversationAccepted={vi.fn()}
        onConversationUpdated={vi.fn()}
      />,
    );

    const sendButton = screen.getByRole("button", { name: "送出訊息" });
    expect(sendButton.querySelector("svg")).toBeTruthy();
    expect(sendButton.hasAttribute("disabled")).toBe(true);

    const composer = screen.getByRole("textbox", { name: "輸入訊息" });
    expect(composer.getAttribute("rows")).toBe("1");
    expect(document.querySelector(".chat-workspace__conversation-rail")).toBeTruthy();
    expect(document.querySelector(".chat-workspace__user-avatar")).toBeNull();

    fireEvent.change(composer, { target: { value: "hello" } });
    expect(sendButton.hasAttribute("disabled")).toBe(false);
  });
});
