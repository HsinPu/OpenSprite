import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SchedulePage } from "../src/features/schedules/SchedulePage";
import type { Schedule } from "../src/api/schedules";
import type { Workspace } from "../src/api/workspaces";


const controller = {
  schedules: [] as Schedule[], occurrences: {}, runtimeStatus: { platform: "windows", continuity: "login_only" },
  loading: false, saving: false, error: null,
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
  id: "00000000-0000-4000-8000-000000000000", kind: "unassigned", name: "Unassigned workspace",
  rootPath: null, availability: "not_applicable", unavailableReason: null, revision: 1,
  createdAt: "1970-01-01T00:00:00Z", updatedAt: "1970-01-01T00:00:00Z",
  usage: { conversationCount: 0, scheduleCount: 0, activeRunCount: 0 },
};
const directoryWorkspace: Workspace = {
  ...unassignedWorkspace,
  id: "30000000-0000-4000-8000-000000000001", kind: "directory", name: "Alpha",
  rootPath: "C:\\Projects\\Alpha", availability: "available",
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
  controller.loadOccurrences.mockClear();
  props.onOpenConversation.mockClear();
  props.onOverlayChange.mockClear();
  Object.defineProperty(window, "innerWidth", { configurable: true, value: 1440 });
});

describe("schedule page", () => {
  it("shows grouped schedule actions and loads occurrence history", () => {
    controller.schedules = [schedule];
    render(<SchedulePage {...props} workspaces={[unassignedWorkspace, directoryWorkspace]} />);

    expect(screen.queryByRole("heading", { level: 1 })).toBeNull();
    expect(screen.getByRole("heading", { name: "Morning brief" })).toBeTruthy();
    expect(screen.getByText("Alpha")).toBeTruthy();
    expect(document.querySelector(".schedule-card__workspace-warning")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "開啟對話" }));
    expect(props.onOpenConversation).toHaveBeenCalledWith("20000000-0000-4000-8000-000000000003");
    fireEvent.click(screen.getByRole("button", { name: /執行紀錄/ }));
    expect(controller.loadOccurrences).toHaveBeenCalledWith(controller.schedules[0].id);
    expect(screen.getByRole("dialog")).toBeTruthy();
  });

  it("shows an unavailable Workspace reason without disabling schedule actions", () => {
    controller.schedules = [schedule];
    const unavailable = { ...directoryWorkspace, availability: "unavailable" as const, unavailableReason: "missing" as const };
    render(<SchedulePage {...props} workspaces={[unassignedWorkspace, unavailable]} />);

    expect(screen.getByText("工作區資料夾目前無法使用：資料夾不存在。純文字排程仍可執行。")).toBeTruthy();
    expect((screen.getByRole("button", { name: /立即執行/ }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("warns when a schedule Workspace is missing from a loaded catalog", () => {
    controller.schedules = [schedule];
    render(<SchedulePage {...props} workspaces={[unassignedWorkspace]} />);

    expect(screen.getByText("這個排程所屬的工作區已不在目前目錄中。")).toBeTruthy();
    expect(screen.getByText("工作區資料不存在")).toBeTruthy();
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
