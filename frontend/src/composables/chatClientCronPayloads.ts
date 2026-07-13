import { coerceBoolean, coerceNonNegativeInteger, coerceText as textField } from "./chatClientCoercion";
import { toPayloadSource } from "./payloadBoundary";
import { normalizeCronJobMode } from "./scheduleDefaults";
import type { CronJobView } from "./useSettingsState";

type CronJobsSourcePayload = { jobs?: unknown };

type CronJobScheduleSourcePayload = {
  kind?: unknown;
  display?: unknown;
  every_ms?: unknown;
  expr?: unknown;
  at_ms?: unknown;
  tz?: unknown;
};

type CronJobMessageSourcePayload = {
  message?: unknown;
  deliver?: unknown;
};

type CronJobStateSourcePayload = {
  next_run_display?: unknown;
  nextRunDisplay?: unknown;
};

type CronJobSourcePayload = {
  id?: unknown;
  name?: unknown;
  enabled?: unknown;
  schedule?: unknown;
  payload?: unknown;
  every_seconds?: unknown;
  cron_expr?: unknown;
  session_id?: unknown;
  sessionId?: unknown;
  state?: unknown;
  message?: unknown;
};

export type CronJobsPayload = {
  jobs: CronJobView[];
};

function normalizeCronJobSchedule(value: unknown): CronJobView["schedule"] {
  const schedule = toPayloadSource<CronJobScheduleSourcePayload>(value) || {};
  const atMs = Number(schedule.at_ms);
  return {
    kind: normalizeCronJobMode(schedule.kind),
    display: textField(schedule.display),
    every_ms: coerceNonNegativeInteger(schedule.every_ms),
    expr: textField(schedule.expr),
    at_ms: Number.isFinite(atMs) && atMs > 0 ? atMs : textField(schedule.at_ms),
    tz: textField(schedule.tz),
  };
}

function normalizeCronJobMessage(value: unknown): CronJobView["payload"] {
  const payload = toPayloadSource<CronJobMessageSourcePayload>(value) || {};
  return {
    message: textField(payload.message),
    deliver: payload.deliver !== false,
  };
}

function normalizeCronJobState(value: unknown): CronJobView["state"] {
  const state = toPayloadSource<CronJobStateSourcePayload>(value) || {};
  return {
    next_run_display: textField(state.next_run_display || state.nextRunDisplay),
  };
}

function normalizeCronJob(value: unknown): CronJobView | null {
  const job = toPayloadSource<CronJobSourcePayload>(value);
  if (!job) {
    return null;
  }
  const schedule = normalizeCronJobSchedule(job.schedule);
  const payload = normalizeCronJobMessage(job.payload);
  const everySeconds = coerceNonNegativeInteger(job.every_seconds || (schedule.every_ms ? schedule.every_ms / 1000 : 0));
  return {
    id: textField(job.id),
    name: textField(job.name),
    enabled: coerceBoolean(job.enabled),
    schedule,
    cron_expr: textField(job.cron_expr || schedule.expr),
    every_seconds: everySeconds,
    session_id: textField(job.session_id || job.sessionId),
    state: normalizeCronJobState(job.state),
    payload,
    message: textField(job.message || payload.message),
  };
}

export function toCronJobsPayload(value: unknown): CronJobsPayload | null {
  const payload = toPayloadSource<CronJobsSourcePayload>(value);
  if (!payload) {
    return null;
  }
  const jobs = Array.isArray(payload.jobs) ? payload.jobs : [];
  return {
    jobs: jobs.map(normalizeCronJob).filter((job): job is CronJobView => job !== null),
  };
}
