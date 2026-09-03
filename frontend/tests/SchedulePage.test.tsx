import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SchedulePage } from "../src/features/schedules/SchedulePage";
import type { Schedule } from "../src/api/schedules";


const controller = {
  schedules: [] as Schedule[], occurrences: {}, runtimeStatus: { platform: "windows", continuity: "login_only" },
  loading: false, saving: false, error: null,
  refresh: vi.fn(), loadOccurrences: vi.fn(), create: vi.fn(), update: vi.fn(),
  pause: vi.fn(), resume: vi.fn(), runNow: vi.fn(), remove: vi.fn(),
};

vi.mock("../src/features/schedules/useSchedules", () => ({ useSchedules: () => controller }));

const props = {
  active: true,
  defaultTimeZone: "Asia/Taipei",
  modelSelection: { providerId: "openai", modelId: "gpt-5.6", contextBudget: "64k", outputBudget: "16k" } as const,
  modelChoices: [{ selection: { providerId: "openai", modelId: "gpt-5.6", contextBudget: "64k", outputBudget: "16k" } as const, label: "GPT-5.6" }],
  responseMode: "balanced" as const,
  outputContinuation: "5" as const,
  onOpenConversation: vi.fn(),
};

beforeEach(() => {
  controller.schedules = [];
  Object.defineProperty(window, "innerWidth", { configurable: true, value: 1440 });
});

describe("schedule page", () => {
  it("shows grouped schedule actions and loads occurrence history", () => {
    controller.schedules = [{
      ...props.modelSelection,
      id: "20000000-0000-4000-8000-000000000001",
      name: "Morning brief", prompt: "Summarize today.", timeZone: "Asia/Taipei",
      cadence: { type: "daily", localTime: "09:30" } as const,
      executionProfile: { ...props.modelSelection, responseMode: "balanced", outputContinuation: "5" } as const,
      status: "active" as const, conversationId: null, nextRunAt: "2026-09-04T01:30:00Z",
      revision: 1, createdAt: "2026-09-03T01:00:00Z", updatedAt: "2026-09-03T01:00:00Z",
      latestOccurrence: null,
    }];
    render(<SchedulePage {...props} />);

    expect(screen.getByRole("heading", { name: "Morning brief" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /執行紀錄/ }));
    expect(controller.loadOccurrences).toHaveBeenCalledWith(controller.schedules[0].id);
    expect(screen.getByRole("dialog")).toBeTruthy();
  });

  it.each([[1440, ".ant-modal"], [390, ".ant-drawer"]])("uses the responsive editor at %ipx", (width, selector) => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: width });
    const { baseElement } = render(<SchedulePage {...props} />);
    fireEvent.click(screen.getByRole("button", { name: /新增排程/ }));
    expect(baseElement.querySelector(selector)).toBeTruthy();
    expect(screen.getByLabelText("名稱")).toBeTruthy();
  });
});
