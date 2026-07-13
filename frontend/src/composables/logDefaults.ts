import { toPayloadSource } from "./payloadBoundary";

export const DEFAULT_LOG_ENABLED = true;
export const DEFAULT_LOG_RETENTION_DAYS = 365;
export const DEFAULT_LOG_LEVEL = "INFO";
export const DEFAULT_LOG_LEVELS = ["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"];
export const DEFAULT_LOG_SYSTEM_PROMPT = true;
export const DEFAULT_LOG_SYSTEM_PROMPT_LINES = 0;
export const DEFAULT_LOG_REASONING_DETAILS = false;

type LogSettingsDataPayload = {
  enabled?: unknown;
  level?: unknown;
  retention_days?: unknown;
  log_system_prompt?: unknown;
  log_system_prompt_lines?: unknown;
  log_reasoning_details?: unknown;
  levels?: unknown;
};

export interface LogState {
  enabled: boolean;
  level: string;
  retention_days: number;
  log_system_prompt: boolean;
  log_system_prompt_lines: number;
  log_reasoning_details: boolean;
  levels: string[];
}

export interface LogForm {
  enabled: boolean;
  level: string;
  retentionDays: number;
  logSystemPrompt: boolean;
  logSystemPromptLines: number;
  logReasoningDetails: boolean;
}

export function createDefaultLogState(): LogState {
  return {
    enabled: DEFAULT_LOG_ENABLED,
    level: DEFAULT_LOG_LEVEL,
    retention_days: DEFAULT_LOG_RETENTION_DAYS,
    log_system_prompt: DEFAULT_LOG_SYSTEM_PROMPT,
    log_system_prompt_lines: DEFAULT_LOG_SYSTEM_PROMPT_LINES,
    log_reasoning_details: DEFAULT_LOG_REASONING_DETAILS,
    levels: DEFAULT_LOG_LEVELS,
  };
}

export function createDefaultLogForm(): LogForm {
  return {
    enabled: DEFAULT_LOG_ENABLED,
    level: DEFAULT_LOG_LEVEL,
    retentionDays: DEFAULT_LOG_RETENTION_DAYS,
    logSystemPrompt: DEFAULT_LOG_SYSTEM_PROMPT,
    logSystemPromptLines: DEFAULT_LOG_SYSTEM_PROMPT_LINES,
    logReasoningDetails: DEFAULT_LOG_REASONING_DETAILS,
  };
}

function toLogSettingsDataPayload(value: unknown): LogSettingsDataPayload {
  return toPayloadSource<LogSettingsDataPayload>(value) || {};
}

export function normalizeLogSettings(log: unknown = {}): LogState {
  const payload = toLogSettingsDataPayload(log);
  const rawLevels = Array.isArray(payload.levels) ? payload.levels : [];
  const levels = rawLevels.length
    ? rawLevels.map((level: unknown) => String(level || "").toUpperCase()).filter(Boolean)
    : DEFAULT_LOG_LEVELS;
  const level = String(payload.level || DEFAULT_LOG_LEVEL).toUpperCase();
  return {
    enabled: payload.enabled !== false,
    level: levels.includes(level) ? level : DEFAULT_LOG_LEVEL,
    retention_days: Number(payload.retention_days || DEFAULT_LOG_RETENTION_DAYS),
    log_system_prompt: payload.log_system_prompt !== false,
    log_system_prompt_lines: Number(payload.log_system_prompt_lines || DEFAULT_LOG_SYSTEM_PROMPT_LINES),
    log_reasoning_details: Boolean(payload.log_reasoning_details),
    levels,
  };
}
