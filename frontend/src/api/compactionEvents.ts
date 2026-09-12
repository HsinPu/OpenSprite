/** Allowlisted metadata only; no prompts, summaries, or provider error bodies. */
export function validCompactionPayload(type: string, data: Record<string, unknown>): boolean {
  if (type === "context.compaction.started" && Object.keys(data).length === 0) return true;
  const fields: Record<string, string[]> = {
    "context.compaction.started": ["reason", "fromSequence", "throughSequence", "estimatedBeforeTokens", "inputBudgetTokens"],
    "context.compaction.completed": ["throughSequence", "inputTokens", "outputTokens"],
    "context.compaction.failed": ["errorCode"],
    "context.compaction.cancelled": ["reason"],
  };
  const required = fields[type];
  if (!required) return false;
  const keys = ["schemaVersion", "compactionId", ...required];
  if (Object.keys(data).length !== keys.length || Object.keys(data).some((key) => !keys.includes(key))) return false;
  if (data.schemaVersion !== 1 || typeof data.compactionId !== "string" || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(data.compactionId)) return false;
  const numeric = required.filter((key) => !["reason", "errorCode"].includes(key));
  if (numeric.some((key) => !Number.isSafeInteger(data[key]) || (data[key] as number) < 0)) return false;
  if (type === "context.compaction.started") return ["local_budget", "provider_context_limit"].includes(String(data.reason)) && (data.fromSequence as number) >= 1 && (data.fromSequence as number) <= (data.throughSequence as number) && (data.inputBudgetTokens as number) > 0;
  if (type === "context.compaction.completed") return (data.throughSequence as number) > 0;
  if (type === "context.compaction.failed") return ["context_limit", "preparation_failed", "provider_failed"].includes(String(data.errorCode));
  return data.reason === "cancelled";
}
