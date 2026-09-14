import { expect, it } from "vitest";
import { disabledModelsError, normalizeDisabledModels } from "../src/features/settings/providerToolPolicy";

it("trims and deduplicates without changing model case", () => {
  expect(normalizeDisabledModels([" A ", "A", "a"])).toEqual(["A", "a"]);
});
it("matches backend code-point length and count boundaries", () => {
  expect(disabledModelsError(["😀".repeat(256)])).toBeNull();
  expect(disabledModelsError(["a".repeat(257)])).toBe("models.tools.longId");
  expect(disabledModelsError([" "])).toBe("models.tools.emptyId");
  expect(disabledModelsError(Array.from({ length: 1000 }, (_, i) => String(i)))).toBeNull();
  expect(disabledModelsError(Array.from({ length: 1001 }, (_, i) => String(i)))).toBe("models.tools.tooManyIds");
});
