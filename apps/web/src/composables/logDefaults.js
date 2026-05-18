export const DEFAULT_LOG_ENABLED = true;
export const DEFAULT_LOG_RETENTION_DAYS = 365;
export const DEFAULT_LOG_LEVEL = "INFO";
export const DEFAULT_LOG_LEVELS = ["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"];
export const DEFAULT_LOG_SYSTEM_PROMPT = true;
export const DEFAULT_LOG_SYSTEM_PROMPT_LINES = 0;
export const DEFAULT_LOG_REASONING_DETAILS = false;

export function createDefaultLogState() {
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

export function createDefaultLogForm() {
  return {
    enabled: DEFAULT_LOG_ENABLED,
    level: DEFAULT_LOG_LEVEL,
    retentionDays: DEFAULT_LOG_RETENTION_DAYS,
    logSystemPrompt: DEFAULT_LOG_SYSTEM_PROMPT,
    logSystemPromptLines: DEFAULT_LOG_SYSTEM_PROMPT_LINES,
    logReasoningDetails: DEFAULT_LOG_REASONING_DETAILS,
  };
}

export function normalizeLogSettings(log = {}) {
  const levels = Array.isArray(log.levels) && log.levels.length
    ? log.levels.map((level) => String(level || "").toUpperCase()).filter(Boolean)
    : DEFAULT_LOG_LEVELS;
  const level = String(log.level || DEFAULT_LOG_LEVEL).toUpperCase();
  return {
    enabled: log.enabled !== false,
    level: levels.includes(level) ? level : DEFAULT_LOG_LEVEL,
    retention_days: Number(log.retention_days || DEFAULT_LOG_RETENTION_DAYS),
    log_system_prompt: log.log_system_prompt !== false,
    log_system_prompt_lines: Number(log.log_system_prompt_lines || DEFAULT_LOG_SYSTEM_PROMPT_LINES),
    log_reasoning_details: Boolean(log.log_reasoning_details),
    levels,
  };
}
