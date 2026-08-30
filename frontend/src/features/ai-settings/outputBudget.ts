import type { OutputBudget } from "../../api/aiSettings";


const fixedLimits: Readonly<Record<Exclude<OutputBudget, "auto" | "max">, number>> = {
  "8k": 8_192,
  "16k": 16_384,
  "32k": 32_768,
  "64k": 65_536,
};

export const outputBudgetValues: ReadonlyArray<OutputBudget> = ["auto", "8k", "16k", "32k", "64k", "max"];

export function safeOutputMaximum(contextLimit: number, modelMaximum: number): number {
  const safetyReserve = Math.max(4_096, Math.ceil(contextLimit / 10));
  const minimumInputReserve = Math.max(1, Math.ceil(contextLimit / 4));
  return Math.min(
    modelMaximum,
    Math.max(1, contextLimit - safetyReserve - minimumInputReserve),
  );
}

export function outputBudgetLimit(
  budget: OutputBudget,
  contextLimit: number,
  modelMaximum: number,
): number {
  const safeMaximum = safeOutputMaximum(contextLimit, modelMaximum);
  if (budget === "max") return safeMaximum;
  const target = budget === "auto"
    ? Math.min(32_768, Math.max(8_192, Math.floor(contextLimit / 4)))
    : fixedLimits[budget];
  return Math.min(target, safeMaximum);
}

export function outputBudgetAvailable(
  budget: OutputBudget,
  contextLimit: number,
  modelMaximum: number,
): boolean {
  return budget === "auto"
    || budget === "max"
    || fixedLimits[budget] <= safeOutputMaximum(contextLimit, modelMaximum);
}
