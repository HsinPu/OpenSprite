import { describe, expect, it, vi } from "vitest";
import { AppInfoApiError, getAppInfo } from "../src/api/appInfo";

describe("app info client", () => {
  it("accepts the exact installed build shape", async () => {
    const value = { version: "0.1.0", revision: "84142959", buildType: "installed", dirty: false, installedAt: "2026-08-31T01:02:03Z" };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(value))));

    await expect(getAppInfo()).resolves.toEqual(value);
    expect(fetch).toHaveBeenCalledWith("/api/app-info");
  });

  it.each([
    { version: "0.1.0", revision: "bad!", buildType: "installed", dirty: false, installedAt: "2026-08-31T01:02:03Z" },
    { version: "0.1.0", revision: "84142959", buildType: "installed", dirty: "false", installedAt: "2026-08-31T01:02:03Z" },
    { version: "0.1.0", revision: "84142959", buildType: "installed", dirty: false, installedAt: null, extra: true },
  ])("rejects malformed build metadata", async (value) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(value))));
    await expect(getAppInfo()).rejects.toBeInstanceOf(AppInfoApiError);
  });
});
