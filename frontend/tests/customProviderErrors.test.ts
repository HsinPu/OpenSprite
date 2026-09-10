import { describe, expect, it } from "vitest";
import { createTranslator } from "../src/i18n/catalog";
import { customProviderErrorText } from "../src/features/ai-settings/customProviderErrors";

describe("custom Provider error messages", () => {
  it.each(["zh-TW", "en", "ja"] as const)("localizes recovery guidance in %s", (locale) => {
    const t = createTranslator(locale);
    for (const code of ["invalid_request", "revision_conflict", "provider_busy", "provider_in_use", "model_discovery_unsupported", "network_error", "malformed_response"]) {
      const message = customProviderErrorText(code, t);
      expect(message.length).toBeGreaterThan(10);
      expect(message).not.toContain(code);
      expect(message).not.toContain("models.custom.error");
    }
  });
});
