import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { RunEvent, RunSnapshot } from "../src/api/agentChat";
import { ChatWorkspace } from "../src/features/chat/ChatWorkspace";
import { useConversationRun } from "../src/features/chat/useConversationRun";
import { useRunInspection } from "../src/features/chat/useRunInspection";
import { useConversationAutoScroll } from "../src/features/chat/useConversationAutoScroll";
import type { ModelSelection } from "../src/features/ai-settings/modelCatalog";


vi.mock("../src/features/chat/useConversationRun", () => ({
  useConversationRun: vi.fn(),
}));
vi.mock("../src/features/chat/useRunInspection", () => ({
  useRunInspection: vi.fn(),
}));
vi.mock("../src/features/chat/useConversationAutoScroll", () => ({
  useConversationAutoScroll: vi.fn(),
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
const mockedUseRunInspection = vi.mocked(useRunInspection);
const mockedUseConversationAutoScroll = vi.mocked(useConversationAutoScroll);
const selection = (providerId: ModelSelection["providerId"], modelId: string): ModelSelection => ({ providerId, modelId, contextBudget: "auto" });
const inspectRun = vi.fn(async () => undefined);
const returnToLatest = vi.fn();
const followLatest = vi.fn();
const preservePositionWhilePrepending = vi.fn(async (load: () => Promise<void>) => load());

beforeEach(() => {
  mockedUseConversationRun.mockReset();
  mockedUseRunInspection.mockReset();
  inspectRun.mockClear();
  returnToLatest.mockClear();
  followLatest.mockClear();
  preservePositionWhilePrepending.mockClear();
  mockedUseConversationAutoScroll.mockReset();
  mockedUseConversationAutoScroll.mockReturnValue({
    containerRef: { current: null },
    onScroll: vi.fn(),
    followLatest,
    preservePositionWhilePrepending,
  });
  mockedUseRunInspection.mockReturnValue({
    selectedRunId: null,
    run: null,
    events: [],
    loading: false,
    error: null,
    inspectRun,
    retry: vi.fn(async () => undefined),
    returnToLatest,
  });
});

describe("live chat workspace", () => {
  it("shows localized timestamps beneath persisted user and assistant messages", () => {
    mockedUseConversationRun.mockReturnValue({
      messages: [
        { id: run.userMessageId, runId: run.id, role: "user", content: "你好", createdAt: "2026-08-22T08:00:00Z", delivery: "persisted" },
        { id: "44444444-4444-4444-8444-444444444444", runId: run.id, role: "assistant", content: "你好！", createdAt: "2026-08-22T08:00:07Z", delivery: "persisted" },
      ],
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

    render(<ChatWorkspace conversationId={run.conversationId} modelName="GPT-5.6" modelSelection={selection("openrouter", run.modelId)} modelChoices={[{ selection: selection("openrouter", run.modelId), label: "GPT-5.6" }]} modelSelectionSaving={false} timeZone="Asia/Taipei" sendBehavior="enter" autoScroll executionPanelDefaultExpanded={false} onModelSelectionChange={vi.fn(async () => null)} onConversationAccepted={vi.fn()} onConversationUpdated={vi.fn()} />);

    const timestamps = Array.from(document.querySelectorAll("time.chat-workspace__message-time"));
    expect(timestamps).toHaveLength(2);
    expect(timestamps.map((element) => element.getAttribute("datetime"))).toEqual([
      "2026-08-22T08:00:00Z",
      "2026-08-22T08:00:07Z",
    ]);
    const viewExecution = screen.getByRole("button", { name: "查看這次執行" });
    fireEvent.click(viewExecution);
    expect(inspectRun).toHaveBeenCalledWith(run.id);
  });

  it("shows a fallback inspection action for a terminal Run without an assistant reply", () => {
    const failedRun: RunSnapshot = { ...run, status: "failed", assistantMessageId: null, finishedAt: "2026-08-22T08:00:04Z", error: { code: "provider_unreachable", message: "safe", retryable: true } };
    mockedUseConversationRun.mockReturnValue({ messages: [{ id: run.userMessageId, runId: run.id, role: "user", content: "你好", createdAt: run.createdAt, delivery: "persisted" }], activeRun: failedRun, events: [], streamedText: "", loading: false, loadingOlderMessages: false, hasOlderMessages: false, error: null, isRunning: false, send: vi.fn(async () => true), cancel: vi.fn(async () => undefined), loadOlderMessages: vi.fn(async () => undefined) });
    render(<ChatWorkspace conversationId={run.conversationId} modelName="GPT-5.6" modelSelection={selection("openrouter", run.modelId)} modelChoices={[{ selection: selection("openrouter", run.modelId), label: "GPT-5.6" }]} modelSelectionSaving={false} timeZone="system" sendBehavior="enter" autoScroll executionPanelDefaultExpanded={false} onModelSelectionChange={vi.fn(async () => null)} onConversationAccepted={vi.fn()} onConversationUpdated={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "查看這次執行" }));
    expect(inspectRun).toHaveBeenCalledWith(run.id);
  });

  it("shows the selected historical Run and returns to the latest execution", () => {
    const historicalRun: RunSnapshot = { ...run, status: "completed", assistantMessageId: "44444444-4444-4444-8444-444444444444", modelId: "historic/model", partialText: "歷史完成", finishedAt: "2026-08-22T08:00:07Z" };
    mockedUseRunInspection.mockReturnValue({ selectedRunId: run.id, run: historicalRun, events, loading: false, error: null, inspectRun, retry: vi.fn(async () => undefined), returnToLatest });
    mockedUseConversationRun.mockReturnValue({ messages: [{ id: run.userMessageId, runId: run.id, role: "user", content: "你好", createdAt: run.createdAt, delivery: "persisted" }, { id: historicalRun.assistantMessageId!, runId: run.id, role: "assistant", content: "歷史完成", createdAt: historicalRun.finishedAt!, delivery: "persisted" }], activeRun: run, events: [], streamedText: "正在整理", loading: false, loadingOlderMessages: false, hasOlderMessages: false, error: null, isRunning: true, send: vi.fn(async () => true), cancel: vi.fn(async () => undefined), loadOlderMessages: vi.fn(async () => undefined) });
    render(<ChatWorkspace conversationId={run.conversationId} modelName="目前模型" modelSelection={selection("openrouter", run.modelId)} modelChoices={[{ selection: selection("openrouter", run.modelId), label: "目前模型" }, { selection: selection("openrouter", historicalRun.modelId), label: "歷史模型" }]} modelSelectionSaving={false} timeZone="system" sendBehavior="enter" autoScroll executionPanelDefaultExpanded={false} onModelSelectionChange={vi.fn(async () => null)} onConversationAccepted={vi.fn()} onConversationUpdated={vi.fn()} />);

    expect(screen.getByRole("button", { name: "正在查看這次執行" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("heading", { level: 2, name: "執行詳情" })).toBeTruthy();
    expect(within(screen.getByRole("complementary", { name: "執行詳情" })).getAllByText("歷史模型").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "回到最新執行" }));
    expect(returnToLatest).toHaveBeenCalledOnce();
  });

  it("shows a safe historical inspection error and retries without affecting chat", () => {
    const retry = vi.fn(async () => undefined);
    mockedUseRunInspection.mockReturnValue({ selectedRunId: run.id, run: null, events: [], loading: false, error: "執行紀錄暫時無法讀取。", inspectRun, retry, returnToLatest });
    mockedUseConversationRun.mockReturnValue({ messages: [{ id: run.userMessageId, runId: run.id, role: "user", content: "你好", createdAt: run.createdAt, delivery: "persisted" }, { id: "44444444-4444-4444-8444-444444444444", runId: run.id, role: "assistant", content: "你好！", createdAt: "2026-08-22T08:00:07Z", delivery: "persisted" }], activeRun: run, events, streamedText: "正在整理", loading: false, loadingOlderMessages: false, hasOlderMessages: false, error: null, isRunning: true, send: vi.fn(async () => true), cancel: vi.fn(async () => undefined), loadOlderMessages: vi.fn(async () => undefined) });
    render(<ChatWorkspace conversationId={run.conversationId} modelName="目前模型" modelSelection={selection("openrouter", run.modelId)} modelChoices={[{ selection: selection("openrouter", run.modelId), label: "目前模型" }]} modelSelectionSaving={false} timeZone="system" sendBehavior="enter" autoScroll executionPanelDefaultExpanded={false} onModelSelectionChange={vi.fn(async () => null)} onConversationAccepted={vi.fn()} onConversationUpdated={vi.fn()} />);

    expect(screen.getByRole("alert").textContent).toContain("執行紀錄暫時無法讀取");
    fireEvent.click(screen.getByRole("button", { name: "重試" }));
    expect(retry).toHaveBeenCalledOnce();
    expect(screen.getByText("你好！")).toBeTruthy();
  });

  it("shows the real run, exposes cancellation, and does not advertise fake tools", () => {
    const cancel = vi.fn(async () => undefined);
    mockedUseConversationRun.mockReturnValue({
      messages: [{
        id: run.userMessageId,
        runId: run.id,
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
        modelSelection={selection("openrouter", run.modelId)}
        modelChoices={[{ selection: selection("openrouter", run.modelId), label: "GPT-5.6" }]}
        modelSelectionSaving={false}
        timeZone="system"
        sendBehavior="enter"
        autoScroll
        executionPanelDefaultExpanded={false}
        onModelSelectionChange={vi.fn(async () => null)}
        onConversationAccepted={vi.fn()}
        onConversationUpdated={vi.fn()}
        title="整理今天的工作"
      />,
    );

    expect(screen.getByText("正在整理")).toBeTruthy();
    expect(screen.getByText("openrouter · openai/gpt-5.6 · 廠商預設")).toBeTruthy();
    expect(screen.getByText("本次執行沒有使用額外工具。")).toBeTruthy();
    const recordSummary = screen.getByText("執行紀錄").closest("summary");
    expect(recordSummary?.querySelector(".anticon-down")).toBeTruthy();
    expect(recordSummary?.textContent).not.toContain("⌄");
    expect(screen.queryByText("Search")).toBeNull();
    expect(screen.queryByText("File")).toBeNull();
    expect(screen.queryByText("Memory")).toBeNull();
    expect(screen.queryByText("本機 Agent")).toBeNull();
    expect(screen.queryByRole("button", { name: "更多對話功能（尚未上線）" })).toBeNull();
    expect(screen.queryByRole("button", { name: "查看這次執行" })).toBeNull();

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
        modelSelection={selection("openai", "gpt-5.6")}
        modelChoices={[{ selection: selection("openai", "gpt-5.6"), label: "GPT-5.6" }]}
        modelSelectionSaving={false}
        timeZone="system"
        sendBehavior="enter"
        autoScroll
        executionPanelDefaultExpanded={false}
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

  it("preserves the reading position while loading older messages", () => {
    const loadOlderMessages = vi.fn(async () => undefined);
    mockedUseConversationRun.mockReturnValue({ messages: [], activeRun: null, events: [], streamedText: "", loading: false, loadingOlderMessages: false, hasOlderMessages: true, error: null, isRunning: false, send: vi.fn(async () => true), cancel: vi.fn(async () => undefined), loadOlderMessages });
    render(<ChatWorkspace conversationId={run.conversationId} modelName="GPT-5.6" modelSelection={selection("openrouter", run.modelId)} modelChoices={[{ selection: selection("openrouter", run.modelId), label: "GPT-5.6" }]} modelSelectionSaving={false} timeZone="system" sendBehavior="enter" autoScroll executionPanelDefaultExpanded={false} onModelSelectionChange={vi.fn(async () => null)} onConversationAccepted={vi.fn()} onConversationUpdated={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "載入較早訊息" }));
    expect(preservePositionWhilePrepending).toHaveBeenCalledOnce();
    expect(loadOlderMessages).toHaveBeenCalledOnce();
  });

  it("sends with Enter but preserves Shift+Enter and IME composition", () => {
    const send = vi.fn(async () => true);
    mockedUseConversationRun.mockReturnValue({ messages: [], activeRun: null, events: [], streamedText: "", loading: false, loadingOlderMessages: false, hasOlderMessages: false, error: null, isRunning: false, send, cancel: vi.fn(async () => undefined), loadOlderMessages: vi.fn(async () => undefined) });
    render(<ChatWorkspace conversationId={null} modelName="GPT-5.6" modelSelection={selection("openai", "gpt-5.6")} modelChoices={[{ selection: selection("openai", "gpt-5.6"), label: "GPT-5.6" }]} modelSelectionSaving={false} timeZone="system" sendBehavior="enter" autoScroll={false} executionPanelDefaultExpanded={false} onModelSelectionChange={vi.fn(async () => null)} onConversationAccepted={vi.fn()} onConversationUpdated={vi.fn()} />);
    expect(mockedUseConversationAutoScroll).toHaveBeenCalledWith(expect.objectContaining({ enabled: false }));
    const composer = screen.getByRole("textbox", { name: "輸入訊息" });
    fireEvent.change(composer, { target: { value: "hello" } });
    fireEvent.keyDown(composer, { key: "Enter", shiftKey: true });
    fireEvent.keyDown(composer, { key: "Enter", isComposing: true });
    expect(send).not.toHaveBeenCalled();

    fireEvent.keyDown(composer, { key: "Enter" });
    expect(send).toHaveBeenCalledWith("hello");
    expect(followLatest).toHaveBeenCalledOnce();
  });

  it("uses Ctrl or Cmd Enter in modifier mode", () => {
    const send = vi.fn(async () => true);
    mockedUseConversationRun.mockReturnValue({ messages: [], activeRun: null, events: [], streamedText: "", loading: false, loadingOlderMessages: false, hasOlderMessages: false, error: null, isRunning: false, send, cancel: vi.fn(async () => undefined), loadOlderMessages: vi.fn(async () => undefined) });
    render(<ChatWorkspace conversationId={null} modelName="GPT-5.6" modelSelection={selection("openai", "gpt-5.6")} modelChoices={[{ selection: selection("openai", "gpt-5.6"), label: "GPT-5.6" }]} modelSelectionSaving={false} timeZone="system" sendBehavior="modifier-enter" autoScroll executionPanelDefaultExpanded={false} onModelSelectionChange={vi.fn(async () => null)} onConversationAccepted={vi.fn()} onConversationUpdated={vi.fn()} />);
    const composer = screen.getByRole("textbox", { name: "輸入訊息" });
    fireEvent.change(composer, { target: { value: "hello" } });
    fireEvent.keyDown(composer, { key: "Enter" });
    expect(send).not.toHaveBeenCalled();

    fireEvent.keyDown(composer, { key: "Enter", ctrlKey: true });
    expect(send).toHaveBeenCalledWith("hello");
  });
});
