import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useSchedules } from "../src/features/schedules/useSchedules";


const api = vi.hoisted(() => ({
  listSchedules: vi.fn(),
  getScheduleRuntimeStatus: vi.fn(),
  createSchedule: vi.fn(),
  updateSchedule: vi.fn(),
  setSchedulePaused: vi.fn(),
  runScheduleNow: vi.fn(),
  deleteSchedule: vi.fn(),
  listScheduleOccurrences: vi.fn(),
}));

vi.mock("../src/api/schedules", () => api);

const flush = async () => {
  await Promise.resolve();
  await Promise.resolve();
};

describe("schedule polling lifecycle", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    api.listSchedules.mockResolvedValue({ schedules: [], nextCursor: null });
    api.getScheduleRuntimeStatus.mockResolvedValue({ platform: "windows", continuity: "login_only" });
  });

  afterEach(() => vi.useRealTimers());

  it("polls only while the schedules settings section is active", async () => {
    const { rerender } = renderHook(
      ({ active }) => useSchedules(active),
      { initialProps: { active: false } },
    );
    expect(api.listSchedules).not.toHaveBeenCalled();

    rerender({ active: true });
    await act(flush);
    expect(api.listSchedules).toHaveBeenCalledTimes(1);

    await act(async () => {
      vi.advanceTimersByTime(5_000);
      await flush();
    });
    expect(api.listSchedules).toHaveBeenCalledTimes(2);

    rerender({ active: false });
    await act(async () => {
      vi.advanceTimersByTime(10_000);
      await flush();
    });
    expect(api.listSchedules).toHaveBeenCalledTimes(2);
  });
});
