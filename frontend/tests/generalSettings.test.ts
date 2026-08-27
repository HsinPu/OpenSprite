import { afterEach, describe, expect, it, vi } from "vitest";

import {
  GeneralSettingsApiError,
  generalSettingsErrorText,
  getGeneralSettings,
  putGeneralSettings,
} from "../src/api/generalSettings";
import { createTranslator } from "../src/i18n/catalog";

afterEach(() => vi.unstubAllGlobals());

describe("general settings API", () => {
  it("reads and writes only the strict locale and time-zone shape", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ locale: "ja", timeZone: "Asia/Taipei" })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ locale: "en", timeZone: "UTC" })));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getGeneralSettings()).resolves.toEqual({ locale: "ja", timeZone: "Asia/Taipei" });
    await expect(putGeneralSettings({ locale: "en", timeZone: "UTC" })).resolves.toEqual({ locale: "en", timeZone: "UTC" });
    expect(fetchMock).toHaveBeenLastCalledWith("/api/settings/general", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ locale: "en", timeZone: "UTC" }),
    });
  });

  it.each([
    { locale: "other", timeZone: "system" },
    { locale: "en", timeZone: "Asia/Tokyo" },
    { locale: "en", timeZone: "UTC", extra: true },
  ])("rejects malformed responses", async (body) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(body))));
    await expect(getGeneralSettings()).rejects.toMatchObject({ code: "malformed_response" });
  });

  it("maps only the documented sanitized error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: "settings_store_unavailable", message: "private", retryable: true } }), { status: 503 })));
    const error = await getGeneralSettings().catch((value: unknown) => value);
    expect(error).toBeInstanceOf(GeneralSettingsApiError);
    expect(generalSettingsErrorText(error, createTranslator("en"))).toBe("Language and time-zone settings cannot be read or saved right now.");
  });
});
