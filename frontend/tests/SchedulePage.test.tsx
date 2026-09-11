import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SchedulePage } from "../src/features/schedules/SchedulePage";
import type { Schedule } from "../src/api/schedules";
import type { Workspace } from "../src/api/workspaces";
import { createTranslator } from "../src/i18n/catalog";


const controller = {
  schedules: [] as Schedule[], occurrences: {}, runtimeStatus: { platform: "windows", continuity: "login_only" },
  loading: false, saving: false, error: null, refreshFailed: false, mutationRefreshFailed: false, historyLoading: {} as Record<string, boolean>, historyErrors: {} as Record<string, unknown>,
  refresh: vi.fn(), loadOccurrences: vi.fn(), create: vi.fn(), update: vi.fn(),
  pause: vi.fn(), resume: vi.fn(), runNow: vi.fn(), remove: vi.fn(),
};

vi.mock("../src/features/schedules/useSchedules", () => ({ useSchedules: () => controller }));

const props = {
  active: true,
  container: null,
  defaultTimeZone: "Asia/Taipei",
  modelSelection: { providerId: "openai", modelId: "gpt-5.6", contextBudget: "64k", outputBudget: "16k" } as const,
  modelChoices: [{ selection: { providerId: "openai", modelId: "gpt-5.6", contextBudget: "64k", outputBudget: "16k" } as const, label: "GPT-5.6" }],
  responseMode: "balanced" as const,
  outputContinuation: "5" as const,
  onOpenConversation: vi.fn(),
  onOverlayChange: vi.fn(),
};

const unassignedWorkspace: Workspace = {
  id: "00000000-0000-4000-8000-000000000000", kind: "default", name: "Default workspace", directoryName: "default",
  rootPath: "C:\\Users\\Test\\OpenSprite\\workspace\\default", mounts: [], availability: "available", unavailableReason: null, revision: 1,
  createdAt: "1970-01-01T00:00:00Z", updatedAt: "1970-01-01T00:00:00Z",
  usage: { conversationCount: 0, scheduleCount: 0, activeRunCount: 0 },
};
const directoryWorkspace: Workspace = {
  ...unassignedWorkspace,
  id: "30000000-0000-4000-8000-000000000001", kind: "managed", name: "Alpha", directoryName: "Alpha",
  rootPath: "C:\\Users\\Test\\OpenSprite\\workspace\\Alpha", availability: "available",
};
const schedule: Schedule = {
  id: "20000000-0000-4000-8000-000000000001",
  workspaceId: directoryWorkspace.id,
  name: "Morning brief", prompt: "Summarize today.", timeZone: "Asia/Taipei",
  cadence: { type: "daily", localTime: "09:30" },
  executionProfile: { ...props.modelSelection, responseMode: "balanced", outputContinuation: "5" },
  status: "active", conversationId: "20000000-0000-4000-8000-000000000003", nextRunAt: "2026-09-04T01:30:00Z",
  revision: 1, createdAt: "2026-09-03T01:00:00Z", updatedAt: "2026-09-03T01:00:00Z",
  latestOccurrence: null,
};

beforeEach(() => {
  controller.schedules = [];
  controller.loading = false; controller.saving = false; controller.refreshFailed = false;
  controller.historyLoading = {}; controller.historyErrors = {};
  controller.create.mockReset().mockResolvedValue(schedule);
  controller.update.mockReset().mockResolvedValue(schedule);
  controller.loadOccurrences.mockClear();
  props.onOpenConversation.mockClear();
  props.onOverlayChange.mockClear();
  Object.defineProperty(window, "innerWidth", { configurable: true, value: 1440 });
});

