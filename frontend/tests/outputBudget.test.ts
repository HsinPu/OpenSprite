import { describe, expect, it } from "vitest";

import {
  outputBudgetAvailable,
  outputBudgetLimit,
  outputCeiling,
} from "../src/features/ai-settings/outputBudget";


describe("output budget", () => {
  it.each([
    ["auto", 32_768, 128_000, 32_767],
    ["auto", 65_536, 128_000, 65_535],
    ["auto", 131_072, 128_000, 128_000],
    ["auto", 262_144, 128_000, 128_000],
    ["64k", 131_072, 128_000, 65_536],
    ["max", 131_072, 128_000, 128_000],
    ["64k", 131_072, 4_096, 4_096],
    ["max", 32_768, 128_000, 32_767],
  ] as const)("resolves %s within Context and model limits", (budget, context, model, expected) => {
    expect(outputBudgetLimit(budget, context, model)).toBe(expected);
  });

  it("disables fixed values that do not fit while keeping auto and max available", () => {
    expect(outputCeiling(32_768, 128_000)).toBe(32_767);
    expect(outputBudgetAvailable("32k", 32_768, 128_000)).toBe(false);
    expect(outputBudgetAvailable("16k", 32_768, 128_000)).toBe(true);
    expect(outputBudgetAvailable("auto", 32_768, 128_000)).toBe(true);
    expect(outputBudgetAvailable("max", 32_768, 128_000)).toBe(true);
  });
});
