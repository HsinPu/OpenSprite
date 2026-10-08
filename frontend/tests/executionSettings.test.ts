import { afterEach, describe, expect, it, vi } from "vitest";

import { ExecutionSettingsApiError, executionSettingsErrorText, getExecutionSettings, putExecutionSettings, type ExecutionSettings } from "../src/api/executionSettings";
import { createTranslator } from "../src/i18n/catalog";

const settings: ExecutionSettings = {
  selection: { loopId: "standard", policyId: "standard" },
  plugins: [
    { id: "standard", kind: "loop", name: "Standard Loop", description: "Default loop", version: "2.0.0", apiVersion: 1, status: "available" },
    { id: "standard", kind: "policy", name: "Standard", description: "Default recovery", version: "2.0.0", apiVersion: 1, status: "available" },
    { id: "no_recovery", kind: "policy", name: "No recovery", description: "No automatic recovery", version: "2.0.0", apiVersion: 1, status: "available" },
  ],
};
const body = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
}
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

  it("waits for every pending write, including writes started while the read is waiting", async () => {
    const first = deferred<Response>();
    const second = deferred<Response>();
    const third = deferred<Response>();
    const selected = { loopId: "standard", policyId: "no_recovery" };
    const responses = [first.promise, second.promise, third.promise];
    let stored = settings;
    const fetchMock = vi.fn((_path: string, init?: RequestInit) => init?.method === "PUT"
      ? responses.shift()!
      : Promise.resolve(body(stored)));
    vi.stubGlobal("fetch", fetchMock);
    const firstWrite = putExecutionSettings(selected);
    const reading = getExecutionSettings();
    const secondWrite = putExecutionSettings(settings.selection);
    let thirdWrite: Promise<ExecutionSettings> | undefined;
    try {
      second.resolve(body(settings));
      await secondWrite;
      expect(fetchMock).toHaveBeenCalledTimes(2);
      thirdWrite = putExecutionSettings(settings.selection);
      first.resolve(body({ ...settings, selection: selected }));
      await firstWrite;
      expect(fetchMock).toHaveBeenCalledTimes(3);
      stored = settings;
      third.resolve(body(stored));
      await expect(reading).resolves.toEqual(stored);
      expect(fetchMock).toHaveBeenCalledTimes(4);
      expect(fetchMock).toHaveBeenLastCalledWith("/api/settings/execution", undefined);
    } finally {
      first.resolve(body({ ...settings, selection: selected }));
      second.resolve(body(settings));
      third.resolve(body(settings));
      await Promise.allSettled([firstWrite, secondWrite, reading, ...(thirdWrite ? [thirdWrite] : [])]);
    }
  });

  it("reads persisted settings after a failed write and cleans up the pending write", async () => {
    const pending = deferred<Response>();
    const fetchMock = vi.fn((_path: string, init?: RequestInit) => init?.method === "PUT"
      ? pending.promise
      : Promise.resolve(body(settings)));
    vi.stubGlobal("fetch", fetchMock);
    const writing = putExecutionSettings({ loopId: "standard", policyId: "no_recovery" });
    const failure = expect(writing).rejects.toMatchObject({ code: "network_error" });
    const reading = getExecutionSettings();
    try {
      expect(fetchMock).toHaveBeenCalledOnce();
      pending.reject(new Error("offline"));
      await failure;
      await expect(reading).resolves.toEqual(settings);
      await expect(getExecutionSettings()).resolves.toEqual(settings);
      expect(fetchMock).toHaveBeenCalledTimes(3);
    } finally {
      pending.resolve(body({ ...settings, selection: { loopId: "standard", policyId: "no_recovery" } }));
      await Promise.allSettled([writing, failure, reading]);
    }
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
