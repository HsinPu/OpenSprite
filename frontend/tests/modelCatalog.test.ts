import { describe, expect, it } from "vitest";

import { openRouterModelCatalog } from "../src/features/ai-settings/modelCatalog";


describe("OpenRouter model catalog", () => {
  it("uses a Context-bounded 32K fallback when output capability is unknown", () => {
    const models = openRouterModelCatalog([
      { id: "openrouter/auto", name: "Auto Router", contextWindowTokens: 131_072, maxOutputTokens: null },
      { id: "small/model", name: "Small", contextWindowTokens: 16_384, maxOutputTokens: null },
    ]);

    expect(models.map((model) => model.maxOutputTokens)).toEqual([32_768, 16_384]);
  });
});
