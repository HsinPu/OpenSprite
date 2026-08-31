import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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
  completionReason: null,
  error: null,
  partialText: "正在整理",
  createdAt: "2026-08-22T08:00:00Z",
  startedAt: "2026-08-22T08:00:01Z",
  finishedAt: null,
};

const events: RunEvent[] = [
  { sequence: 1, type: "run.started", runId: run.id, conversationId: run.conversationId, createdAt: "2026-08-22T08:00:01Z", data: {} },
  { sequence: 2, type: "model.started", runId: run.id, conversationId: run.conversationId, createdAt: "2026-08-22T08:00:02Z", data: { providerId: run.providerId, modelId: run.modelId, responseMode: run.responseMode, maxOutputTokens: 32_768 } },
  { sequence: 3, type: "assistant.delta", runId: run.id, conversationId: run.conversationId, createdAt: "2026-08-22T08:00:03Z", data: { text: "正在整理" } },
];

const contextEvents: RunEvent[] = events.map((event) => event.type === "model.started"
  ? { ...event, data: { ...event.data, contextTokens: 4_096, contextLimitTokens: 262_144, inputBudgetTokens: 196_608 } }
  : event);

const compactionStartedEvent: RunEvent = {
  sequence: 2,
  type: "context.compaction.started",
  runId: run.id,
  conversationId: run.conversationId,
  createdAt: "2026-08-22T08:00:02Z",
  data: {},
};

const mockedUseConversationRun = vi.mocked(useConversationRun);
const mockedUseRunInspection = vi.mocked(useRunInspection);
const mockedUseConversationAutoScroll = vi.mocked(useConversationAutoScroll);
const selection = (providerId: ModelSelection["providerId"], modelId: string): ModelSelection => ({ providerId, modelId, contextBudget: "auto", outputBudget: "auto" });
const inspectRun = vi.fn(async () => undefined);
const returnToLatest = vi.fn();
const followLatest = vi.fn();
const preservePositionWhilePrepending = vi.fn(async (load: () => Promise<void>) => load());

function createMobileHeaderActionTarget(): HTMLDivElement {
  const target = document.createElement("div");
  target.dataset.testMobileHeaderActionTarget = "true";
  document.body.append(target);
  return target;
}

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

afterEach(() => {
  document.querySelectorAll("[data-test-mobile-header-action-target]").forEach((target) => target.remove());
});

