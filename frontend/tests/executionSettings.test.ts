import { afterEach, describe, expect, it, vi } from "vitest";

import { ExecutionSettingsApiError, executionSettingsErrorText, getExecutionSettings, putExecutionSettings, type ExecutionSettings } from "../src/api/executionSettings";
import { createTranslator } from "../src/i18n/catalog";

const settings: ExecutionSettings = {
  selection: { loopId: "standard", policyId: "standard" },
  plugins: [
    { id: "standard", kind: "loop", name: "Standard Loop", description: "Default loop", version: "1.0.0", apiVersion: 1, status: "available" },
    { id: "standard", kind: "policy", name: "Standard", description: "Default recovery", version: "1.0.0", apiVersion: 1, status: "available" },
    { id: "no_recovery", kind: "policy", name: "No recovery", description: "No automatic recovery", version: "1.0.0", apiVersion: 1, status: "available" },
  ],
};
const body = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
afterEach(() => vi.unstubAllGlobals());

describe("execution settings API", () => {
  it("reads metadata and sends only the two selected IDs", async () => {
    const selected = { loopId: "standard", policyId: "no_recovery" };
    const fetchMock = vi.fn().mockResolvedValueOnce(body(settings)).mockResolvedValueOnce(body({ ...settings, selection: selected }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(getExecutionSettings()).resolves.toEqual(settings);
    await expect(putExecutionSettings(selected)).resolves.toEqual({ ...settings, selection: selected });
    expect(fetchMock).toHaveBeenLastCalledWith("/api/settings/execution", {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(selected),
    });
  });

  it("allows a missing saved plugin and reports newer incompatible API versions", async () => {
    const response = { selection: { loopId: "removed", policyId: "standard" }, plugins: [...settings.plugins, { ...settings.plugins[0], id: "future.loop", apiVersion: 2, status: "incompatible" }] };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(body(response)));
    await expect(getExecutionSettings()).resolves.toEqual(response);
  });

  it.each([
    { ...settings, extra: true },
    { ...settings, selection: { ...settings.selection, extra: "hidden" } },
    { ...settings, selection: { loopId: "../path", policyId: "standard" } },
    { ...settings, plugins: [...settings.plugins, settings.plugins[0]] },
    { ...settings, plugins: [{ ...settings.plugins[0], kind: "tool" }] },
    { ...settings, plugins: [{ ...settings.plugins[0], apiVersion: true }] },
    { ...settings, plugins: [{ ...settings.plugins[0], apiVersion: 0 }] },
    { ...settings, plugins: [{ ...settings.plugins[0], apiVersion: 1.5 }] },
    { ...settings, plugins: [{ ...settings.plugins[0], version: "" }] },
    { ...settings, plugins: [{ ...settings.plugins[0], status: "enabled" }] },
    { ...settings, plugins: [{ ...settings.plugins[0], factory: "private" }] },
  ])("rejects malformed catalogs and fields", async (value) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(body(value)));
    await expect(getExecutionSettings()).rejects.toMatchObject({ code: "malformed_response" });
  });

  it("rejects a PUT response that does not confirm the requested IDs", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(body(settings)));
    await expect(putExecutionSettings({ loopId: "standard", policyId: "no_recovery" })).rejects.toMatchObject({ code: "malformed_response" });
  });

  it.each([[400, "invalid_request"], [503, "plugin_unavailable"], [503, "settings_store_unavailable"], [500, "internal_error"]] as const)("maps the documented %s error %s", async (status, code) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(body({ error: { code, message: "private exception", retryable: status === 503 } }, status)));
    const error: unknown = await putExecutionSettings(settings.selection).catch((failure: unknown) => failure);
    expect(error).toBeInstanceOf(ExecutionSettingsApiError);
    expect(error).toMatchObject({ code });
    expect(executionSettingsErrorText(error, createTranslator("en"))).not.toContain("private");
  });

  it("rejects wrong error/status combinations and malformed successful JSON", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(body({ error: { code: "invalid_request", message: "invalid", retryable: false } }, 503))
      .mockResolvedValueOnce(new Response("not-json"));
    vi.stubGlobal("fetch", fetchMock);
    await expect(getExecutionSettings()).rejects.toMatchObject({ code: "malformed_response" });
    await expect(getExecutionSettings()).rejects.toMatchObject({ code: "malformed_response" });
  });

  it("sanitizes network failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("private network details")));
    await expect(getExecutionSettings()).rejects.toMatchObject({ code: "network_error", message: "network_error" });
  });
});
