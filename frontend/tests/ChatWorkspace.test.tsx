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
      loadingOlderMessages: false,
      hasOlderMessages: false,
      error: null,
      isRunning: true,
      send: vi.fn(async () => true),
      cancel,
      loadOlderMessages: vi.fn(async () => undefined),
    });

    render(
      <ChatWorkspace
        conversationId={run.conversationId}
        modelName="GPT-5.6"
        modelSelection={{ providerId: "openrouter", modelId: run.modelId }}
        modelChoices={[{ selection: { providerId: "openrouter", modelId: run.modelId }, label: "GPT-5.6" }]}
        modelSelectionSaving={false}
        timeZone="system"
        sendBehavior="enter"
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
    expect(screen.queryByText("本機 Agent")).toBeNull();
    expect(screen.queryByRole("button", { name: "更多對話功能（尚未上線）" })).toBeNull();

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
      loadingOlderMessages: false,
      hasOlderMessages: false,
      error: null,
      isRunning: false,
      send: vi.fn(async () => true),
      cancel: vi.fn(async () => undefined),
      loadOlderMessages: vi.fn(async () => undefined),
    });

    render(
      <ChatWorkspace
        conversationId={null}
        modelName="GPT-5.6"
        modelSelection={{ providerId: "openai", modelId: "gpt-5.6" }}
        modelChoices={[{ selection: { providerId: "openai", modelId: "gpt-5.6" }, label: "GPT-5.6" }]}
        modelSelectionSaving={false}
        timeZone="system"
        sendBehavior="enter"
        onModelSelectionChange={vi.fn(async () => null)}
        onConversationAccepted={vi.fn()}
        onConversationUpdated={vi.fn()}
      />,
    );

    const sendButton = screen.getByRole("button", { name: "送出訊息" });
    const modelPicker = screen.getByRole("combobox", { name: /目前模型 GPT-5.6/ });
    expect(sendButton.querySelector("svg")).toBeTruthy();
    expect(sendButton.hasAttribute("disabled")).toBe(true);
    expect(modelPicker.closest(".chat-workspace__composer")).toBeTruthy();
    expect(modelPicker.parentElement?.classList.contains("chat-workspace__composer-primary-actions")).toBe(true);
    expect(modelPicker.parentElement?.contains(sendButton)).toBe(true);

    const composer = screen.getByRole("textbox", { name: "輸入訊息" });
    expect(composer.getAttribute("rows")).toBe("1");
    expect(document.querySelector(".chat-workspace__conversation-rail")).toBeTruthy();
    expect(document.querySelector(".chat-workspace__user-avatar")).toBeNull();

    fireEvent.change(composer, { target: { value: "hello" } });
    expect(sendButton.hasAttribute("disabled")).toBe(false);
  });

  it("sends with Enter but preserves Shift+Enter and IME composition", () => {
    const send = vi.fn(async () => true);
    mockedUseConversationRun.mockReturnValue({ messages: [], activeRun: null, events: [], streamedText: "", loading: false, loadingOlderMessages: false, hasOlderMessages: false, error: null, isRunning: false, send, cancel: vi.fn(async () => undefined), loadOlderMessages: vi.fn(async () => undefined) });
    render(<ChatWorkspace conversationId={null} modelName="GPT-5.6" modelSelection={{ providerId: "openai", modelId: "gpt-5.6" }} modelChoices={[{ selection: { providerId: "openai", modelId: "gpt-5.6" }, label: "GPT-5.6" }]} modelSelectionSaving={false} timeZone="system" sendBehavior="enter" onModelSelectionChange={vi.fn(async () => null)} onConversationAccepted={vi.fn()} onConversationUpdated={vi.fn()} />);
    const composer = screen.getByRole("textbox", { name: "輸入訊息" });
    fireEvent.change(composer, { target: { value: "hello" } });
    fireEvent.keyDown(composer, { key: "Enter", shiftKey: true });
    fireEvent.keyDown(composer, { key: "Enter", isComposing: true });
    expect(send).not.toHaveBeenCalled();

    fireEvent.keyDown(composer, { key: "Enter" });
    expect(send).toHaveBeenCalledWith("hello");
  });

  it("uses Ctrl or Cmd Enter in modifier mode", () => {
    const send = vi.fn(async () => true);
    mockedUseConversationRun.mockReturnValue({ messages: [], activeRun: null, events: [], streamedText: "", loading: false, loadingOlderMessages: false, hasOlderMessages: false, error: null, isRunning: false, send, cancel: vi.fn(async () => undefined), loadOlderMessages: vi.fn(async () => undefined) });
    render(<ChatWorkspace conversationId={null} modelName="GPT-5.6" modelSelection={{ providerId: "openai", modelId: "gpt-5.6" }} modelChoices={[{ selection: { providerId: "openai", modelId: "gpt-5.6" }, label: "GPT-5.6" }]} modelSelectionSaving={false} timeZone="system" sendBehavior="modifier-enter" onModelSelectionChange={vi.fn(async () => null)} onConversationAccepted={vi.fn()} onConversationUpdated={vi.fn()} />);
    const composer = screen.getByRole("textbox", { name: "輸入訊息" });
    fireEvent.change(composer, { target: { value: "hello" } });
    fireEvent.keyDown(composer, { key: "Enter" });
    expect(send).not.toHaveBeenCalled();

    fireEvent.keyDown(composer, { key: "Enter", ctrlKey: true });
    expect(send).toHaveBeenCalledWith("hello");
  });
});
