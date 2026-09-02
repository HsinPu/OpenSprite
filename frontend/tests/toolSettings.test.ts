import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getToolCatalog,
  getToolSettings,
  putToolSettings,
  ToolSettingsApiError,
  toolSettingsErrorText,
} from "../src/api/toolSettings";
import { createTranslator } from "../src/i18n/catalog";


afterEach(() => vi.unstubAllGlobals());

describe("tool settings API", () => {
  it("reads the strict catalog and settings and writes the exact payload", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [{ id: "calculator", source: "builtin", effect: "read_only", available: true }] })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ enabled: true, enabledTools: ["calculator"] })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ enabled: false, enabledTools: ["calculator"] })));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getToolCatalog()).resolves.toEqual({ items: [{ id: "calculator", source: "builtin", effect: "read_only", available: true }] });
    await expect(getToolSettings()).resolves.toEqual({ enabled: true, enabledTools: ["calculator"] });
    await expect(putToolSettings({ enabled: false, enabledTools: ["calculator"] })).resolves.toEqual({ enabled: false, enabledTools: ["calculator"] });
    expect(fetchMock).toHaveBeenLastCalledWith("/api/settings/tools", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: false, enabledTools: ["calculator"] }),
    });
  });

  it.each([
    { enabled: true, enabledTools: ["calculator", "calculator"] },
    { enabled: true, enabledTools: ["Bad Tool"] },
    { enabled: true, enabledTools: [], extra: true },
  ])("rejects malformed settings responses", async (body) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(body))));
    await expect(getToolSettings()).rejects.toMatchObject({ code: "malformed_response" });
  });

  it("rejects unsorted, duplicate, or unknown catalog fields", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ items: [
      { id: "z_tool", source: "builtin", effect: "read_only", available: true },
      { id: "a_tool", source: "builtin", effect: "read_only", available: true },
    ] }))));
    await expect(getToolCatalog()).rejects.toMatchObject({ code: "malformed_response" });
  });

  it("maps only documented sanitized errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: "tool_not_found", message: "private", retryable: false } }), { status: 400 })));
    const error = await putToolSettings({ enabled: true, enabledTools: ["missing_tool"] }).catch((value: unknown) => value);
    expect(error).toBeInstanceOf(ToolSettingsApiError);
    expect(toolSettingsErrorText(error, createTranslator("en"))).toBe("The selected tool does not exist or is unavailable.");
  });
});
