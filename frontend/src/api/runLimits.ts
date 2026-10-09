export const limitErrorCodes = {
  duration_seconds: "run_deadline_exceeded",
  model_requests: "model_request_limit_reached",
  summary_requests: "summary_request_limit_reached",
  generated_chars: "generated_text_limit_reached",
  host_operations: "host_operation_limit_reached",
} as const;
export type RunLimitEvidence = { kind: keyof typeof limitErrorCodes; maximum: number; used: number };

export function validRunLimit(value: unknown, errorCode: unknown): value is RunLimitEvidence {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const data = value as Record<string, unknown>;
  if (Object.keys(data).sort().join(",") !== "kind,maximum,used" || typeof data.kind !== "string"
    || !Object.hasOwn(limitErrorCodes, data.kind) || limitErrorCodes[data.kind as keyof typeof limitErrorCodes] !== errorCode) return false;
  const numbers = [data.maximum, data.used];
  return numbers.every(n => typeof n === "number" && Number.isFinite(n) && n >= 0 && n <= Number.MAX_SAFE_INTEGER)
    && Number(data.maximum) > 0 && (data.kind === "duration_seconds" || numbers.every(Number.isSafeInteger));
}