describe("live chat workspace", () => {
  it("shows the latest Context usage beside the model picker", () => {
    mockedUseConversationRun.mockReturnValue({
      messages: [],
      activeRun: run,
      events: contextEvents,
      streamedText: "正在整理",
      loading: false,
      loadingOlderMessages: false,
      hasOlderMessages: false,
      error: null,
      isRunning: true,
      send: vi.fn(async () => true),
      cancel: vi.fn(async () => undefined),
      loadOlderMessages: vi.fn(async () => undefined),
    });

    render(<ChatWorkspace conversationId={run.conversationId} modelName="GPT-5.6" modelSelection={selection("openrouter", run.modelId)} modelChoices={[{ selection: selection("openrouter", run.modelId), label: "GPT-5.6", contextWindowTokens: 262_144, maxOutputTokens: 32_768 }]} modelSelectionSaving={false} timeZone="system" sendBehavior="enter" autoScroll executionPanelDefaultExpanded={false} onModelSelectionChange={vi.fn(async () => null)} onConversationAccepted={vi.fn()} onConversationUpdated={vi.fn()} />);

    const indicator = screen.getByTestId("context-usage");
    const modelPicker = screen.getByRole("combobox", { name: /目前模型 GPT-5.6/ });
    expect(indicator.textContent).toContain("Context 4K / 256K");
    expect(indicator.compareDocumentPosition(modelPicker) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("renders persisted assistant Markdown while keeping user messages as plain text", () => {
    mockedUseConversationRun.mockReturnValue({
      messages: [
        { id: run.userMessageId, runId: run.id, role: "user", content: "**使用者原文**", createdAt: run.createdAt, delivery: "persisted" },
        { id: "44444444-4444-4444-8444-444444444444", runId: run.id, role: "assistant", content: "**助理粗體**", createdAt: "2026-08-22T08:00:07Z", delivery: "persisted" },
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

    render(<ChatWorkspace conversationId={run.conversationId} modelName="GPT-5.6" modelSelection={selection("openrouter", run.modelId)} modelChoices={[{ selection: selection("openrouter", run.modelId), label: "GPT-5.6" }]} modelSelectionSaving={false} timeZone="system" sendBehavior="enter" autoScroll executionPanelDefaultExpanded={false} onModelSelectionChange={vi.fn(async () => null)} onConversationAccepted={vi.fn()} onConversationUpdated={vi.fn()} />);

    expect(screen.getByText("**使用者原文**").tagName).toBe("P");
    expect(screen.getByText("助理粗體").tagName).toBe("STRONG");
  });

  it("renders streamed assistant text as Markdown", () => {
    mockedUseConversationRun.mockReturnValue({
      messages: [{ id: run.userMessageId, runId: run.id, role: "user", content: "你好", createdAt: run.createdAt, delivery: "persisted" }],
      activeRun: run,
      events,
      streamedText: "**串流粗體**",
      loading: false,
      loadingOlderMessages: false,
      hasOlderMessages: false,
      error: null,
      isRunning: true,
      send: vi.fn(async () => true),
      cancel: vi.fn(async () => undefined),
      loadOlderMessages: vi.fn(async () => undefined),
    });

    render(<ChatWorkspace conversationId={run.conversationId} modelName="GPT-5.6" modelSelection={selection("openrouter", run.modelId)} modelChoices={[{ selection: selection("openrouter", run.modelId), label: "GPT-5.6" }]} modelSelectionSaving={false} timeZone="system" sendBehavior="enter" autoScroll executionPanelDefaultExpanded={false} onModelSelectionChange={vi.fn(async () => null)} onConversationAccepted={vi.fn()} onConversationUpdated={vi.fn()} />);

    expect(screen.getByText("串流粗體").tagName).toBe("STRONG");
  });

  it("shows an output-limit notice beneath the persisted Markdown response", () => {
    const assistantId = "44444444-4444-4444-8444-444444444444";
    mockedUseConversationRun.mockReturnValue({
      messages: [
        { id: run.userMessageId, runId: run.id, role: "user", content: "建立完整頁面", createdAt: run.createdAt, delivery: "persisted" },
        { id: assistantId, runId: run.id, role: "assistant", content: "部分 **Markdown** 回覆", createdAt: "2026-08-22T08:00:07Z", delivery: "persisted" },
      ],
      activeRun: {
        ...run,
        status: "completed",
        assistantMessageId: assistantId,
        completionReason: "output_limit",
        partialText: "部分 **Markdown** 回覆",
        finishedAt: "2026-08-22T08:00:07Z",
      },
      events: [{ sequence: 4, type: "run.completed", runId: run.id, conversationId: run.conversationId, createdAt: "2026-08-22T08:00:07Z", data: { assistantMessageId: assistantId, completionReason: "output_limit" } }],
      streamedText: "部分 **Markdown** 回覆",
      loading: false,
      loadingOlderMessages: false,
      hasOlderMessages: false,
      error: null,
      isRunning: false,
      send: vi.fn(async () => true),
      cancel: vi.fn(async () => undefined),
      loadOlderMessages: vi.fn(async () => undefined),
    });

    render(<ChatWorkspace conversationId={run.conversationId} modelName="Auto Router" modelSelection={selection("openrouter", run.modelId)} modelChoices={[{ selection: selection("openrouter", run.modelId), label: "Auto Router" }]} modelSelectionSaving={false} timeZone="system" sendBehavior="enter" autoScroll executionPanelDefaultExpanded onModelSelectionChange={vi.fn(async () => null)} onConversationAccepted={vi.fn()} onConversationUpdated={vi.fn()} />);

    expect(screen.getByText("Markdown").tagName).toBe("STRONG");
    expect(screen.getByText("回覆已達輸出長度上限，內容可能不完整。")).toBeTruthy();
    expect(screen.queryByText("模型廠家的回應無法安全使用。")).toBeNull();
    expect(screen.getAllByText("已達輸出上限").length).toBeGreaterThan(0);
  });

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
    const failedRun: RunSnapshot = { ...run, status: "failed", assistantMessageId: null, completionReason: null, finishedAt: "2026-08-22T08:00:04Z", error: { code: "provider_unreachable", message: "safe", retryable: true } };
    mockedUseConversationRun.mockReturnValue({ messages: [{ id: run.userMessageId, runId: run.id, role: "user", content: "你好", createdAt: run.createdAt, delivery: "persisted" }], activeRun: failedRun, events: [], streamedText: "", loading: false, loadingOlderMessages: false, hasOlderMessages: false, error: null, isRunning: false, send: vi.fn(async () => true), cancel: vi.fn(async () => undefined), loadOlderMessages: vi.fn(async () => undefined) });
    render(<ChatWorkspace conversationId={run.conversationId} modelName="GPT-5.6" modelSelection={selection("openrouter", run.modelId)} modelChoices={[{ selection: selection("openrouter", run.modelId), label: "GPT-5.6" }]} modelSelectionSaving={false} timeZone="system" sendBehavior="enter" autoScroll executionPanelDefaultExpanded={false} onModelSelectionChange={vi.fn(async () => null)} onConversationAccepted={vi.fn()} onConversationUpdated={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "查看這次執行" }));
    expect(inspectRun).toHaveBeenCalledWith(run.id);
  });

  it("shows Context compaction as a temporary reply status", () => {
    const activeRun = { ...run, partialText: "" };
    const state = (runEvents: RunEvent[]) => ({
      messages: [{ id: run.userMessageId, runId: run.id, role: "user" as const, content: "你好", createdAt: run.createdAt, delivery: "persisted" as const }],
      activeRun,
      events: runEvents,
      streamedText: "",
      loading: false,
      loadingOlderMessages: false,
      hasOlderMessages: false,
      error: null,
      isRunning: true,
      send: vi.fn(async () => true),
      cancel: vi.fn(async () => undefined),
      loadOlderMessages: vi.fn(async () => undefined),
    });
    mockedUseConversationRun.mockReturnValue(state([events[0]!, compactionStartedEvent]));
    const workspace = () => <ChatWorkspace conversationId={run.conversationId} modelName="GPT-5.6" modelSelection={selection("openrouter", run.modelId)} modelChoices={[{ selection: selection("openrouter", run.modelId), label: "GPT-5.6" }]} modelSelectionSaving={false} timeZone="system" sendBehavior="enter" autoScroll executionPanelDefaultExpanded={false} onModelSelectionChange={vi.fn(async () => null)} onConversationAccepted={vi.fn()} onConversationUpdated={vi.fn()} />;
    const { rerender } = render(workspace());

    expect(screen.getByText("正在整理較早的對話內容…")).toBeTruthy();
    expect(screen.queryByText("正在準備回覆…")).toBeNull();

    mockedUseConversationRun.mockReturnValue(state([events[0]!, compactionStartedEvent, events[1]!]));
    rerender(workspace());
    expect(screen.getByText("正在準備回覆…")).toBeTruthy();
    expect(screen.queryByText("正在整理較早的對話內容…")).toBeNull();
  });

  it("opens the mobile execution drawer from the global header and restores focus on close", async () => {
    mockedUseConversationRun.mockReturnValue({
      messages: [],
      activeRun: run,
      events,
      streamedText: "正在整理",
      loading: false,
      loadingOlderMessages: false,
      hasOlderMessages: false,
      error: null,
      isRunning: true,
      send: vi.fn(async () => true),
      cancel: vi.fn(async () => undefined),
      loadOlderMessages: vi.fn(async () => undefined),
    });

    const mobileHeaderActionTarget = createMobileHeaderActionTarget();
    render(<ChatWorkspace conversationId={run.conversationId} modelName="GPT-5.6" modelSelection={selection("openrouter", run.modelId)} modelChoices={[{ selection: selection("openrouter", run.modelId), label: "GPT-5.6" }]} modelSelectionSaving={false} timeZone="system" sendBehavior="enter" autoScroll executionPanelDefaultExpanded={true} mobileHeaderActionTarget={mobileHeaderActionTarget} onModelSelectionChange={vi.fn(async () => null)} onConversationAccepted={vi.fn()} onConversationUpdated={vi.fn()} title="整理今天的工作" />);

    const trigger = screen.getByRole("button", { name: "開啟本次執行" });
    expect(trigger.className).toContain("mobile-execution-button");
    expect(mobileHeaderActionTarget.contains(trigger)).toBe(true);
    expect(trigger.textContent).toBe("");
    expect(trigger.querySelector(".anticon-left")).toBeTruthy();
    expect(trigger.getAttribute("aria-expanded")).toBe("false");

    fireEvent.click(trigger);
    const drawer = await screen.findByRole("dialog");
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    expect(within(drawer).getByText("本次執行")).toBeTruthy();
    expect(within(drawer).getByText("openrouter · openai/gpt-5.6 · 廠商預設")).toBeTruthy();
    expect(within(drawer).queryByRole("button", { name: "收合本次執行" })).toBeNull();

    fireEvent.keyDown(drawer, { key: "Escape" });
    await waitFor(() => expect(document.activeElement).toBe(trigger));
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
  });

  it("places both desktop shell toggles around the chat title", () => {
    mockedUseConversationRun.mockReturnValue({
      messages: [],
      activeRun: run,
      events,
      streamedText: "正在整理",
      loading: false,
      loadingOlderMessages: false,
      hasOlderMessages: false,
      error: null,
      isRunning: true,
      send: vi.fn(async () => true),
      cancel: vi.fn(async () => undefined),
      loadOlderMessages: vi.fn(async () => undefined),
    });

    const onNavigationToggle = vi.fn();
    render(<ChatWorkspace conversationId={run.conversationId} modelName="GPT-5.6" modelSelection={selection("openrouter", run.modelId)} modelChoices={[{ selection: selection("openrouter", run.modelId), label: "GPT-5.6" }]} modelSelectionSaving={false} timeZone="system" sendBehavior="enter" autoScroll executionPanelDefaultExpanded={false} navigationCollapsed={false} onNavigationToggle={onNavigationToggle} onModelSelectionChange={vi.fn(async () => null)} onConversationAccepted={vi.fn()} onConversationUpdated={vi.fn()} title="整理今天的工作" />);

    const header = screen.getByRole("heading", { level: 1, name: "整理今天的工作" }).closest("header")!;
    const navigation = screen.getByRole("button", { name: "收合側邊欄" });
    const expand = screen.getByRole("button", { name: "展開本次執行" });
    expect(header.firstElementChild).toBe(navigation);
    expect(header.lastElementChild).toBe(expand);
    fireEvent.click(navigation);
    expect(onNavigationToggle).toHaveBeenCalledOnce();
    expect(expand.className).toContain("chat-workspace__header-context-toggle");
    expect(expand.closest("header")).toBeTruthy();
    const body = document.getElementById(expand.getAttribute("aria-controls")!);
    expect(body?.hidden).toBe(true);

    fireEvent.click(expand);
    const collapse = screen.getByRole("button", { name: "收合本次執行" });
    expect(collapse.getAttribute("aria-expanded")).toBe("true");
    expect(body?.hidden).toBe(false);
  });

  it("opens the mobile drawer when inspecting a historical execution", async () => {
    const matchMedia = vi.fn((query: string) => ({
      matches: query === "(max-width: 900px)",
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(() => false),
    }));
    vi.stubGlobal("matchMedia", matchMedia);
    mockedUseConversationRun.mockReturnValue({
      messages: [{ id: run.userMessageId, runId: run.id, role: "user", content: "你好", createdAt: run.createdAt, delivery: "persisted" }],
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
    render(<ChatWorkspace conversationId={run.conversationId} modelName="GPT-5.6" modelSelection={selection("openrouter", run.modelId)} modelChoices={[{ selection: selection("openrouter", run.modelId), label: "GPT-5.6" }]} modelSelectionSaving={false} timeZone="system" sendBehavior="enter" autoScroll executionPanelDefaultExpanded={true} onModelSelectionChange={vi.fn(async () => null)} onConversationAccepted={vi.fn()} onConversationUpdated={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "查看這次執行" }));
    expect(inspectRun).toHaveBeenCalledWith(run.id);
    expect(await screen.findByRole("dialog")).toBeTruthy();
    vi.unstubAllGlobals();
  });

  it("shows the selected historical Run and returns to the latest execution", () => {
    const historicalRun: RunSnapshot = { ...run, status: "completed", assistantMessageId: "44444444-4444-4444-8444-444444444444", modelId: "historic/model", partialText: "歷史完成", completionReason: "stop", finishedAt: "2026-08-22T08:00:07Z" };
    mockedUseRunInspection.mockReturnValue({ selectedRunId: run.id, run: historicalRun, events, loading: false, error: null, inspectRun, retry: vi.fn(async () => undefined), returnToLatest });
    mockedUseConversationRun.mockReturnValue({ messages: [{ id: run.userMessageId, runId: run.id, role: "user", content: "你好", createdAt: run.createdAt, delivery: "persisted" }, { id: historicalRun.assistantMessageId!, runId: run.id, role: "assistant", content: "歷史完成", createdAt: historicalRun.finishedAt!, delivery: "persisted" }], activeRun: run, events: [], streamedText: "正在整理", loading: false, loadingOlderMessages: false, hasOlderMessages: false, error: null, isRunning: true, send: vi.fn(async () => true), cancel: vi.fn(async () => undefined), loadOlderMessages: vi.fn(async () => undefined) });
    render(<ChatWorkspace conversationId={run.conversationId} modelName="目前模型" modelSelection={selection("openrouter", run.modelId)} modelChoices={[{ selection: selection("openrouter", run.modelId), label: "目前模型" }, { selection: selection("openrouter", historicalRun.modelId), label: "歷史模型" }]} modelSelectionSaving={false} timeZone="system" sendBehavior="enter" autoScroll executionPanelDefaultExpanded={false} onModelSelectionChange={vi.fn(async () => null)} onConversationAccepted={vi.fn()} onConversationUpdated={vi.fn()} />);

    expect(screen.getByRole("button", { name: "正在查看這次執行" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("heading", { level: 2, name: "執行詳情" })).toBeTruthy();
    expect(within(screen.getByRole("complementary", { name: "執行詳情" })).getAllByText("歷史模型").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "回到最新執行" }));
    expect(returnToLatest).toHaveBeenCalledOnce();
  });

  it("allows historical execution details to be collapsed after opening", () => {
    const historicalRun: RunSnapshot = { ...run, status: "completed", assistantMessageId: "44444444-4444-4444-8444-444444444444", modelId: "historic/model", partialText: "歷史完成", completionReason: "stop", finishedAt: "2026-08-22T08:00:07Z" };
    mockedUseRunInspection.mockReturnValue({ selectedRunId: run.id, run: historicalRun, events, loading: false, error: null, inspectRun, retry: vi.fn(async () => undefined), returnToLatest });
    mockedUseConversationRun.mockReturnValue({ messages: [{ id: run.userMessageId, runId: run.id, role: "user", content: "你好", createdAt: run.createdAt, delivery: "persisted" }, { id: historicalRun.assistantMessageId!, runId: run.id, role: "assistant", content: "歷史完成", createdAt: historicalRun.finishedAt!, delivery: "persisted" }], activeRun: run, events: [], streamedText: "正在整理", loading: false, loadingOlderMessages: false, hasOlderMessages: false, error: null, isRunning: true, send: vi.fn(async () => true), cancel: vi.fn(async () => undefined), loadOlderMessages: vi.fn(async () => undefined) });
    render(<ChatWorkspace conversationId={run.conversationId} modelName="目前模型" modelSelection={selection("openrouter", run.modelId)} modelChoices={[{ selection: selection("openrouter", run.modelId), label: "目前模型" }, { selection: selection("openrouter", historicalRun.modelId), label: "歷史模型" }]} modelSelectionSaving={false} timeZone="system" sendBehavior="enter" autoScroll executionPanelDefaultExpanded={false} onModelSelectionChange={vi.fn(async () => null)} onConversationAccepted={vi.fn()} onConversationUpdated={vi.fn()} />);

    const collapse = screen.getByRole("button", { name: "收合執行詳情" });
    const body = document.getElementById(collapse.getAttribute("aria-controls")!);
    expect(body?.hidden).toBe(false);

    fireEvent.click(collapse);

    const expand = screen.getByRole("button", { name: "展開執行詳情" });
    expect(expand.getAttribute("aria-expanded")).toBe("false");
    expect(body?.hidden).toBe(true);
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
