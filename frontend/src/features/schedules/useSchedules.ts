import { useCallback, useEffect, useRef, useState } from "react";

import {
  createSchedule,
  deleteSchedule,
  getScheduleRuntimeStatus,
  listScheduleOccurrences,
  listSchedules,
  runScheduleNow,
  setSchedulePaused,
  updateSchedule,
  type Occurrence,
  type Schedule,
  type ScheduleFields,
  type ScheduleRuntimeStatus,
} from "../../api/schedules";

export function useSchedules(active: boolean) {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [occurrences, setOccurrences] = useState<Record<string, Occurrence[]>>({});
  const [runtimeStatus, setRuntimeStatus] = useState<ScheduleRuntimeStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [refreshFailed, setRefreshFailed] = useState(false);
  const [mutationRefreshFailed, setMutationRefreshFailed] = useState(false);
  const [historyLoading, setHistoryLoading] = useState<Record<string, boolean>>({});
  const [historyErrors, setHistoryErrors] = useState<Record<string, unknown>>({});
  const mounted = useRef(true);
  const refreshGeneration = useRef(0);
  const historyGeneration = useRef<Record<string, number>>({});
  const mutationPending = useRef(false);

  useEffect(() => { mounted.current = true; return () => { mounted.current = false; refreshGeneration.current += 1; }; }, []);

  const refresh = useCallback(async (quiet = false) => {
    const request = ++refreshGeneration.current;
    if (!quiet) setLoading(true);
    try {
      const [page, status] = await Promise.all([listSchedules(), getScheduleRuntimeStatus()]);
      const items = new Map(page.schedules.map((item) => [item.id, item]));
      const cursors = new Set<string>();
      let cursor = page.nextCursor;
      while (cursor) {
        if (!mounted.current || request !== refreshGeneration.current) return false;
        if (cursors.has(cursor)) throw new Error("invalid_pagination");
        cursors.add(cursor);
        const next = await listSchedules(cursor);
        for (const item of next.schedules) if (!items.has(item.id)) items.set(item.id, item);
        cursor = next.nextCursor;
      }
      if (!mounted.current || request !== refreshGeneration.current) return false;
      setSchedules([...items.values()]);
      setRuntimeStatus(status);
      setError(null);
      setRefreshFailed(false);
      setMutationRefreshFailed(false);
      return true;
    } catch (caught) {
      if (mounted.current && request === refreshGeneration.current) { setError(caught); setRefreshFailed(true); }
      return false;
    } finally {
      if (mounted.current && request === refreshGeneration.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!active) return;
    void refresh();
    const timer = window.setInterval(() => { if (!mutationPending.current) void refresh(true); }, 5_000);
    return () => window.clearInterval(timer);
  }, [active, refresh]);

  const mutate = useCallback(async <T,>(operation: () => Promise<T>) => {
    if (mutationPending.current) throw new Error("operation_in_progress");
    mutationPending.current = true;
    refreshGeneration.current += 1;
    setSaving(true);
    try {
      const result = await operation();
      const refreshed = await refresh(true);
      if (mounted.current) setMutationRefreshFailed(!refreshed);
      return result;
    } catch (caught) {
      if (mounted.current) setError(caught);
      throw caught;
    } finally {
      mutationPending.current = false;
      if (mounted.current) setSaving(false);
    }
  }, [refresh]);

  const loadOccurrences = useCallback(async (scheduleId: string) => {
    const request = (historyGeneration.current[scheduleId] ?? 0) + 1;
    historyGeneration.current[scheduleId] = request;
    setHistoryLoading((current) => ({ ...current, [scheduleId]: true }));
    setHistoryErrors((current) => ({ ...current, [scheduleId]: null }));
    try {
      const page = await listScheduleOccurrences(scheduleId);
      if (mounted.current && historyGeneration.current[scheduleId] === request) setOccurrences((current) => ({ ...current, [scheduleId]: page.occurrences }));
    } catch (caught) {
      if (mounted.current && historyGeneration.current[scheduleId] === request) setHistoryErrors((current) => ({ ...current, [scheduleId]: caught }));
    } finally {
      if (mounted.current && historyGeneration.current[scheduleId] === request) setHistoryLoading((current) => ({ ...current, [scheduleId]: false }));
    }
  }, []);

  return {
    schedules,
    occurrences,
    runtimeStatus,
    loading,
    saving,
    error,
    refreshFailed,
    mutationRefreshFailed,
    historyLoading,
    historyErrors,
    refresh,
    loadOccurrences,
    create: (fields: ScheduleFields) => mutate(() => createSchedule(fields)),
    update: (schedule: Schedule, fields: ScheduleFields) => mutate(() => updateSchedule(schedule, fields)),
    pause: (schedule: Schedule) => mutate(() => setSchedulePaused(schedule, true)),
    resume: (schedule: Schedule) => mutate(() => setSchedulePaused(schedule, false)),
    runNow: (schedule: Schedule) => mutate(() => runScheduleNow(schedule.id)),
    remove: (schedule: Schedule) => mutate(() => deleteSchedule(schedule.id)),
  };
}
