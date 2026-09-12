import { validContextReceipt } from "./contextReceipts";

export function validAttemptPayload(data: Record<string, unknown>): boolean {
  const common = ["schemaVersion", "requestId", "attemptId", "attemptNumber", "purpose", "retryOfAttemptId", "retryCause", "compactionId", "parentRequestId", "status"];
  const fields: Record<string, string[]> = { started: [], completed: ["finishReason", "inputTokens", "outputTokens"], failed: ["errorCode"], cancelled: [] };
  const extra = fields[String(data.status)];
  if (!extra || data.schemaVersion !== 1) return false;
  const keys = [...common, ...extra];
  if (data.status === "started" && "context" in data) {
    if (!validContextReceipt(data.context)) return false;
    keys.push("context");
  }
  if (Object.keys(data).length !== keys.length || Object.keys(data).some(key => !keys.includes(key))) return false;
  for (const key of ["requestId", "attemptId", "retryOfAttemptId", "compactionId", "parentRequestId"]) {
    if (data[key] === null && !["requestId", "attemptId"].includes(key)) continue;
    if (typeof data[key] !== "string" || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(data[key])) return false;
  }
  if (!Number.isSafeInteger(data.attemptNumber) || Number(data.attemptNumber) < 1 || Number(data.attemptNumber) > 64) return false;
  if (!["main", "continuation", "compaction"].includes(String(data.purpose)) || ![null, "provider_context_limit"].includes(data.retryCause as string | null)) return false;
  if ((data.attemptNumber === 1) !== (data.retryOfAttemptId === null) || (data.retryOfAttemptId === null) !== (data.retryCause === null)) return false;
  if (data.status === "completed") return ["final", "tool_calls", "output_limit"].includes(String(data.finishReason)) && [data.inputTokens, data.outputTokens].every(value => value === null || (Number.isSafeInteger(value) && Number(value) >= 0));
  if (data.status === "failed") return ["provider_not_connected", "invalid_credentials", "provider_rate_limited", "provider_timeout", "provider_unreachable", "context_limit_exceeded", "credential_store_unavailable", "invalid_provider_response", "internal_error"].includes(String(data.errorCode));
  return true;
}
