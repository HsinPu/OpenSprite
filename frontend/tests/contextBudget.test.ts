import { describe, expect, it } from "vitest";

import {
  contextBudgetAvailable,
  contextBudgetLimit,
  formatTokenLimit,
} from "../src/features/ai-settings/contextBudget";


describe("context budget policy", () => {
  it.each([
    [32_768, 32_768],
    [65_536, 49_152],
    [131_072, 98_304],
    [262_144, 196_608],
    [1_050_000, 262_144],
  ])("resolves auto safely for a %i-token model", (maximum, expected) => {
    expect(contextBudgetLimit("auto", maximum)).toBe(expected);
  });

  it("caps fixed limits and disables choices above the model maximum", () => {
    expect(contextBudgetAvailable("128k", 131_072)).toBe(true);
    expect(contextBudgetAvailable("256k", 131_072)).toBe(false);
    expect(contextBudgetAvailable("max", 131_072)).toBe(true);
    expect(contextBudgetLimit("256k", 131_072)).toBe(131_072);
  });

  it("formats binary presets and large provider limits for display", () => {
    expect(formatTokenLimit(131_072)).toBe("128K");
    expect(formatTokenLimit(1_050_000)).toBe("1.05M");
  });
});