describe("schedule page", () => {
  it("searches beyond the visible page and combines workspace and status filters", () => {
    controller.schedules = Array.from({ length: 25 }, (_, index) => ({ ...schedule, id: `s-${index}`, name: index === 24 ? "Café 任務" : `task-${index}`, status: index === 24 ? "paused" : "active" }));
    render(<SchedulePage {...props} workspaces={[unassignedWorkspace, directoryWorkspace]} />);
    expect(screen.queryByRole("heading", { name: "Café 任務" })).toBeNull();
    fireEvent.change(screen.getByRole("textbox", { name: "搜尋排程名稱" }), { target: { value: "CAFE\u0301" } });
    expect(screen.getByRole("heading", { name: "Café 任務" })).toBeTruthy();
    expect(screen.getByText("符合 1 個／共 25 個")).toBeTruthy();
    expect(screen.getByText(/已暫停自動執行/)).toBeTruthy();
    fireEvent.mouseDown(screen.getByRole("combobox", { name: "篩選狀態" }));
    fireEvent.click(screen.getByText("啟用", { selector: ".ant-select-item-option-content" }));
    expect(screen.getByText("找不到符合條件的排程。")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "清除搜尋" }));
    expect(screen.getByText("符合 24 個／共 25 個")).toBeTruthy();
    fireEvent.mouseDown(screen.getByRole("combobox", { name: "篩選工作區" }));
    fireEvent.click(screen.getByText("預設工作區", { selector: ".ant-select-item-option-content" }));
    expect(screen.getByText("符合 0 個／共 25 個")).toBeTruthy();
  });

  it("does not show an enable switch for a completed schedule", () => {
    controller.schedules = [{ ...schedule, status: "completed", cadence: { type: "once", runAt: "2026-09-04T01:30:00Z" }, timeZone: "UTC" }];
    render(<SchedulePage {...props} />);
    expect(screen.queryByRole("switch")).toBeNull();
    expect(screen.getByText(/UTC/)).toBeTruthy();
    expect(screen.getByText("下次執行及紀錄時間顯示時區：Asia/Taipei")).toBeTruthy();
  });

  it("preserves execution settings when saving without expanding advanced fields", async () => {
    controller.schedules = [schedule];
    render(<SchedulePage {...props} workspaces={[directoryWorkspace]} />);
    fireEvent.click(screen.getByRole("button", { name: "編輯 Morning brief" }));
    expect(screen.getByText("進階設定").closest("details")?.open).toBe(false);
    fireEvent.change(screen.getByLabelText("名稱"), { target: { value: "Renamed" } });
    fireEvent.click(screen.getByRole("button", { name: /儲存排程/ }));
    await waitFor(() => expect(controller.update).toHaveBeenCalledWith(schedule, expect.objectContaining({ name: "Renamed", cadence: schedule.cadence, executionProfile: schedule.executionProfile })));
  });

  it("shows a retryable history error instead of an empty history", () => {
    controller.schedules = [schedule]; controller.historyErrors[schedule.id] = new Error("offline");
    render(<SchedulePage {...props} />);
    fireEvent.click(screen.getByRole("button", { name: "更多操作 Morning brief" }));
    fireEvent.click(screen.getByRole("menuitem", { name: /執行紀錄/ }));
    expect(screen.getByText("無法載入執行紀錄，請重試。")).toBeTruthy();
    expect(screen.queryByText(createTranslator("zh-TW")("schedules.noHistory"))).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /重\s*試/ }));
    expect(controller.loadOccurrences).toHaveBeenCalledTimes(2);
  });

  it.each(["zh-TW", "en", "ja"] as const)("provides schedule layout copy in %s", (locale) => {
    const t = createTranslator(locale);
    for (const key of ["schedules.search", "schedules.clearSearch", "schedules.results", "schedules.displayZone", "schedules.savedRefreshFailed", "schedules.section.task", "schedules.section.time", "schedules.section.execution", "schedules.historyError"] as const) expect(t(key, { count: 1, total: 2, zone: "UTC" })).not.toBe(key);
  });
  it("shows compact schedule actions and loads occurrence history", () => {
    controller.schedules = [schedule];
    render(<SchedulePage {...props} workspaces={[unassignedWorkspace, directoryWorkspace]} />);

    expect(screen.queryByRole("heading", { level: 1 })).toBeNull();
    expect(screen.getByRole("heading", { name: "Morning brief" })).toBeTruthy();
    expect(screen.getByText("Alpha")).toBeTruthy();
    expect(document.querySelector(".schedule-card__workspace-warning")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "更多操作 Morning brief" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "開啟對話" }));
    expect(props.onOpenConversation).toHaveBeenCalledWith("20000000-0000-4000-8000-000000000003");
    fireEvent.click(screen.getByRole("button", { name: "更多操作 Morning brief" }));
    fireEvent.click(screen.getByRole("menuitem", { name: /執行紀錄/ }));
    expect(controller.loadOccurrences).toHaveBeenCalledWith(controller.schedules[0].id);
    expect(screen.getByRole("dialog")).toBeTruthy();
  });

  it("shows an unavailable Workspace reason without disabling schedule actions", () => {
    controller.schedules = [schedule];
    const unavailable = { ...directoryWorkspace, availability: "unavailable" as const, unavailableReason: "missing" as const };
    render(<SchedulePage {...props} workspaces={[unassignedWorkspace, unavailable]} />);

    expect(screen.getByText("工作區資料夾目前無法使用：資料夾不存在。純文字排程仍可執行。")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "更多操作 Morning brief" }));
    expect(screen.getByRole("menuitem", { name: /立即執行/ }).getAttribute("aria-disabled")).not.toBe("true");
  });

  it("warns when a schedule Workspace is missing from a loaded catalog", () => {
    controller.schedules = [schedule];
    render(<SchedulePage {...props} workspaces={[unassignedWorkspace]} />);

    expect(screen.getByText("這個排程所屬的工作區已不在目前目錄中。")).toBeTruthy();
    expect(screen.getByText("工作區資料不存在")).toBeTruthy();
  });

  it("shows a retryable Workspace catalog error and blocks create or edit", () => {
    controller.schedules = [schedule];
    const retry = vi.fn();
    render(<SchedulePage {...props} workspaceError onWorkspaceRetry={retry} />);

    expect(screen.getByRole("alert").textContent).toContain("無法載入工作區，請重試。");
    expect((screen.getByRole("button", { name: /新增排程/ }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: /編輯/ }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: /重.*試/ }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it.each([[1440, ".ant-modal"], [390, ".ant-drawer"]])("uses the responsive editor at %ipx", (width, selector) => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: width });
    const container = document.createElement("div");
    document.body.append(container);
    const { unmount } = render(<SchedulePage {...props} container={container} />);
    fireEvent.click(screen.getByRole("button", { name: /新增排程/ }));
    expect(container.querySelector(selector)).toBeTruthy();
    expect(screen.getByLabelText("名稱")).toBeTruthy();
    expect(screen.getByRole("combobox", { name: "工作區" })).toBeTruthy();
    expect(props.onOverlayChange).toHaveBeenLastCalledWith(true);
    unmount();
    container.remove();
  });
});
