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

  it("loads all cursor pages before exposing the searchable list", async () => {
    api.listSchedules.mockResolvedValueOnce({ schedules: [{ id: "a" }], nextCursor: "older" }).mockResolvedValueOnce({ schedules: [{ id: "b" }], nextCursor: null });
    const { result } = renderHook(() => useSchedules(true));
    await act(flush);
    expect(api.listSchedules).toHaveBeenNthCalledWith(2, "older");
    expect(result.current.schedules.map((item) => item.id)).toEqual(["a", "b"]);
  });

  it("retains data and reports refresh failure without resubmitting a successful mutation", async () => {
    api.listSchedules.mockResolvedValueOnce({ schedules: [{ id: "a" }], nextCursor: null });
    const { result } = renderHook(() => useSchedules(true));
    await act(flush);
    api.deleteSchedule.mockResolvedValue(undefined);
    api.listSchedules.mockRejectedValueOnce(new Error("offline"));
    await act(async () => { await result.current.remove(result.current.schedules[0]); });
    expect(result.current.schedules).toHaveLength(1);
    expect(result.current.refreshFailed).toBe(true);
    expect(result.current.mutationRefreshFailed).toBe(true);
    expect(api.deleteSchedule).toHaveBeenCalledTimes(1);
    await act(async () => { await result.current.refresh(); });
    expect(result.current.refreshFailed).toBe(false);
    expect(result.current.mutationRefreshFailed).toBe(false);
  });

  it("separates history loading and error state from the schedule list", async () => {
    const { result } = renderHook(() => useSchedules(true));
    await act(flush);
    let reject!: (error: Error) => void;
    api.listScheduleOccurrences.mockImplementationOnce(() => new Promise((_resolve, fail) => { reject = fail; }));
    let pending!: Promise<void>;
    act(() => { pending = result.current.loadOccurrences("a"); });
    expect(result.current.historyLoading.a).toBe(true);
    await act(async () => { reject(new Error("history offline")); await pending; });
    expect(result.current.historyLoading.a).toBe(false);
    expect(result.current.historyErrors.a).toBeInstanceOf(Error);
    expect(result.current.error).toBeNull();
    api.listScheduleOccurrences.mockResolvedValueOnce({ occurrences: [], nextCursor: null });
    await act(async () => { await result.current.loadOccurrences("a"); });
    expect(result.current.historyErrors.a).toBeNull();
    expect(result.current.occurrences.a).toEqual([]);
  });

  it("rejects duplicate operations while one request is pending", async () => {
    const { result } = renderHook(() => useSchedules(true));
    await act(flush);
    let resolve!: () => void;
    api.deleteSchedule.mockImplementationOnce(() => new Promise<void>((done) => { resolve = done; }));
    const item = { id: "a" } as Parameters<typeof result.current.remove>[0];
    let first!: Promise<void>;
    act(() => { first = result.current.remove(item); });
    await expect(result.current.remove(item)).rejects.toThrow("operation_in_progress");
    expect(api.deleteSchedule).toHaveBeenCalledTimes(1);
    await act(async () => { resolve(); await first; });
  });

  it("does not replace newer refresh data with an older response", async () => {
    const { result } = renderHook(() => useSchedules(false));
    let resolve!: (value: unknown) => void;
    api.listSchedules.mockImplementationOnce(() => new Promise((done) => { resolve = done; })).mockResolvedValueOnce({ schedules: [{ id: "new" }], nextCursor: null });
    let old!: Promise<boolean>;
    act(() => { old = result.current.refresh(); });
    await act(async () => { await result.current.refresh(); });
    await act(async () => { resolve({ schedules: [{ id: "old" }], nextCursor: null }); await old; });
    expect(result.current.schedules.map((item) => item.id)).toEqual(["new"]);
  });
});
