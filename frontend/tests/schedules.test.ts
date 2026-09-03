import { describe, expect, it, vi } from "vitest";

import {
  ScheduleApiError,
  createSchedule,
  deleteSchedule,
  getScheduleRuntimeStatus,
  listScheduleOccurrences,
  listSchedules,
  runScheduleNow,
  setSchedulePaused,
  updateSchedule,
  type Schedule,
  type ScheduleFields,
} from "../src/api/schedules";


const fields: ScheduleFields = {
  name: "Morning brief",
  prompt: "Summarize today.",
  timeZone: "Asia/Taipei",
  cadence: { type: "daily", localTime: "09:30" },
  executionProfile: {
    providerId: "openai",
    modelId: "gpt-5.6",
    responseMode: "balanced",
    contextBudget: "64k",
    outputBudget: "16k",
    outputContinuation: "5",
  },
};

const schedule: Schedule = {
  ...fields,
  id: "20000000-0000-4000-8000-000000000001",
  status: "active",
  conversationId: null,
  nextRunAt: "2026-09-04T01:30:00Z",
  revision: 1,
  createdAt: "2026-09-03T01:00:00Z",
  updatedAt: "2026-09-03T01:00:00Z",
  latestOccurrence: null,
};

const occurrence = {
  id: "20000000-0000-4000-8000-000000000002",
  scheduleId: schedule.id,
  scheduledFor: "2026-09-03T02:00:00Z",
  trigger: "manual",
  status: "pending",
  runId: null,
  errorCode: null,
  missedCount: 0,
  startedAt: null,
  finishedAt: null,
  createdAt: "2026-09-03T02:00:00Z",
} as const;

describe("schedule API", () => {
  it("uses the approved CRUD and action requests", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ schedules: [schedule], nextCursor: null })))
      .mockResolvedValueOnce(new Response(JSON.stringify(schedule)))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...schedule, revision: 2 })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...schedule, status: "paused", revision: 2 })))
      .mockResolvedValueOnce(new Response(JSON.stringify(occurrence), { status: 202 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ occurrences: [occurrence], nextCursor: null })))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ platform: "windows", continuity: "login_only" })));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listSchedules()).resolves.toEqual({ schedules: [schedule], nextCursor: null });
    await createSchedule(fields);
    await updateSchedule(schedule, fields);
    await setSchedulePaused(schedule, true);
    await runScheduleNow(schedule.id);
    await listScheduleOccurrences(schedule.id);
    await deleteSchedule(schedule.id);
    await expect(getScheduleRuntimeStatus()).resolves.toEqual({ platform: "windows", continuity: "login_only" });

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/schedules?limit=100", undefined);
    expect(fetchMock).toHaveBeenNthCalledWith(4, `/api/schedules/${schedule.id}/pause`, expect.objectContaining({ method: "POST" }));
    expect(fetchMock).toHaveBeenNthCalledWith(5, `/api/schedules/${schedule.id}/run-now`, { method: "POST" });
    expect(fetchMock).toHaveBeenNthCalledWith(7, `/api/schedules/${schedule.id}`, { method: "DELETE" });
  });

  it("fails closed on malformed success and mismatched error bodies", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ schedules: [{ ...schedule, extra: true }], nextCursor: null }))));
    await expect(listSchedules()).rejects.toMatchObject({ code: "malformed_response" });

    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: "secret_error", message: "private", retryable: false } }), { status: 500 })));
    await expect(createSchedule(fields)).rejects.toEqual(new ScheduleApiError("malformed_response"));
  });
});
