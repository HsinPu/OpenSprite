import type { OutputBudget } from "../../api/aiSettings";

const fixedLimits: Readonly<Record<Exclude<OutputBudget, "auto" | "max">, number>> = {
  "8k": 8_192,
  "16k": 16_384,
  "32k": 32_768,
  "64k": 65_536,
};

export const outputBudgetValues: ReadonlyArray<OutputBudget> = ["auto", "8k", "16k", "32k", "64k", "max"];

export function outputCeiling(contextLimit: number, modelMaximum: number): number {
  return Math.min(modelMaximum, 131_072, Math.max(1, contextLimit - 1));
}

export function outputBudgetLimit(
  budget: OutputBudget,
  contextLimit: number,
  modelMaximum: number,
): number {
  const safeMaximum = outputCeiling(contextLimit, modelMaximum);
  if (budget === "max") return safeMaximum;
  const target = budget === "auto" ? safeMaximum : fixedLimits[budget];
  return Math.min(target, safeMaximum);
}

export function outputBudgetAvailable(
  budget: OutputBudget,
  contextLimit: number,
  modelMaximum: number,
): boolean {
  return budget === "auto"
    || budget === "max"
    || fixedLimits[budget] <= outputCeiling(contextLimit, modelMaximum);
}
