export const MODEL_REASONING_EFFORTS = ["", "none", "minimal", "low", "medium", "high", "xhigh"] as const;

export type ModelReasoningEffort = (typeof MODEL_REASONING_EFFORTS)[number];

const MODEL_REASONING_EFFORT_SET: ReadonlySet<string> = new Set(MODEL_REASONING_EFFORTS);

function isModelReasoningEffort(value: string): value is ModelReasoningEffort {
  return MODEL_REASONING_EFFORT_SET.has(value);
}

export function normalizeModelReasoningEffort(value: unknown): ModelReasoningEffort {
  const normalized = String(value || "").trim().toLowerCase();
  return isModelReasoningEffort(normalized) ? normalized : "";
}
