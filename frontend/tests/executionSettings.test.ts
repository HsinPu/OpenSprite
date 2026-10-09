import { afterEach, describe, expect, it, vi } from "vitest";
import { ExecutionSettingsApiError, executionSettingsErrorText, getExecutionSettings, putExecutionSettings, type ExecutionSettings } from "../src/api/executionSettings";
import { createTranslator } from "../src/i18n/catalog";
const settings: ExecutionSettings = {
  selection: { pluginId: "standard" }, revision: 0, migration: null,
  plugins: [{ id: "standard", name: "Standard", description: "Default", version: "0.1.0", apiVersion: 5, status: "available" }],
};
const body = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const saved = { ...settings, selection: { pluginId: "external" }, revision: 1 };
afterEach(() => vi.unstubAllGlobals());
function deferred<T>() {
  let resolve!: (value: T) => void; let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((a, b) => { resolve = a; reject = b; });
  return { promise, resolve, reject };
}
describe("single Loop settings API", () => {
  it("sends one ID and optimistic revision, accepting only its confirmed revision", async () => {
    const mock = vi.fn().mockResolvedValueOnce(body(settings)).mockResolvedValueOnce(body(saved));
    vi.stubGlobal("fetch", mock);
    expect(await getExecutionSettings()).toEqual(settings);
    expect(await putExecutionSettings({ pluginId: "external" }, 0)).toEqual(saved);
    expect(mock).toHaveBeenLastCalledWith("/api/settings/execution", {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ pluginId: "external", expectedRevision: 0 }),
    });
  });
  it("waits for all in-flight writes before reading after a remount", async () => {
    const first = deferred<Response>(); const second = deferred<Response>();
    const mock = vi.fn().mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise).mockResolvedValue(body(saved));
    vi.stubGlobal("fetch", mock);
    const one = putExecutionSettings({ pluginId: "external" }, 0);
    const read = getExecutionSettings();
    const two = putExecutionSettings({ pluginId: "standard" }, 1);
    second.resolve(body({ ...settings, revision: 2 })); await two;
    expect(mock).toHaveBeenCalledTimes(2);
    first.resolve(body(saved)); await one;
    expect(await read).toEqual(saved); expect(mock).toHaveBeenCalledTimes(3);
  });
  it("reads again after a rejected write", async () => {
    const pending = deferred<Response>();
    const mock = vi.fn().mockReturnValueOnce(pending.promise).mockResolvedValue(body(settings));
    vi.stubGlobal("fetch", mock);
    const writing = putExecutionSettings({ pluginId: "external" }, 0);
    const failure = expect(writing).rejects.toMatchObject({ code: "network_error" });
    const read = getExecutionSettings(); pending.reject(new Error("private")); await failure;
    expect(await read).toEqual(settings);
  });
  it("reads explicit migration information and missing selections without substituting defaults", async () => {
    const migration = { ...settings, selection: null, migration: { loopId: "old", policyId: "old_policy" } };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(body(migration)).mockResolvedValueOnce(body(saved)));
    expect(await getExecutionSettings()).toEqual(migration);
    expect(await getExecutionSettings()).toEqual(saved);
  });
  it.each([
    { ...settings, extra: true }, { ...settings, selection: { pluginId: "../private" } },
    { ...settings, selection: { loopId: "standard", policyId: "standard" } },
    { ...settings, revision: -1 }, { ...settings, revision: true }, { ...settings, revision: Number.MAX_SAFE_INTEGER + 1 },
    { ...settings, selection: null }, { ...settings, migration: { loopId: "old", policyId: "old" } },
    { ...settings, plugins: [...settings.plugins, settings.plugins[0]] },
    { ...settings, plugins: [{ ...settings.plugins[0], kind: "policy" }] },
    { ...settings, plugins: [{ ...settings.plugins[0], apiVersion: 2 }] },
    { ...settings, plugins: [{ ...settings.plugins[0], apiVersion: 3 }] },
    { ...settings, plugins: [{ ...settings.plugins[0], status: "enabled" }] },
    { ...settings, plugins: [{ ...settings.plugins[0], version: "" }] },
  ])("rejects malformed catalogs", async value => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(body(value)));
    await expect(getExecutionSettings()).rejects.toMatchObject({ code: "malformed_response" });
  });
  it.each([{ ...saved, revision: 0 }, { ...saved, selection: { pluginId: "standard" } }])("rejects a mismatched confirmation", async value => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(body(value)));
    await expect(putExecutionSettings({ pluginId: "external" }, 0)).rejects.toMatchObject({ code: "malformed_response" });
  });
  it.each([[400, "invalid_request"], [409, "revision_conflict"], [503, "plugin_unavailable"], [503, "settings_store_unavailable"], [500, "internal_error"]] as const)("maps %s %s without displaying server details", async (status, code) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(body({ error: { code, message: "private", retryable: false } }, status)));
    const error: unknown = await putExecutionSettings({ pluginId: "external" }, 0).catch(x => x);
    expect(error).toBeInstanceOf(ExecutionSettingsApiError);
    expect(error).toMatchObject({ code });
    expect(executionSettingsErrorText(error, createTranslator("en"))).not.toContain("private");
  });
  it("rejects invalid write input before fetch", async () => {
    const mock = vi.fn(); vi.stubGlobal("fetch", mock);
    await expect(putExecutionSettings({ pluginId: "../x" }, 0)).rejects.toMatchObject({ code: "invalid_request" });
    await expect(putExecutionSettings({ pluginId: "standard" }, -1)).rejects.toMatchObject({ code: "invalid_request" });
    expect(mock).not.toHaveBeenCalled();
  });
});
