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
  const mounted = useRef(true);

  useEffect(() => () => { mounted.current = false; }, []);

  const refresh = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    try {
      const [page, status] = await Promise.all([listSchedules(), getScheduleRuntimeStatus()]);
      if (mounted.current) {
        setSchedules(page.schedules);
        setRuntimeStatus(status);
        setError(null);
      }
    } catch (caught) {
      if (mounted.current) setError(caught);
    } finally {
      if (mounted.current && !quiet) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!active) return;
    void refresh();
    const timer = window.setInterval(() => void refresh(true), 5_000);
    return () => window.clearInterval(timer);
  }, [active, refresh]);

  const mutate = useCallback(async <T,>(operation: () => Promise<T>) => {
    setSaving(true);
    try {
      const result = await operation();
      await refresh(true);
      return result;
    } catch (caught) {
      if (mounted.current) setError(caught);
      throw caught;
    } finally {
      if (mounted.current) setSaving(false);
    }
  }, [refresh]);

  const loadOccurrences = useCallback(async (scheduleId: string) => {
    try {
      const page = await listScheduleOccurrences(scheduleId);
      if (mounted.current) setOccurrences((current) => ({ ...current, [scheduleId]: page.occurrences }));
    } catch (caught) {
      if (mounted.current) setError(caught);
    }
  }, []);

  return {
    schedules,
    occurrences,
    runtimeStatus,
    loading,
    saving,
    error,
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
