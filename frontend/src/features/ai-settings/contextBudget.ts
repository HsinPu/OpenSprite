import type { ContextBudget } from "../../api/aiSettings";

const fixedLimits: Readonly<Record<Exclude<ContextBudget, "auto" | "max">, number>> = {
  "32k": 32_768,
  "64k": 65_536,
  "128k": 131_072,
  "256k": 262_144,
};

export const contextBudgetValues: ReadonlyArray<ContextBudget> = ["auto", "32k", "64k", "128k", "256k", "max"];

export function contextBudgetLimit(budget: ContextBudget, modelMaximum: number): number {
  if (budget === "max") return modelMaximum;
  if (budget !== "auto") return Math.min(fixedLimits[budget], modelMaximum);
  if (modelMaximum <= 32_768) return modelMaximum;
  if (modelMaximum <= 65_536) return Math.min(49_152, modelMaximum);
  if (modelMaximum <= 131_072) return Math.min(98_304, modelMaximum);
  if (modelMaximum <= 262_144) return Math.min(196_608, modelMaximum);
  return Math.min(262_144, modelMaximum);
}

export function contextBudgetAvailable(budget: ContextBudget, modelMaximum: number): boolean {
  return budget === "auto" || budget === "max" || fixedLimits[budget] <= modelMaximum;
}

export function formatTokenLimit(tokens: number): string {
  if (tokens >= 1_000_000) return `${Number((tokens / 1_000_000).toFixed(2))}M`;
  return `${Math.round(tokens / 1024)}K`;
}
